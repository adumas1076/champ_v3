# ============================================
# CHAMP V3 — Brain Configuration
# All settings loaded from environment variables
# ============================================

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Brain layer configuration. Loaded from .env."""

    # --- Brain Server ---
    host: str = Field(default="0.0.0.0", alias="BRAIN_HOST")
    port: int = Field(default=8100, alias="BRAIN_PORT")

    # --- LiteLLM upstream (port 4000) ---
    litellm_base_url: str = Field(
        default="http://127.0.0.1:4000/v1", alias="LITELLM_BASE_URL"
    )
    litellm_api_key: str = Field(alias="LITELLM_MASTER_KEY")
    default_model: str = "claude-sonnet"

    # --- Supabase Memory ---
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")

    # --- Persona ---
    persona_dir: Path = Path(__file__).resolve().parent.parent / "persona"
    default_persona: str = "champ_persona_v1.6.1.md"

    # --- Logging ---
    log_level: str = Field(default="DEBUG", alias="CHAMP_LOG_LEVEL")

    model_config = {"env_file": ".env", "extra": "ignore"}


def load_settings() -> Settings:
    return Settings()