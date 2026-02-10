# ============================================
# CHAMP V3 — Memory Seeder
# Brick 6.5: Seeds Supabase memory tables from
# champ_memory_extract.json — gives Champ his
# foundational memory from 628 ChatGPT sessions.
#
# Run: python -m mind.memory_seeder
# ============================================
# "Built to build. Born to create."

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to the extraction file
EXTRACT_PATH = Path(__file__).parent.parent / "brain" / "champ_memory_extract.json"


def load_extract(path: Path = EXTRACT_PATH) -> dict:
    """Load the ChatGPT memory extraction JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_profile_entries(data: dict) -> list[dict]:
    """
    Parse extraction data into mem_profile entries.

    Pulls from: stats, speech_patterns, key_conversations, common_topics.
    Returns list of {key, value, category, confidence} dicts.
    """
    entries = []

    # ---- Stats / Meta ----
    stats = data.get("stats", {})
    if stats:
        entries.append({
            "key": "history_depth",
            "value": (
                f"{stats.get('total_conversations', 0)} conversations, "
                f"{stats.get('total_messages', 0):,} messages since "
                f"{stats.get('date_range', {}).get('earliest', 'unknown')}"
            ),
            "category": "meta",
            "confidence": "high",
        })

    # ---- Business identity (from key conversations) ----
    key_convos = data.get("key_conversations", {}).get("deepest_sessions", [])
    titles = [c.get("title", "") for c in key_convos]

    # Extract business names from conversation titles
    businesses = []
    if any("Abundant" in t for t in titles):
        businesses.append("Abundant Creators")
        businesses.append("Abundant Growth Solutions")
    if any("Skipper" in t or "skip the line" in t.lower() for t in titles):
        businesses.append("Line Skippers / Skipper Financial")

    if businesses:
        entries.append({
            "key": "businesses",
            "value": ", ".join(businesses),
            "category": "business",
            "confidence": "high",
        })

    # ---- Tech stack (from key conversation topics) ----
    tech_signals = {
        "n8n": False, "VAPI": False, "LiveKit": False,
        "Python": False, "Claude": False, "GoHighLevel": False,
        "Supabase": False, "ElevenLabs": False, "HeyGen": False,
        "Stripe": False, "Langchain": False,
    }
    all_text = json.dumps(key_convos).lower()
    for tech in tech_signals:
        if tech.lower() in all_text:
            tech_signals[tech] = True

    active_tech = [k for k, v in tech_signals.items() if v]
    if active_tech:
        entries.append({
            "key": "tech_stack",
            "value": ", ".join(active_tech),
            "category": "tech",
            "confidence": "high",
        })

    # ---- Greeting style (from speech patterns) ----
    top_openers = data.get("speech_patterns", {}).get("top_openers", [])
    greetings = []
    for opener, count in top_openers:
        lower = opener.lower()
        if any(g in lower for g in ["top of the morning", "got it champ", "got you champ", "yes sir"]):
            greetings.append(f"{opener} ({count}x)")
    if greetings:
        entries.append({
            "key": "greeting_style",
            "value": "; ".join(greetings[:5]),
            "category": "communication",
            "confidence": "high",
        })

    # ---- Build approach (from key conversations) ----
    build_signals = []
    for convo in key_convos:
        title = convo.get("title", "")
        first_msg = convo.get("first_user_msg", "")
        if any(kw in title.lower() or kw in first_msg.lower()
               for kw in ["framework", "core", "foundation", "design", "blueprint"]):
            build_signals.append(title)
    if build_signals:
        entries.append({
            "key": "build_approach",
            "value": "Brick wall method: one piece at a time, test each before moving on. Key builds: " + ", ".join(build_signals[:5]),
            "category": "workflow",
            "confidence": "high",
        })

    # ---- Core interests (from common_topics) ----
    common_topics = data.get("common_topics", [])
    if common_topics:
        top_topics = [t[0] for t in common_topics[:15]]
        entries.append({
            "key": "interests",
            "value": ", ".join(top_topics),
            "category": "interests",
            "confidence": "high",
        })

    # ---- Agent roster (from key conversations + signature exchanges + topics) ----
    agents = set()
    agent_names = {
        "genesis": "Genesis (credit guide / onboarding)",
        "billy": "Billy (billing agent)",
        "sam": "Sam (qualifier agent)",
        "aria": "ARIA (orchestration layer)",
        "elly": "Elly (eBay voice agent)",
    }
    # Scan key conversations
    for convo in key_convos:
        combined = (convo.get("title", "") + " " + convo.get("first_user_msg", "")).lower()
        for name, desc in agent_names.items():
            if name in combined:
                agents.add(desc)
    # Scan signature exchanges
    for ex in data.get("signature_exchanges", []):
        combined = (ex.get("conversation", "") + " " + ex.get("user", "")).lower()
        for name, desc in agent_names.items():
            if name in combined:
                agents.add(desc)
    # Scan common topics
    for topic, _ in data.get("common_topics", []):
        for name, desc in agent_names.items():
            if name in topic.lower():
                agents.add(desc)
    if agents:
        entries.append({
            "key": "agent_roster",
            "value": ", ".join(sorted(agents)),
            "category": "agents",
            "confidence": "high",
        })

    # ---- Communication style (from speech_patterns) ----
    style = data.get("speech_patterns", {}).get("style_markers", {})
    if style:
        entries.append({
            "key": "communication_style",
            "value": (
                f"High energy: {style.get('exclamation_rate', 0)}% exclamations, "
                f"{style.get('caps_emphasis_rate', 0)} caps-emphasis per 1K msgs, "
                f"{style.get('dash_rate', 0)}% dashes for pacing"
            ),
            "category": "communication",
            "confidence": "high",
        })

    return entries


def build_lesson_entries(data: dict) -> list[dict]:
    """
    Parse extraction data into mem_lessons entries.

    Pulls from: key_conversations (project patterns),
    signature_exchanges (voice/style), common_topics (recurring work).
    Returns list of {lesson, tags, status, times_seen} dicts.
    """
    lessons = []

    # ---- Key project patterns (from deepest sessions) ----
    key_convos = data.get("key_conversations", {}).get("deepest_sessions", [])
    for convo in key_convos:
        title = convo.get("title", "")
        msg_count = convo.get("message_count", 0)
        date = convo.get("date", "")
        first_user = convo.get("first_user_msg", "")[:200]

        # Only create lessons for deep sessions (100+ messages)
        if msg_count >= 100:
            lesson_text = (
                f"Deep session: '{title}' ({date}, {msg_count} msgs). "
                f"Anthony's opener: \"{first_user}\""
            )
            # Tag based on content
            tags = _infer_tags(title + " " + first_user)
            lessons.append({
                "lesson": lesson_text,
                "tags": tags,
                "status": "standard",
                "times_seen": max(1, msg_count // 100),
            })

    # ---- Signature voice patterns (from exchanges) ----
    exchanges = data.get("signature_exchanges", [])
    # Group by conversation
    convo_groups = {}
    for ex in exchanges:
        conv_name = ex.get("conversation", "")
        if conv_name not in convo_groups:
            convo_groups[conv_name] = []
        convo_groups[conv_name].append(ex)

    for conv_name, exs in convo_groups.items():
        # Create a single lesson per conversation group showing the voice pattern
        sample_user = exs[0].get("user", "")[:100]
        sample_champ = exs[0].get("champ", "")[:200]
        lesson_text = (
            f"Voice pattern from '{conv_name}': "
            f"Anthony says: \"{sample_user}\" -> "
            f"Champ responds: \"{sample_champ}\""
        )
        lessons.append({
            "lesson": lesson_text,
            "tags": ["voice", "style", conv_name.lower().replace(" ", "_")],
            "status": "standard",
            "times_seen": len(exs),
        })

    # ---- Recurring topic lessons ----
    common_topics = data.get("common_topics", [])
    for topic, count in common_topics:
        if count >= 2:  # Only seed recurring topics
            lessons.append({
                "lesson": f"Recurring topic: {topic} (appeared in {count} conversations)",
                "tags": ["recurring", "topic"],
                "status": "draft" if count < 3 else "standard",
                "times_seen": count,
            })

    return lessons


def _infer_tags(text: str) -> list[str]:
    """Infer tags from text content."""
    tags = []
    text_lower = text.lower()

    tag_map = {
        "credit": "credit_repair",
        "agent": "ai_agents",
        "n8n": "n8n",
        "vapi": "voice_ai",
        "livekit": "voice_ai",
        "billing": "billing",
        "genesis": "genesis",
        "landing page": "marketing",
        "vsl": "marketing",
        "webinar": "marketing",
        "social media": "marketing",
        "abundant": "abundant_creators",
        "framework": "architecture",
        "python": "python",
        "automation": "automation",
        "influencer": "ai_influencer",
        "heygen": "heygen",
        "workflow": "automation",
        "stripe": "payments",
        "slack": "integrations",
        "film": "creative",
    }

    for keyword, tag in tag_map.items():
        if keyword in text_lower and tag not in tags:
            tags.append(tag)

    return tags if tags else ["general"]


async def seed_memory(memory, data: dict = None) -> dict:
    """
    Seed Supabase memory tables from extraction data.

    Args:
        memory: SupabaseMemory instance (already connected)
        data: Optional pre-loaded extraction dict. If None, loads from file.

    Returns:
        Summary dict with counts: {profiles, lessons}
    """
    if data is None:
        data = load_extract()

    profile_entries = build_profile_entries(data)
    lesson_entries = build_lesson_entries(data)

    # Write profiles
    profile_count = 0
    for entry in profile_entries:
        try:
            await memory.upsert_profile(
                user_id="anthony",
                key=entry["key"],
                value=entry["value"],
                category=entry["category"],
                confidence=entry["confidence"],
            )
            profile_count += 1
        except Exception as e:
            logger.error(f"Seed profile failed for {entry['key']}: {e}")

    # Write lessons
    lesson_count = 0
    for entry in lesson_entries:
        try:
            await memory.insert_lesson(
                user_id="anthony",
                lesson=entry["lesson"],
                tags=entry["tags"],
            )
            # Update status and times_seen if not draft defaults
            # (insert_lesson defaults to draft/1, so we may need to update)
            lesson_count += 1
        except Exception as e:
            logger.error(f"Seed lesson failed: {e}")

    summary = {
        "profiles": profile_count,
        "lessons": lesson_count,
        "total_conversations_seeded_from": data.get("stats", {}).get("total_conversations", 0),
    }

    logger.info(
        f"Memory seeded: {profile_count} profile entries, "
        f"{lesson_count} lessons from "
        f"{summary['total_conversations_seeded_from']} conversations"
    )

    return summary


# ---- CLI entry point ----
if __name__ == "__main__":
    import asyncio
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    async def main():
        print("=" * 60)
        print("CHAMP V3 -- MEMORY SEEDER")
        print("Seeding foundational memory from 628 ChatGPT sessions")
        print("=" * 60)

        # Load config
        from brain.config import load_settings
        from brain.memory import SupabaseMemory

        settings = load_settings()
        memory = SupabaseMemory(settings)
        await memory.connect()

        if not memory._client:
            print("\nFAILED: Could not connect to Supabase")
            print("Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
            return 1

        # Load and seed
        data = load_extract()
        print(f"\nLoaded extraction: {data['stats']['total_conversations']} conversations, "
              f"{data['stats']['total_messages']:,} messages")

        summary = await seed_memory(memory, data)

        print(f"\nSeeded: {summary['profiles']} profile entries")
        print(f"Seeded: {summary['lessons']} lessons")
        print("\n" + "=" * 60)
        print("MEMORY SEEDED. Champ now remembers his history.")
        print("=" * 60)

        await memory.disconnect()
        return 0

    sys.exit(asyncio.run(main()))
