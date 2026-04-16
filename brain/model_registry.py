# ============================================
# CHAMP V3 — Model Registry
# Dynamic model metadata lookup.
#
# Inspired by Hermes-Agent models_dev.py:
#   Fetches model metadata (context lengths, costs,
#   capabilities) from models.dev API with caching.
#   No more hardcoded max_tokens for everything.
#
# Usage:
#   registry = ModelRegistry()
#   info = await registry.get_model_info("claude-sonnet")
#   context_limit = info.context_window  # 200000
#   cost = info.input_cost_per_m        # 3.00
# ============================================

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cache TTL: 1 hour in-memory, disk cache persists across restarts
CACHE_TTL_SECONDS = 3600
DISK_CACHE_PATH = Path(__file__).resolve().parent.parent / ".model_cache.json"


@dataclass
class ModelInfo:
    """Metadata for a single model."""
    name: str                           # LiteLLM model_name (e.g., "claude-sonnet")
    provider: str = ""                  # Provider name (e.g., "anthropic")
    context_window: int = 128_000       # Max input tokens
    max_output_tokens: int = 4096       # Max output tokens
    input_cost_per_m: float = 0.0       # Cost per 1M input tokens (USD)
    output_cost_per_m: float = 0.0      # Cost per 1M output tokens (USD)
    supports_vision: bool = False       # Can handle image inputs
    supports_tools: bool = True         # Can handle function calling
    supports_streaming: bool = True     # Supports SSE streaming


# ============================================
# Built-in Registry (fallback when API unavailable)
# ============================================
# These match litellm_config.yaml model_names.
# Updated manually when models change.

BUILTIN_MODELS: dict[str, ModelInfo] = {
    "claude-sonnet": ModelInfo(
        name="claude-sonnet",
        provider="anthropic",
        context_window=200_000,
        max_output_tokens=8192,
        input_cost_per_m=3.00,
        output_cost_per_m=15.00,
        supports_vision=True,
    ),
    "claude-haiku": ModelInfo(
        name="claude-haiku",
        provider="anthropic",
        context_window=200_000,
        max_output_tokens=4096,
        input_cost_per_m=1.00,
        output_cost_per_m=5.00,
        supports_vision=True,
    ),
    "gpt-4o": ModelInfo(
        name="gpt-4o",
        provider="openai",
        context_window=128_000,
        max_output_tokens=4096,
        input_cost_per_m=2.50,
        output_cost_per_m=10.00,
        supports_vision=True,
    ),
    "gemini-flash": ModelInfo(
        name="gemini-flash",
        provider="google",
        context_window=1_000_000,
        max_output_tokens=8192,
        input_cost_per_m=0.10,
        output_cost_per_m=0.40,
        supports_vision=True,
    ),
    "gemini-flash-volume": ModelInfo(
        name="gemini-flash-volume",
        provider="google",
        context_window=1_000_000,
        max_output_tokens=8192,
        input_cost_per_m=0.075,
        output_cost_per_m=0.30,
        supports_vision=True,
    ),
    "grok-mini": ModelInfo(
        name="grok-mini",
        provider="xai",
        context_window=131_072,
        max_output_tokens=4096,
        input_cost_per_m=0.30,
        output_cost_per_m=0.50,
        supports_vision=False,
    ),
    "llama-groq": ModelInfo(
        name="llama-groq",
        provider="groq",
        context_window=131_072,
        max_output_tokens=2048,
        input_cost_per_m=0.05,
        output_cost_per_m=0.08,
        supports_vision=False,
    ),
    "local": ModelInfo(
        name="local",
        provider="ollama",
        context_window=32_768,
        max_output_tokens=4096,
        input_cost_per_m=0.0,
        output_cost_per_m=0.0,
        supports_vision=False,
    ),
    "local-small": ModelInfo(
        name="local-small",
        provider="ollama",
        context_window=16_384,
        max_output_tokens=2048,
        input_cost_per_m=0.0,
        output_cost_per_m=0.0,
        supports_vision=False,
    ),
}


class ModelRegistry:
    """
    Dynamic model metadata registry with caching.

    Provides model info (context windows, costs, capabilities)
    used by the cortex router and context builder.

    Falls back to built-in registry if external lookup unavailable.
    Future: fetch from models.dev API (Hermes pattern).
    """

    def __init__(self):
        self._cache: dict[str, ModelInfo] = {}
        self._cache_timestamp: float = 0.0
        self._load_disk_cache()

    def get(self, model_name: str) -> ModelInfo:
        """Get model info by LiteLLM model_name. Synchronous."""
        # Check in-memory cache first
        if model_name in self._cache and not self._cache_expired():
            return self._cache[model_name]

        # Check built-in registry
        if model_name in BUILTIN_MODELS:
            info = BUILTIN_MODELS[model_name]
            self._cache[model_name] = info
            return info

        # Unknown model — return safe defaults
        logger.warning(f"[REGISTRY] Unknown model '{model_name}', using defaults")
        return ModelInfo(name=model_name)

    def get_context_window(self, model_name: str) -> int:
        """Shortcut: get context window for a model."""
        return self.get(model_name).context_window

    def get_max_output(self, model_name: str) -> int:
        """Shortcut: get max output tokens for a model."""
        return self.get(model_name).max_output_tokens

    def estimate_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a request."""
        info = self.get(model_name)
        return (
            input_tokens * info.input_cost_per_m
            + output_tokens * info.output_cost_per_m
        ) / 1_000_000

    def list_models(self) -> list[str]:
        """List all known model names."""
        return list(BUILTIN_MODELS.keys())

    def supports_vision(self, model_name: str) -> bool:
        """Check if model supports image inputs."""
        return self.get(model_name).supports_vision

    # ---- Cache Management ----

    def _cache_expired(self) -> bool:
        return (time.time() - self._cache_timestamp) > CACHE_TTL_SECONDS

    def _load_disk_cache(self) -> None:
        """Load cached model info from disk (survives restarts)."""
        if not DISK_CACHE_PATH.exists():
            return
        try:
            data = json.loads(DISK_CACHE_PATH.read_text())
            for name, info_dict in data.get("models", {}).items():
                self._cache[name] = ModelInfo(**info_dict)
            self._cache_timestamp = data.get("timestamp", 0.0)
            logger.debug(f"[REGISTRY] Loaded {len(self._cache)} models from disk cache")
        except Exception as e:
            logger.warning(f"[REGISTRY] Failed to load disk cache: {e}")

    def _save_disk_cache(self) -> None:
        """Persist cache to disk."""
        try:
            data = {
                "timestamp": time.time(),
                "models": {
                    name: {
                        "name": info.name,
                        "provider": info.provider,
                        "context_window": info.context_window,
                        "max_output_tokens": info.max_output_tokens,
                        "input_cost_per_m": info.input_cost_per_m,
                        "output_cost_per_m": info.output_cost_per_m,
                        "supports_vision": info.supports_vision,
                        "supports_tools": info.supports_tools,
                        "supports_streaming": info.supports_streaming,
                    }
                    for name, info in self._cache.items()
                },
            }
            DISK_CACHE_PATH.write_text(json.dumps(data, indent=2))
            logger.debug(f"[REGISTRY] Saved {len(self._cache)} models to disk cache")
        except Exception as e:
            logger.warning(f"[REGISTRY] Failed to save disk cache: {e}")


# Singleton instance
_registry: Optional[ModelRegistry] = None


def get_registry() -> ModelRegistry:
    """Get the global model registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
