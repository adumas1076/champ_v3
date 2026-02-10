# ============================================
# CHAMP V3 -- Brick 7 Gate Test (Ears)
# Tests wake word detection + LiveKit bridge
# Run: python gate_test_ears.py
# ============================================

import asyncio
import sys
import numpy as np
from unittest.mock import MagicMock, AsyncMock, patch


async def run_gate_tests():
    print("=" * 60)
    print("CHAMP V3 -- BRICK 7 GATE TEST (EARS)")
    print("Built to build. Born to create.")
    print("=" * 60)

    passed = 0
    failed = 0

    # ---- Test 1: Config loads ----
    print("\n[1/6] EarsSettings loads with .env values...")
    try:
        from ears.config import EarsSettings
        s = EarsSettings(
            LIVEKIT_URL="wss://test",
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret-long-enough-for-jwt",
        )
        if s.sample_rate == 16000 and s.frame_ms == 80:
            print(f"  PASSED: rate={s.sample_rate}, frame={s.frame_ms}ms, model={s.wake_model}")
            passed += 1
        else:
            print(f"  FAILED: unexpected defaults")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 2: openWakeWord model loads ----
    print("\n[2/6] openWakeWord model loads (hey_jarvis placeholder)...")
    try:
        from openwakeword.model import Model as OWWModel
        model = OWWModel(wakeword_models=["hey_jarvis"], vad_threshold=0.5, inference_framework="onnx")
        keys = list(model.models.keys())
        if keys:
            print(f"  PASSED: Model loaded with keys: {keys}")
            passed += 1
        else:
            print(f"  FAILED: No model keys found")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 3: Wake word detection on silence ----
    print("\n[3/6] Silence frame returns low confidence...")
    try:
        silence = np.zeros(1280, dtype=np.int16)
        prediction = model.predict(silence)
        score = list(prediction.values())[0]
        if score < 0.3:
            print(f"  PASSED: silence score={score:.4f} (< 0.3)")
            passed += 1
        else:
            print(f"  FAILED: silence score={score:.4f} (expected < 0.3)")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 4: sounddevice mic access ----
    print("\n[4/6] sounddevice can list audio devices...")
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [d for d in devices if d["max_input_channels"] > 0]
        if input_devs:
            default = sd.query_devices(kind="input")
            print(f"  PASSED: {len(input_devs)} input devices, default: {default['name']}")
            passed += 1
        else:
            print(f"  FAILED: No input devices found")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 5: LiveKit token generation ----
    print("\n[5/6] AccessToken generates valid JWT...")
    try:
        from livekit.api import AccessToken, VideoGrants
        token = AccessToken(
            "APIydS6B3LNPSoA",
            "opbyZAK9fBfTxKRXjno3USIC8Pu71ODNkvhX6V2U2kv",
        )
        token.with_identity("ears-listener")
        token.with_name("Champ Ears")
        token.with_grants(VideoGrants(
            room_join=True,
            room="champ-ears",
            can_publish=True,
            can_subscribe=True,
        ))
        jwt_str = token.to_jwt()
        if jwt_str and jwt_str.count(".") == 2:
            print(f"  PASSED: JWT generated ({len(jwt_str)} chars)")
            passed += 1
        else:
            print(f"  FAILED: Invalid JWT")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 6: State machine transitions ----
    print("\n[6/6] Listener state machine: LISTENING -> CONVERSATION -> LISTENING...")
    try:
        from ears.listener import EarsListener, ListenerState

        with patch("ears.listener.OWWModel") as MockModel:
            instance = MockModel.return_value
            instance.models = {"hey_jarvis": MagicMock()}
            instance.predict.return_value = {"hey_jarvis": 0.95}
            instance.reset = MagicMock()

            settings = EarsSettings(
                LIVEKIT_URL="wss://test",
                LIVEKIT_API_KEY="key",
                LIVEKIT_API_SECRET="secret-long-enough-for-jwt",
            )
            listener = EarsListener(settings)
            assert listener.state == ListenerState.LISTENING

            # Mock bridge
            listener.bridge = MagicMock()
            listener.bridge.connect = AsyncMock()
            listener.bridge.send_audio = AsyncMock()
            listener.bridge.disconnect = AsyncMock()
            listener.bridge.is_connected = True

            # Trigger wake word
            frame = np.zeros(1280, dtype=np.int16)
            await listener._process_listening(frame)
            assert listener.state == ListenerState.CONVERSATION

            # Simulate silence timeout
            listener.settings.silence_timeout_s = 0.0
            listener.settings.cooldown_s = 0.0
            listener._last_speech_time = 0.0
            await listener._process_conversation(frame)
            assert listener.state == ListenerState.LISTENING

            print(f"  PASSED: LISTENING -> CONVERSATION -> LISTENING")
            passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"BRICK 7 GATE TEST: {passed}/6 passed, {failed}/6 failed")
    if failed == 0:
        print("\nBRICK 7 GATE: PASSED")
        print("Ears are wired. Champ can HEAR you now.")
    else:
        print("\nBRICK 7 GATE: NEEDS WORK")
    print("=" * 60)

    return failed


if __name__ == "__main__":
    sys.exit(asyncio.run(run_gate_tests()))
