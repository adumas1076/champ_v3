# ============================================
# CHAMP V3 — Letta Memory Manager Unit Tests
# Tests graceful degradation when Letta is not available.
# Run: python -m pytest tests/test_letta_memory.py -v
# ============================================

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mind.letta_memory import LettaMemory, DEFAULT_BLOCKS
from brain.config import Settings


def _run(coro):
    """Helper to run async in sync tests."""
    return asyncio.run(coro)


def test_graceful_degradation_no_url():
    """Should work fine when LETTA_BASE_URL is not set."""
    settings = Settings(
        LITELLM_MASTER_KEY="test-key",
        _env_file=None,
    )
    letta = LettaMemory(settings)
    result = _run(letta.connect())

    assert result is False, "Should return False when no URL configured"
    assert letta.available is False


def test_get_block_when_unavailable():
    """Should return None when Letta is not available."""
    settings = Settings(
        LITELLM_MASTER_KEY="test-key",
        _env_file=None,
    )
    letta = LettaMemory(settings)
    _run(letta.connect())

    block = _run(letta.get_block("persona"))
    assert block is None


def test_update_block_when_unavailable():
    """Should return False when Letta is not available."""
    settings = Settings(
        LITELLM_MASTER_KEY="test-key",
        _env_file=None,
    )
    letta = LettaMemory(settings)
    _run(letta.connect())

    result = _run(letta.update_block("human", "test data"))
    assert result is False


def test_get_all_blocks_when_unavailable():
    """Should return empty string when Letta is not available."""
    settings = Settings(
        LITELLM_MASTER_KEY="test-key",
        _env_file=None,
    )
    letta = LettaMemory(settings)
    _run(letta.connect())

    blocks = _run(letta.get_all_blocks())
    assert blocks == ""


def test_sync_from_supabase_when_unavailable():
    """Should return False when Letta is not available."""
    settings = Settings(
        LITELLM_MASTER_KEY="test-key",
        _env_file=None,
    )
    letta = LettaMemory(settings)
    _run(letta.connect())

    result = _run(letta.sync_from_supabase({"name": "Anthony"}))
    assert result is False


def test_default_blocks_have_all_five():
    """Should have all 5 AIOSCP memory blocks defined."""
    assert "persona" in DEFAULT_BLOCKS
    assert "human" in DEFAULT_BLOCKS
    assert "knowledge" in DEFAULT_BLOCKS
    assert "episodic" in DEFAULT_BLOCKS
    assert "working" in DEFAULT_BLOCKS
    assert len(DEFAULT_BLOCKS) == 5


def test_default_blocks_have_required_fields():
    """Each block should have value, limit, and description."""
    for label, config in DEFAULT_BLOCKS.items():
        assert "value" in config, f"Block '{label}' missing 'value'"
        assert "limit" in config, f"Block '{label}' missing 'limit'"
        assert "description" in config, f"Block '{label}' missing 'description'"
        assert config["limit"] == 5000, f"Block '{label}' should have 5000 char limit"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
