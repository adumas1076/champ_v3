# ============================================
# CHAMP V3 — Memory Seeder Tests
# Brick 6.5: Unit tests for memory_seeder.py
# Run: python -m pytest tests/test_memory_seeder.py -v
# ============================================

import pytest
from unittest.mock import AsyncMock

from mind.memory_seeder import (
    load_extract,
    build_profile_entries,
    build_lesson_entries,
    seed_memory,
    _infer_tags,
)

# ---- Sample extraction data (mirrors real structure) ----
SAMPLE_DATA = {
    "meta": {"extracted": "2026-02-07", "version": "1.0"},
    "stats": {
        "total_conversations": 628,
        "total_messages": 52676,
        "date_range": {"earliest": "2023-01-27", "latest": "2026-02-04"},
    },
    "speech_patterns": {
        "style_markers": {
            "exclamation_rate": 37.4,
            "dash_rate": 54.9,
            "caps_emphasis_rate": 395.5,
        },
        "top_openers": [
            ["got it champ --- ", 46],
            ["top of the morning, champ!", 22],
            ["yes sir, i got you.", 24],
        ],
        "top_phrases": [["let me know", 6254], ["want me to", 3154]],
    },
    "key_conversations": {
        "total_sessions": 598,
        "deepest_sessions": [
            {
                "title": "Create Abundant Creators Headline",
                "date": "2023-02-09",
                "message_count": 1843,
                "first_user_msg": "create a headline for a online school",
                "first_assistant_msg": "Unleash Your Potential",
            },
            {
                "title": "Billy Billing Agent Blueprint",
                "date": "2025-04-12",
                "message_count": 799,
                "first_user_msg": "ok champ we are building Billy the billing agent",
                "first_assistant_msg": "Anthony is building Billy",
            },
            {
                "title": "Genesis Conversation Strategy",
                "date": "2025-01-24",
                "message_count": 722,
                "first_user_msg": "ok lets start to lay the foundation",
                "first_assistant_msg": "Audio check section locked",
            },
            {
                "title": "ElevenLabs Voices Test",
                "date": "2025-04-08",
                "message_count": 624,
                "first_user_msg": "champ i just tested elevn labs agents",
                "first_assistant_msg": "Let's goooo champ!!",
            },
            {
                "title": "AI MODEL FRAMEWORK",
                "date": "2024-09-24",
                "message_count": 656,
                "first_user_msg": "create a hybrid textbase code and python framework",
                "first_assistant_msg": "Let's get it!",
            },
            {
                "title": "Short Chat",
                "date": "2025-01-01",
                "message_count": 50,
                "first_user_msg": "hey",
                "first_assistant_msg": "hey champ",
            },
        ],
    },
    "signature_exchanges": [
        {
            "conversation": "ARIA Overview",
            "user": "dont write any thing what you think?",
            "champ": "I think you're pointed in the right direction",
        },
        {
            "conversation": "ARIA Overview",
            "user": "ok let me see yours here",
            "champ": "Here's mine, Anthony -- rewritten so it lands clean",
        },
        {
            "conversation": "$20 vs $200 Plan",
            "user": "champ i got the 20$ plan what the diffrence",
            "champ": "Anthony -- the $200 Max 20x plan is basically the same Claude",
        },
    ],
    "common_topics": [
        ["genesis conversation strategy", 2],
        ["credit repair workflow design", 2],
        ["a2a with langchain", 3],
        ["photo-realistic ai influencer", 1],
    ],
}


# ---- Test 1: Profile entries include history_depth ----

def test_profile_history_depth():
    """Stats section -> history_depth profile entry."""
    entries = build_profile_entries(SAMPLE_DATA)
    history = [e for e in entries if e["key"] == "history_depth"]
    assert len(history) == 1
    assert "628 conversations" in history[0]["value"]
    assert "52,676 messages" in history[0]["value"]
    assert history[0]["category"] == "meta"


# ---- Test 2: Profile entries include businesses ----

def test_profile_businesses():
    """Key conversations with 'Abundant' and 'Skipper' -> businesses entry."""
    entries = build_profile_entries(SAMPLE_DATA)
    biz = [e for e in entries if e["key"] == "businesses"]
    assert len(biz) == 1
    assert "Abundant Creators" in biz[0]["value"]


# ---- Test 3: Profile entries include tech stack ----

def test_profile_tech_stack():
    """Key conversations referencing tools -> tech_stack entry."""
    entries = build_profile_entries(SAMPLE_DATA)
    tech = [e for e in entries if e["key"] == "tech_stack"]
    assert len(tech) == 1
    assert "Python" in tech[0]["value"]
    assert "ElevenLabs" in tech[0]["value"]


# ---- Test 4: Profile entries include greeting style ----

def test_profile_greeting_style():
    """Top openers with 'champ' -> greeting_style entry."""
    entries = build_profile_entries(SAMPLE_DATA)
    greet = [e for e in entries if e["key"] == "greeting_style"]
    assert len(greet) == 1
    assert "champ" in greet[0]["value"].lower()


# ---- Test 5: Profile entries include agent roster ----

def test_profile_agent_roster():
    """Key conversations with agent names -> agent_roster entry."""
    entries = build_profile_entries(SAMPLE_DATA)
    roster = [e for e in entries if e["key"] == "agent_roster"]
    assert len(roster) == 1
    assert "Billy" in roster[0]["value"]
    assert "Genesis" in roster[0]["value"]


# ---- Test 6: Lessons from deep sessions (100+ msgs) ----

def test_lessons_deep_sessions():
    """Key conversations with 100+ messages -> lesson entries."""
    lessons = build_lesson_entries(SAMPLE_DATA)
    deep = [l for l in lessons if l["lesson"].startswith("Deep session:")]
    # Short Chat (50 msgs) should be excluded
    assert len(deep) == 5
    assert all(l["status"] == "standard" for l in deep)
    # Check times_seen scales with depth
    abundant = [l for l in deep if "Abundant" in l["lesson"]]
    assert abundant[0]["times_seen"] >= 10  # 1843 // 100


# ---- Test 7: Lessons from signature exchanges ----

def test_lessons_voice_patterns():
    """Signature exchanges -> voice pattern lessons."""
    lessons = build_lesson_entries(SAMPLE_DATA)
    voice = [l for l in lessons if "Voice pattern" in l["lesson"]]
    # 2 conversations: ARIA Overview (2 exchanges), $20 vs $200 (1 exchange)
    assert len(voice) == 2
    assert any("voice" in l["tags"] for l in voice)


# ---- Test 8: Lessons from recurring topics ----

def test_lessons_recurring_topics():
    """Common topics with count >= 2 -> lesson entries."""
    lessons = build_lesson_entries(SAMPLE_DATA)
    recurring = [l for l in lessons if "Recurring topic" in l["lesson"]]
    # 3 topics with count >= 2 (photo-realistic has count 1, excluded)
    assert len(recurring) == 3
    # a2a with langchain (count=3) should be "standard"
    langchain = [l for l in recurring if "langchain" in l["lesson"].lower()]
    assert langchain[0]["status"] == "standard"


# ---- Test 9: Tag inference ----

def test_tag_inference():
    """Tag inference from text content."""
    tags = _infer_tags("building a credit repair agent with n8n")
    assert "credit_repair" in tags
    assert "ai_agents" in tags
    assert "n8n" in tags


# ---- Test 10: seed_memory calls memory methods ----


@pytest.mark.asyncio(loop_scope="function")
async def test_seed_memory_calls():
    """seed_memory writes profiles + lessons to memory."""
    memory = AsyncMock()
    memory.upsert_profile = AsyncMock()
    memory.insert_lesson = AsyncMock()

    summary = await seed_memory(memory, SAMPLE_DATA)

    assert summary["profiles"] > 0
    assert summary["lessons"] > 0
    assert memory.upsert_profile.call_count == summary["profiles"]
    assert memory.insert_lesson.call_count == summary["lessons"]
    assert summary["total_conversations_seeded_from"] == 628
