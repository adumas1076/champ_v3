# ============================================
# Cocreatiq V1 — Conversation Recovery
# Detect interrupted sessions, resume gracefully
# Pattern: Claude Code conversation recovery + Skipper cleanup pipeline
# ============================================

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


async def find_interrupted_sessions(supabase_client, operator_name: str, user_id: str, max_age_hours: int = 24) -> list[dict]:
    """Find sessions that started but never ended (crashed/disconnected)."""
    if not supabase_client:
        return []

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
        result = await supabase_client.table("sessions").select(
            "id, operator_name, started_at, message_count, title"
        ).eq("operator_name", operator_name).eq("user_id", user_id).is_("ended_at", "null").gt("started_at", cutoff).execute()

        if result.data:
            logger.info(f"Found {len(result.data)} interrupted sessions for {operator_name}")
        return result.data or []
    except Exception as e:
        logger.warning(f"Failed to check interrupted sessions: {e}")
        return []


async def get_last_transcript(supabase_client, session_id: str) -> Optional[str]:
    """Get the transcript from an interrupted session."""
    if not supabase_client:
        return None

    try:
        result = await supabase_client.table("transcripts").select(
            "transcript_text"
        ).eq("session_id", session_id).limit(1).execute()

        if result.data and result.data[0].get("transcript_text"):
            return result.data[0]["transcript_text"]
        return None
    except Exception as e:
        logger.warning(f"Failed to get last transcript: {e}")
        return None


async def close_interrupted_session(supabase_client, session_id: str) -> None:
    """Close an interrupted session by setting ended_at."""
    if not supabase_client:
        return

    try:
        await supabase_client.table("sessions").update({
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "outcome": "interrupted",
        }).eq("id", session_id).execute()
        logger.info(f"Closed interrupted session: {session_id[:8]}...")
    except Exception as e:
        logger.warning(f"Failed to close interrupted session: {e}")


async def build_recovery_context(supabase_client, operator_name: str, user_id: str) -> str:
    """
    Check for interrupted sessions and build recovery context.
    Returns a string to inject into the operator's greeting.
    """
    interrupted = await find_interrupted_sessions(supabase_client, operator_name, user_id)

    if not interrupted:
        return ""

    # Get the most recent interrupted session
    latest = interrupted[0]
    transcript = await get_last_transcript(supabase_client, latest["id"])

    # Close the interrupted session
    await close_interrupted_session(supabase_client, latest["id"])

    # Build recovery context
    recovery = f"\nRECOVERY NOTE: Your last session was interrupted."
    if latest.get("title"):
        recovery += f" You were working on: {latest['title']}."
    if latest.get("message_count", 0) > 0:
        recovery += f" You had {latest['message_count']} messages."
    if transcript:
        # Get last 3 lines of transcript for context
        lines = transcript.strip().split("\n")
        last_lines = lines[-3:] if len(lines) >= 3 else lines
        recovery += f" Last exchange: {' | '.join(last_lines)}"

    recovery += " Briefly acknowledge the interruption and ask if they want to continue where they left off."

    logger.info(f"Recovery context built from session {latest['id'][:8]}...")
    return recovery