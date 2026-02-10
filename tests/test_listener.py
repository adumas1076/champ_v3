# ============================================
# CHAMP V3 -- Ears Listener Tests
# Brick 7: Unit tests for wake word listener
# Run: python -m pytest tests/test_listener.py -v
# ============================================

import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ears.config import EarsSettings
from ears.listener import (
    WakeWordDetector,
    LiveKitBridge,
    EarsListener,
    ListenerState,
)


@pytest.fixture
def settings():
    """Test settings with defaults."""
    return EarsSettings(
        LIVEKIT_URL="wss://test.livekit.cloud",
        LIVEKIT_API_KEY="test-api-key-1234",
        LIVEKIT_API_SECRET="test-secret-key-that-is-long-enough-for-jwt-signing",
    )


@pytest.fixture
def silence_frame():
    """80ms of silence at 16kHz mono (1280 samples)."""
    return np.zeros(1280, dtype=np.int16)


@pytest.fixture
def speech_frame():
    """80ms of simulated speech (loud signal)."""
    return (np.random.randn(1280) * 10000).astype(np.int16)


# ---- Test 1: Config loads with sane defaults ----

def test_config_defaults(settings):
    """EarsSettings loads with correct defaults."""
    assert settings.sample_rate == 16000
    assert settings.channels == 1
    assert settings.frame_ms == 80
    assert settings.wake_threshold == 0.5
    assert settings.room_name == "champ-ears"
    assert settings.silence_timeout_s == 30.0
    assert settings.cooldown_s == 2.0
    assert settings.wake_model == "hey_jarvis"


# ---- Test 2: WakeWordDetector returns score ----

def test_detector_returns_score(settings):
    """Detector returns float between 0 and 1."""
    with patch("ears.listener.OWWModel") as MockModel:
        instance = MockModel.return_value
        instance.models = {"hey_jarvis": MagicMock()}
        instance.predict.return_value = {"hey_jarvis": 0.85}

        detector = WakeWordDetector(settings)
        frame = np.zeros(1280, dtype=np.int16)
        score = detector.detect(frame)

        assert 0.0 <= score <= 1.0
        assert score == 0.85
        instance.predict.assert_called_once()


# ---- Test 3: Below threshold stays LISTENING ----

@pytest.mark.asyncio(loop_scope="function")
async def test_no_trigger_below_threshold(settings, silence_frame):
    """Score below threshold -> stay in LISTENING state."""
    with patch("ears.listener.OWWModel") as MockModel:
        instance = MockModel.return_value
        instance.models = {"hey_jarvis": MagicMock()}
        instance.predict.return_value = {"hey_jarvis": 0.2}

        listener = EarsListener(settings)
        assert listener.state == ListenerState.LISTENING

        await listener._process_listening(silence_frame)
        assert listener.state == ListenerState.LISTENING


# ---- Test 4: Above threshold triggers activation ----

@pytest.mark.asyncio(loop_scope="function")
async def test_trigger_above_threshold(settings, silence_frame):
    """Score above threshold -> CONVERSATION + bridge.connect called."""
    with patch("ears.listener.OWWModel") as MockModel:
        instance = MockModel.return_value
        instance.models = {"hey_jarvis": MagicMock()}
        instance.predict.return_value = {"hey_jarvis": 0.9}
        instance.reset = MagicMock()

        listener = EarsListener(settings)
        listener.bridge = MagicMock()
        listener.bridge.connect = AsyncMock()
        listener.bridge.is_connected = True

        await listener._process_listening(silence_frame)
        assert listener.state == ListenerState.CONVERSATION
        listener.bridge.connect.assert_awaited_once()


# ---- Test 5: Conversation forwards audio ----

@pytest.mark.asyncio(loop_scope="function")
async def test_conversation_forwards_audio(settings, speech_frame):
    """During CONVERSATION, audio is sent to bridge."""
    with patch("ears.listener.OWWModel") as MockModel:
        instance = MockModel.return_value
        instance.models = {"hey_jarvis": MagicMock()}

        listener = EarsListener(settings)
        listener.state = ListenerState.CONVERSATION
        listener.bridge = MagicMock()
        listener.bridge.send_audio = AsyncMock()
        listener._last_speech_time = float("inf")

        await listener._process_conversation(speech_frame)
        listener.bridge.send_audio.assert_awaited_once()


# ---- Test 6: Silence timeout triggers deactivation ----

@pytest.mark.asyncio(loop_scope="function")
async def test_silence_timeout_disconnects(settings, silence_frame):
    """Extended silence -> disconnect -> back to LISTENING."""
    with patch("ears.listener.OWWModel") as MockModel:
        instance = MockModel.return_value
        instance.models = {"hey_jarvis": MagicMock()}

        listener = EarsListener(settings)
        listener.settings.silence_timeout_s = 0.0
        listener.settings.cooldown_s = 0.0
        listener.state = ListenerState.CONVERSATION
        listener._last_speech_time = 0.0

        listener.bridge = MagicMock()
        listener.bridge.send_audio = AsyncMock()
        listener.bridge.disconnect = AsyncMock()
        listener.bridge.is_connected = True

        await listener._process_conversation(silence_frame)
        listener.bridge.disconnect.assert_awaited_once()
        assert listener.state == ListenerState.LISTENING


# ---- Test 7: Token generation ----

def test_token_generation(settings):
    """LiveKitBridge generates a valid JWT string."""
    bridge = LiveKitBridge(settings)
    token = bridge._generate_token()
    assert isinstance(token, str)
    assert len(token) > 20
    # JWT has 3 dot-separated parts
    assert token.count(".") == 2
