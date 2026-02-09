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
