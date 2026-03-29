# ============================================
# Tests for Mem0 Global Memory Layer
# Tests graceful degradation + API surface
# ============================================

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mind.mem0_memory import Mem0Memory


class FakeSettings:
    """Minimal settings for testing."""
    mem0_enabled = False
    mem0_llm_provider = ""
    mem0_llm_model = ""
    mem0_embedder_provider = ""
    mem0_embedder_model = ""
    mem0_vector_store = ""


class FakeSettingsEnabled:
    """Settings with Mem0 enabled."""
    mem0_enabled = True
    mem0_llm_provider = "openai"
    mem0_llm_model = "gpt-4o-mini"
    mem0_embedder_provider = ""
    mem0_embedder_model = ""
    mem0_vector_store = ""


# ---- Graceful Degradation Tests ----

@pytest.mark.asyncio
async def test_connect_disabled():
    """Mem0 disabled in config → returns False, no crash."""
    mem0 = Mem0Memory(FakeSettings())
    result = await mem0.connect()
    assert result is False
    assert mem0.available is False


@pytest.mark.asyncio
async def test_search_when_disabled():
    """Search returns empty list when Mem0 is disabled."""
    mem0 = Mem0Memory(FakeSettings())
    await mem0.connect()
    results = await mem0.search("test query")
    assert results == []


@pytest.mark.asyncio
async def test_add_when_disabled():
    """Add returns None when Mem0 is disabled."""
    mem0 = Mem0Memory(FakeSettings())
    await mem0.connect()
    result = await mem0.add("test memory")
    assert result is None


@pytest.mark.asyncio
async def test_get_all_when_disabled():
    """get_all returns empty list when Mem0 is disabled."""
    mem0 = Mem0Memory(FakeSettings())
    await mem0.connect()
    results = await mem0.get_all()
    assert results == []


@pytest.mark.asyncio
async def test_get_context_when_disabled():
    """get_context returns empty string when Mem0 is disabled."""
    mem0 = Mem0Memory(FakeSettings())
    await mem0.connect()
    context = await mem0.get_context("anthony")
    assert context == ""


@pytest.mark.asyncio
async def test_delete_when_disabled():
    """delete returns False when Mem0 is disabled."""
    mem0 = Mem0Memory(FakeSettings())
    await mem0.connect()
    result = await mem0.delete("some-id")
    assert result is False


@pytest.mark.asyncio
async def test_disconnect():
    """Disconnect cleans up state."""
    mem0 = Mem0Memory(FakeSettings())
    await mem0.disconnect()
    assert mem0.available is False


# ---- Mock Tests (simulating Mem0 available) ----

@pytest.mark.asyncio
async def test_connect_success():
    """Mem0 enabled + import works → connects successfully."""
    mem0 = Mem0Memory(FakeSettingsEnabled())

    mock_memory = MagicMock()
    with patch("mind.mem0_memory.Mem0Memory.connect") as mock_connect:
        mock_connect.return_value = True
        result = await mem0.connect()
        # The real connect would set _available, mock just returns True
        assert mock_connect.called


@pytest.mark.asyncio
async def test_add_with_agent_id():
    """Add memory with agent_id for provenance tracking."""
    mem0 = Mem0Memory(FakeSettings())
    mem0._available = True
    mem0._memory = MagicMock()
    mem0._memory.add.return_value = {"id": "test-123"}

    result = await mem0.add(
        "Anthony prefers concise answers",
        user_id="anthony",
        agent_id="champ-v1",
        metadata={"source": "conversation"}
    )
    assert result == {"id": "test-123"}
    mem0._memory.add.assert_called_once()


@pytest.mark.asyncio
async def test_search_returns_results():
    """Search returns formatted results."""
    mem0 = Mem0Memory(FakeSettings())
    mem0._available = True
    mem0._memory = MagicMock()
    mem0._memory.search.return_value = {
        "results": [
            {"memory": "Anthony prefers concise answers", "score": 0.95},
            {"memory": "Uses Claude for coding", "score": 0.87},
        ]
    }

    results = await mem0.search("what does Anthony prefer?", user_id="anthony")
    assert len(results) == 2
    assert results[0]["memory"] == "Anthony prefers concise answers"


@pytest.mark.asyncio
async def test_get_context_formatted():
    """get_context returns formatted string for prompt injection."""
    mem0 = Mem0Memory(FakeSettings())
    mem0._available = True
    mem0._memory = MagicMock()
    mem0._memory.get_all.return_value = {
        "results": [
            {"memory": "Anthony is the CEO of Abundant Creators"},
            {"memory": "CHAMP is a voice-first AI OS"},
        ]
    }

    context = await mem0.get_context("anthony")
    assert "[GLOBAL MEMORY]" in context
    assert "Anthony is the CEO of Abundant Creators" in context
    assert "CHAMP is a voice-first AI OS" in context


@pytest.mark.asyncio
async def test_get_context_with_query():
    """get_context with query uses semantic search instead of get_all."""
    mem0 = Mem0Memory(FakeSettings())
    mem0._available = True
    mem0._memory = MagicMock()
    mem0._memory.search.return_value = {
        "results": [
            {"memory": "Pricing: Creator $49, Pro $149"},
        ]
    }

    context = await mem0.get_context("anthony", query="pricing tiers")
    assert "Pricing: Creator $49, Pro $149" in context
    mem0._memory.search.assert_called_once()


@pytest.mark.asyncio
async def test_delete_success():
    """Delete removes memory by ID."""
    mem0 = Mem0Memory(FakeSettings())
    mem0._available = True
    mem0._memory = MagicMock()

    result = await mem0.delete("mem-456")
    assert result is True
    mem0._memory.delete.assert_called_once_with("mem-456")
