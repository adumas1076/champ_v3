# ============================================
# CHAMP V3 — Persona Loader Unit Tests
# Run: python -m pytest tests/test_persona_loader.py -v
# ============================================

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brain.persona_loader import PersonaLoader, FALLBACK_PERSONA
from brain.config import Settings


def _run(coro):
    """Helper to run async in sync tests."""
    return asyncio.run(coro)


def test_loads_persona_from_file():
    """Should load the real persona file."""
    settings = Settings(
        LITELLM_MASTER_KEY="test-key",
        _env_file=None,
    )
    loader = PersonaLoader(settings)
    _run(loader.load())

    persona = loader.get_persona()
    assert len(persona) > 1000, "Persona should be substantial"
    assert "Champ" in persona, "Should contain Champ identity"
    assert "Built in the dark" in persona


def test_fallback_when_file_missing():
    """Should use fallback persona when file doesn't exist."""
    settings = Settings(
        LITELLM_MASTER_KEY="test-key",
        _env_file=None,
    )
    settings.default_persona = "nonexistent_persona.md"
    loader = PersonaLoader(settings)
    _run(loader.load())

    persona = loader.get_persona()
    # Fallback persona is the base; memory_*.md blocks may also be appended
    assert persona.startswith(FALLBACK_PERSONA), "Should start with fallback persona"
    assert "Champ" in persona


def test_reload():
    """Should reload persona from disk."""
    async def _test():
        settings = Settings(
            LITELLM_MASTER_KEY="test-key",
            _env_file=None,
        )
        loader = PersonaLoader(settings)
        await loader.load()
        original = loader.get_persona()
        await loader.reload()
        reloaded = loader.get_persona()
        assert original == reloaded, "Reload should produce same content"

    asyncio.run(_test())


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])