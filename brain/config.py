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
    # Railway sets PORT env var — respect it, fallback to BRAIN_PORT or 8100
    host: str = Field(default="0.0.0.0", alias="BRAIN_HOST")
    port: int = Field(default=8100, alias="PORT")

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
    default_persona: str = "compiled/champ_prompt.md"

    # --- Multi-User ---
    default_user: str = Field(default="anthony", alias="DEFAULT_USER")

    # --- Letta Memory (optional — graceful degradation if not configured) ---
    letta_base_url: str = Field(default="", alias="LETTA_BASE_URL")
    letta_model: str = Field(default="openai/gpt-4o-mini", alias="LETTA_MODEL")
    letta_embedding: str = Field(default="openai/text-embedding-3-small", alias="LETTA_EMBEDDING")

    # --- Mem0 Global Memory (optional — graceful degradation if not configured) ---
    mem0_enabled: bool = Field(default=False, alias="MEM0_ENABLED")
    mem0_llm_provider: str = Field(default="", alias="MEM0_LLM_PROVIDER")
    mem0_llm_model: str = Field(default="", alias="MEM0_LLM_MODEL")
    mem0_embedder_provider: str = Field(default="", alias="MEM0_EMBEDDER_PROVIDER")
    mem0_embedder_model: str = Field(default="", alias="MEM0_EMBEDDER_MODEL")
    mem0_vector_store: str = Field(default="", alias="MEM0_VECTOR_STORE")

    # --- Ears Sidecar ---
    ears_health_url: str = Field(
        default="http://127.0.0.1:8101/health", alias="EARS_HEALTH_URL"
    )

    # --- Logging ---
    log_level: str = Field(default="DEBUG", alias="CHAMP_LOG_LEVEL")

    model_config = {"env_file": ".env", "extra": "ignore"}


def load_settings() -> Settings:
    return Settings()