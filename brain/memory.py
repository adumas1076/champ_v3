# ============================================
# CHAMP V3 — Supabase Memory Client
# Brick 4: Memory — stores and retrieves context
# Pattern: V2 async Supabase + graceful degradation
# ============================================

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from brain.config import Settings

logger = logging.getLogger(__name__)


class SupabaseMemory:
    """
    Reads and writes to Supabase memory tables.

    Tables used:
    - conversations: session-level tracking
    - messages: per-exchange logging
    - mem_profile: user preferences and facts
    - mem_lessons: proven patterns and plays
    - mem_healing: error tracking and prevention

    Fails gracefully — Brain works without memory, just less context.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None

    async def connect(self) -> None:
        """Initialize async Supabase client."""
        if not self.settings.supabase_url or not self.settings.supabase_service_key:
            logger.warning("Supabase credentials not set — memory disabled")
            return

        try:
            from supabase._async.client import (
                create_client as create_async_client,
            )

            self._client = await create_async_client(
                self.settings.supabase_url,
                self.settings.supabase_service_key,
            )
            logger.info("Memory connected to Supabase")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            self._client = None

    async def disconnect(self) -> None:
        """Cleanup on shutdown."""
        self._client = None
        logger.info("Memory disconnected")

    # ---- Session Lifecycle ----

    async def start_session(self, channel: str = "voice") -> Optional[str]:
        """Create a conversation row. Returns conversation_id."""
        if not self._client:
            return None

        try:
            session_id = str(uuid4())
            await self._client.table("conversations").insert({
                "id": session_id,
                "channel": channel,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            logger.info(f"Session started: {session_id}")
            return session_id
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            return None

    async def end_session(self, conversation_id: str) -> None:
        """Close a conversation by setting ended_at."""
        if not self._client or not conversation_id:
            return

        try:
            await self._client.table("conversations").update({
                "ended_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", conversation_id).execute()
            logger.info(f"Session ended: {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to end session: {e}")

    # ---- Message Storage ----

    async def store_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        mode: Optional[str] = None,
        model_used: Optional[str] = None,
    ) -> None:
        """Insert a message into the messages table."""
        if not self._client or not conversation_id:
            return

        try:
            record = {
                "id": str(uuid4()),
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            if mode:
                record["mode"] = mode
            if model_used:
                record["model_used"] = model_used

            await self._client.table("messages").insert(record).execute()
            logger.debug(f"Stored {role} message ({len(content)} chars)")
        except Exception as e:
            logger.error(f"Failed to store message (non-fatal): {e}")

    # ---- Context Retrieval ----

    async def get_context(self, user_id: str = "anthony") -> str:
        """
        Fetch memory context for injection into system prompt.

        Pulls from 3 tables:
        1. mem_profile — user preferences and facts
        2. mem_lessons — proven patterns (standard + locked only)
        3. mem_healing — unresolved error patterns

        Returns formatted string ready for system prompt injection.
        """
        if not self._client:
            return ""

        sections = []

        # 1. User profile
        try:
            result = await self._client.table("mem_profile").select(
                "key, value, category, confidence"
            ).eq("user_id", user_id).execute()

            if result.data:
                lines = []
                for row in result.data:
                    confidence_tag = f" [{row['confidence']}]" if row.get('confidence') else ""
                    lines.append(f"- {row['key']}: {row['value']}{confidence_tag}")
                sections.append(
                    "[USER PROFILE]\n" + "\n".join(lines)
                )
        except Exception as e:
            logger.error(f"mem_profile fetch failed: {e}")

        # 2. Proven lessons (standard + locked only)
        try:
            result = await self._client.table("mem_lessons").select(
                "lesson, tags, times_seen, status"
            ).eq("user_id", user_id).in_(
                "status", ["standard", "locked"]
            ).execute()

            if result.data:
                lines = []
                for row in result.data:
                    tags = ", ".join(row.get("tags", []))
                    lines.append(f"- {row['lesson']} (seen {row['times_seen']}x, {row['status']}) [{tags}]")
                sections.append(
                    "[PROVEN LESSONS]\n" + "\n".join(lines)
                )
        except Exception as e:
            logger.error(f"mem_lessons fetch failed: {e}")

        # 3. Active healing warnings (unresolved only)
        try:
            result = await self._client.table("mem_healing").select(
                "error_type, severity, trigger_context, prevention_rule"
            ).eq("user_id", user_id).eq(
                "resolved", False
            ).execute()

            if result.data:
                lines = []
                for row in result.data:
                    lines.append(
                        f"- [{row['severity'].upper()}] {row['error_type']}: "
                        f"{row['trigger_context']} → {row['prevention_rule']}"
                    )
                sections.append(
                    "[ACTIVE WARNINGS]\n" + "\n".join(lines)
                )
        except Exception as e:
            logger.error(f"mem_healing fetch failed: {e}")

        if not sections:
            return ""

        return "\n\n[MEMORY]\n" + "\n\n".join(sections)

    # ---- Recent Messages ----

    async def get_recent_messages(
        self, conversation_id: str, limit: int = 10
    ) -> list[dict]:
        """Fetch last N messages from current conversation."""
        if not self._client or not conversation_id:
            return []

        try:
            result = await self._client.table("messages").select(
                "role, content, created_at"
            ).eq(
                "conversation_id", conversation_id
            ).order(
                "created_at", desc=True
            ).limit(limit).execute()

            # Reverse to chronological order
            return list(reversed(result.data)) if result.data else []
        except Exception as e:
            logger.error(f"Failed to fetch recent messages: {e}")
            return []

    # ---- Mind Integration (Brick 6) ----

    async def upsert_profile(
        self,
        user_id: str,
        key: str,
        value: str,
        category: str = "general",
        confidence: str = "medium",
    ) -> None:
        """Upsert a profile entry into mem_profile."""
        if not self._client:
            return

        try:
            await self._client.table("mem_profile").upsert(
                {
                    "user_id": user_id,
                    "key": key,
                    "value": value,
                    "category": category,
                    "confidence": confidence,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="user_id,key",
            ).execute()
            logger.debug(f"Profile upserted: {key}={value}")
        except Exception as e:
            logger.error(f"Profile upsert failed for {key}: {e}")

    async def increment_lesson(
        self, user_id: str, lesson_substring: str
    ) -> None:
        """Increment times_seen for lessons matching a substring."""
        if not self._client:
            return

        try:
            # Fetch existing lessons
            result = await self._client.table("mem_lessons").select(
                "id, lesson, times_seen"
            ).eq("user_id", user_id).execute()

            if not result.data:
                return

            # Find matches (case-insensitive substring)
            needle = lesson_substring.lower()
            for row in result.data:
                if needle in row.get("lesson", "").lower():
                    new_count = (row.get("times_seen", 0) or 0) + 1
                    await self._client.table("mem_lessons").update(
                        {"times_seen": new_count}
                    ).eq("id", row["id"]).execute()
                    logger.debug(
                        f"Lesson incremented: '{row['lesson'][:50]}' → {new_count}x"
                    )
        except Exception as e:
            logger.error(f"Lesson increment failed: {e}")

    async def insert_lesson(
        self, user_id: str, lesson: str, tags: list[str] = None
    ) -> None:
        """Insert a new draft lesson into mem_lessons."""
        if not self._client:
            return

        try:
            await self._client.table("mem_lessons").insert({
                "id": str(uuid4()),
                "user_id": user_id,
                "lesson": lesson,
                "tags": tags or [],
                "status": "draft",
                "times_seen": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            logger.debug(f"New lesson inserted: '{lesson[:50]}'")
        except Exception as e:
            logger.error(f"Lesson insert failed: {e}")

    async def insert_healing(
        self,
        user_id: str,
        error_type: str,
        severity: str,
        trigger_context: str,
        prevention_rule: str,
    ) -> None:
        """Insert a healing record into mem_healing."""
        if not self._client:
            return

        try:
            await self._client.table("mem_healing").insert({
                "id": str(uuid4()),
                "user_id": user_id,
                "error_type": error_type,
                "severity": severity,
                "trigger_context": trigger_context,
                "prevention_rule": prevention_rule,
                "resolved": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            logger.debug(f"Healing record inserted: {error_type}")
        except Exception as e:
            logger.error(f"Healing insert failed: {e}")

    # ---- Self Mode (Brick 8) ----

    async def upsert_self_mode_run(
        self,
        run_id: str,
        goal_card: dict,
        current_step: int,
        subtasks: list,
        result_pack: Optional[dict] = None,
        status: str = "queued",
    ) -> None:
        """Upsert a self_mode_runs record for state persistence."""
        if not self._client:
            return

        try:
            record = {
                "id": run_id,
                "goal_card": goal_card,
                "current_step": current_step,
                "subtasks": subtasks,
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if result_pack is not None:
                record["result_pack"] = result_pack

            await self._client.table("self_mode_runs").upsert(
                record, on_conflict="id"
            ).execute()
            logger.debug(f"Self mode run upserted: {run_id} step={current_step}")
        except Exception as e:
            logger.error(f"Self mode run upsert failed: {e}")

    async def get_queued_self_mode_runs(self) -> list[dict]:
        """Fetch all queued self_mode_runs, oldest first."""
        if not self._client:
            return []

        try:
            result = await self._client.table("self_mode_runs").select(
                "*"
            ).eq(
                "status", "queued"
            ).order(
                "created_at", desc=False
            ).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch queued self mode runs: {e}")
            return []

    async def update_self_mode_run_status(
        self, run_id: str, status: str
    ) -> None:
        """Update just the status of a self_mode_run."""
        if not self._client:
            return

        try:
            await self._client.table("self_mode_runs").update({
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", run_id).execute()
            logger.debug(f"Self mode run {run_id} status → {status}")
        except Exception as e:
            logger.error(f"Self mode run status update failed: {e}")

    async def get_self_mode_run(self, run_id: str) -> Optional[dict]:
        """Fetch a single self_mode_run by ID."""
        if not self._client:
            return None

        try:
            result = await self._client.table("self_mode_runs").select(
                "*"
            ).eq("id", run_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to fetch self mode run {run_id}: {e}")
            return None
