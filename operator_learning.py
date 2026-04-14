# ============================================
# Cocreatiq V1 — Self-Improving Learning Loop
# Operators get better every session
# Pattern: Hermes skill creation + CHAMP learning loop
# ============================================

import logging
import os
import json
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def extract_lessons_from_transcript(transcript_text: str, operator_name: str) -> list[dict]:
    """
    Analyze a transcript and extract reusable lessons.
    Called at session end. Returns list of lessons to store.
    """
    try:
        import requests
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or not transcript_text or len(transcript_text) < 50:
            return []

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": f"""Analyze this voice conversation transcript for operator '{operator_name}'.
Extract reusable lessons — patterns that should be remembered for future sessions.

Return ONLY valid JSON array. Each lesson has:
- "lesson": one sentence describing the pattern
- "category": one of (communication, technical, workflow, preference, error)
- "confidence": number 0.0-1.0 how confident this pattern is real

Only extract lessons that would genuinely help in future conversations. Skip generic observations.
Max 3 lessons per transcript. If nothing worth learning, return empty array [].
No markdown, no code blocks, just raw JSON array."""},
                    {"role": "user", "content": transcript_text}
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            },
            timeout=15,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content
            content = content.rsplit("```", 1)[0] if "```" in content else content

        lessons = json.loads(content.strip())
        if not isinstance(lessons, list):
            return []

        logger.info(f"[LEARNING] Extracted {len(lessons)} lessons from transcript")
        return lessons

    except Exception as e:
        logger.warning(f"[LEARNING] Lesson extraction failed (non-fatal): {e}")
        return []


def store_lessons(supabase_client, operator_name: str, user_id: str, lessons: list[dict]) -> int:
    """Store extracted lessons in mem_lessons table."""
    if not supabase_client or not lessons:
        return 0

    stored = 0
    for lesson in lessons:
        try:
            supabase_client.table("mem_lessons").insert({
                "user_id": user_id,
                "operator_name": operator_name,
                "lesson": lesson.get("lesson", ""),
                "tags": [lesson.get("category", "general"), "auto_extracted"],
                "status": "draft",
                "times_seen": 1,
                "tier": "warm",
            }).execute()
            stored += 1
        except Exception as e:
            logger.warning(f"[LEARNING] Failed to store lesson: {e}")

    logger.info(f"[LEARNING] Stored {stored}/{len(lessons)} lessons for {operator_name}")
    return stored


def promote_recurring_lessons(supabase_client, operator_name: str, threshold: int = 3) -> int:
    """Promote draft lessons to standard after they've been seen enough times."""
    if not supabase_client:
        return 0

    try:
        # Find draft lessons seen >= threshold times
        result = supabase_client.table("mem_lessons").select("id, lesson, times_seen").eq(
            "operator_name", operator_name
        ).eq("status", "draft").gte("times_seen", threshold).execute()

        if not result.data:
            return 0

        promoted = 0
        for lesson in result.data:
            supabase_client.table("mem_lessons").update({
                "status": "standard",
                "tier": "hot",
            }).eq("id", lesson["id"]).execute()
            promoted += 1
            logger.info(f"[LEARNING] Promoted lesson: {lesson['lesson'][:50]}... (seen {lesson['times_seen']}x)")

        return promoted

    except Exception as e:
        logger.warning(f"[LEARNING] Promotion failed: {e}")
        return 0


def check_duplicate_lesson(supabase_client, operator_name: str, new_lesson: str) -> Optional[str]:
    """Check if a similar lesson already exists. Returns existing lesson ID if found."""
    if not supabase_client:
        return None

    try:
        result = supabase_client.table("mem_lessons").select("id, lesson, times_seen").eq(
            "operator_name", operator_name
        ).execute()

        if not result.data:
            return None

        # Simple keyword overlap check
        new_words = set(new_lesson.lower().split())
        for existing in result.data:
            existing_words = set(existing["lesson"].lower().split())
            overlap = len(new_words & existing_words) / max(len(new_words), 1)
            if overlap > 0.6:
                # Increment times_seen instead of creating duplicate
                supabase_client.table("mem_lessons").update({
                    "times_seen": existing["times_seen"] + 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", existing["id"]).execute()
                logger.debug(f"[LEARNING] Duplicate found, incremented: {existing['lesson'][:50]}...")
                return existing["id"]

        return None

    except Exception as e:
        logger.warning(f"[LEARNING] Duplicate check failed: {e}")
        return None


def run_learning_loop(supabase_client, operator_name: str, user_id: str, transcript_text: str) -> dict:
    """
    Full learning loop — runs at session end.
    1. Extract lessons from transcript
    2. Deduplicate against existing
    3. Store new lessons
    4. Promote recurring patterns
    """
    results = {"extracted": 0, "stored": 0, "duplicates": 0, "promoted": 0}

    # 1. Extract
    lessons = extract_lessons_from_transcript(transcript_text, operator_name)
    results["extracted"] = len(lessons)

    if not lessons:
        return results

    # 2. Deduplicate + Store
    for lesson in lessons:
        lesson_text = lesson.get("lesson", "")
        if not lesson_text:
            continue

        existing_id = check_duplicate_lesson(supabase_client, operator_name, lesson_text)
        if existing_id:
            results["duplicates"] += 1
        else:
            stored = store_lessons(supabase_client, operator_name, user_id, [lesson])
            results["stored"] += stored

    # 3. Promote
    results["promoted"] = promote_recurring_lessons(supabase_client, operator_name)

    logger.info(
        f"[LEARNING] Loop complete: {results['extracted']} extracted, "
        f"{results['stored']} stored, {results['duplicates']} dupes, "
        f"{results['promoted']} promoted"
    )
    return results