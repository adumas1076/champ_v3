# ============================================
# CHAMP V3 — Learning Loop Tests
# Brick 6 Step 2: Unit tests with mocked deps
# Run: python -m pytest tests/test_learning.py -v
# ============================================

import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")

from mind.learning import LearningLoop


@pytest.fixture
def settings():
    """Mock Settings object."""
    s = MagicMock()
    s.litellm_base_url = "http://127.0.0.1:4000/v1"
    s.litellm_api_key = "test-key"
    s.default_model = "claude-sonnet"
    return s


@pytest.fixture
def memory():
    """Mock SupabaseMemory with async methods."""
    m = AsyncMock()
    m.get_recent_messages = AsyncMock(return_value=[])
    m.upsert_profile = AsyncMock()
    m.increment_lesson = AsyncMock()
    m.insert_lesson = AsyncMock()
    return m


@pytest.fixture
def loop(settings):
    return LearningLoop(settings)


def _make_messages(count: int) -> list[dict]:
    """Generate a fake transcript with N messages."""
    msgs = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"Message {i}"})
    return msgs


def _mock_llm_response(extraction: dict):
    """Create a mock requests.Response with extraction JSON."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [
            {"message": {"content": json.dumps(extraction)}}
        ]
    }
    return resp


# ---- Test 1: Skip short transcripts ----

async def test_skip_short_transcript(loop, memory):
    """< 3 messages → capture returns early, no LLM call."""
    memory.get_recent_messages.return_value = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hey"},
    ]

    with patch("mind.learning.requests.post") as mock_post:
        await loop.capture("conv-123", memory)
        mock_post.assert_not_called()


# ---- Test 2: Extraction prompt sent to LLM ----

async def test_extraction_prompt_sent(loop, memory):
    """Verify LLM gets called with transcript in prompt."""
    memory.get_recent_messages.return_value = _make_messages(6)

    extraction = {
        "profile_updates": [],
        "lesson_matches": [],
        "new_lessons": [],
    }

    with patch("mind.learning.requests.post") as mock_post:
        mock_post.return_value = _mock_llm_response(extraction)
        await loop.capture("conv-123", memory)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        prompt_content = payload["messages"][0]["content"]
        assert "Message 0" in prompt_content
        assert "Message 5" in prompt_content


# ---- Test 3: Profile upsert ----

async def test_profile_upsert(loop, memory):
    """Mock LLM returns profile_updates → verify upsert called."""
    memory.get_recent_messages.return_value = _make_messages(6)

    extraction = {
        "profile_updates": [
            {"key": "preferred_theme", "value": "dark mode", "category": "ui", "confidence": "high"}
        ],
        "lesson_matches": [],
        "new_lessons": [],
    }

    with patch("mind.learning.requests.post") as mock_post:
        mock_post.return_value = _mock_llm_response(extraction)
        await loop.capture("conv-123", memory)

        memory.upsert_profile.assert_called_once_with(
            user_id="anthony",
            key="preferred_theme",
            value="dark mode",
            category="ui",
            confidence="high",
        )


# ---- Test 4: Lesson increment ----

async def test_lesson_increment(loop, memory):
    """Mock existing lesson match → verify increment called."""
    memory.get_recent_messages.return_value = _make_messages(6)

    extraction = {
        "profile_updates": [],
        "lesson_matches": ["brick wall approach", "Dr. Frankenstein method"],
        "new_lessons": [],
    }

    with patch("mind.learning.requests.post") as mock_post:
        mock_post.return_value = _mock_llm_response(extraction)
        await loop.capture("conv-123", memory)

        assert memory.increment_lesson.call_count == 2
        memory.increment_lesson.assert_any_call(
            user_id="anthony", lesson_substring="brick wall approach"
        )
        memory.increment_lesson.assert_any_call(
            user_id="anthony", lesson_substring="Dr. Frankenstein method"
        )


# ---- Test 5: New lesson insert ----

async def test_new_lesson_insert(loop, memory):
    """Mock new lesson → verify insert with status=draft."""
    memory.get_recent_messages.return_value = _make_messages(6)

    extraction = {
        "profile_updates": [],
        "lesson_matches": [],
        "new_lessons": [
            {"lesson": "User prefers Puppeteer over Playwright", "tags": ["tools", "browser"]}
        ],
    }

    with patch("mind.learning.requests.post") as mock_post:
        mock_post.return_value = _mock_llm_response(extraction)
        await loop.capture("conv-123", memory)

        memory.insert_lesson.assert_called_once_with(
            user_id="anthony",
            lesson="User prefers Puppeteer over Playwright",
            tags=["tools", "browser"],
        )
