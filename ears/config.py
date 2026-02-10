# ============================================
# CHAMP V3 -- Ears Configuration
# Brick 7: Wake Word Detection
# All settings loaded from environment variables
# ============================================

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class EarsSettings(BaseSettings):
    """Ears layer configuration. Loaded from .env."""

    # --- Wake Word ---
    wake_model: str = Field(
        default="hey_jarvis",
        alias="WAKE_WORD_MODEL",
    )
    wake_threshold: float = Field(default=0.5, alias="WAKE_THRESHOLD")
    vad_threshold: float = Field(default=0.5, alias="WAKE_VAD_THRESHOLD")
    custom_model_path: str = Field(default="", alias="WAKE_CUSTOM_MODEL_PATH")

    # --- Audio ---
    sample_rate: int = 16000  # openWakeWord requires 16kHz
    channels: int = 1  # mono
    frame_ms: int = 80  # openWakeWord frame size = 80ms
    audio_device: Optional[int] = Field(default=None, alias="AUDIO_DEVICE_INDEX")

    # --- LiveKit ---
    livekit_url: str = Field(default="", alias="LIVEKIT_URL")
    livekit_api_key: str = Field(default="", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(default="", alias="LIVEKIT_API_SECRET")
    room_name: str = Field(default="champ-ears", alias="EARS_ROOM_NAME")
    participant_identity: str = Field(
        default="ears-listener", alias="EARS_IDENTITY"
    )

    # --- Conversation Lifecycle ---
    silence_timeout_s: float = Field(default=30.0, alias="EARS_SILENCE_TIMEOUT")
    cooldown_s: float = Field(default=2.0, alias="EARS_COOLDOWN")

    # --- Logging ---
    log_level: str = Field(default="DEBUG", alias="CHAMP_LOG_LEVEL")

    model_config = {"env_file": ".env", "extra": "ignore"}


def load_ears_settings() -> EarsSettings:
    return EarsSettings()
