# ============================================
# CHAMP V3 — Frozen Memory Snapshot
# Harvested from: Hermes Agent (NousResearch)
#
# Pattern: Memory is loaded ONCE at session start,
# frozen into a snapshot, and injected into every
# system prompt for the entire session.
#
# Mid-session memory writes save to disk/DB but
# do NOT mutate the current system prompt.
# This preserves LLM prefix cache hits across
# the entire conversation = massive cost savings.
# ============================================

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """
    Immutable memory snapshot captured at session start.

    Once frozen, the snapshot never changes for the duration
    of the session. This means the system prompt prefix stays
    identical across turns, enabling prefix caching on Claude,
    GPT-4, and Gemini (saves 50-90% on input tokens).

    Mid-session memory writes go to the live store (Supabase/Letta)
    and will be picked up on the NEXT session start.
    """

    # Frozen content blocks
    profile: str = ""          # [USER PROFILE] section
    lessons: str = ""          # [PROVEN LESSONS] section
    healing: str = ""          # [ACTIVE WARNINGS] section
    letta_blocks: str = ""     # [MEMORY:*] blocks from Letta
    mem0_context: str = ""     # Mem0 knowledge base context
    user_model: str = ""       # [USER MODEL] from dual-peer system
    ai_model: str = ""         # [AI SELF-MODEL] from dual-peer system

    # Metadata
    frozen_at: float = 0.0     # Unix timestamp when snapshot was taken
    session_id: str = ""
    user_id: str = ""
    char_count: int = 0        # Total chars in snapshot

    # State
    _frozen: bool = field(default=False, repr=False)

    def freeze(self) -> None:
        """Lock the snapshot. No more mutations allowed."""
        self._frozen = True
        self.frozen_at = time.time()
        self.char_count = len(self.format())
        logger.info(
            f"[SNAPSHOT] Frozen for session {self.session_id} | "
            f"{self.char_count} chars | user={self.user_id}"
        )

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    def format(self) -> str:
        """
        Render the snapshot as a string for system prompt injection.
        This output is identical on every call (frozen), so the
        LLM prefix cache stays warm.
        """
        sections = []

        if self.profile:
            sections.append(self.profile)
        if self.lessons:
            sections.append(self.lessons)
        if self.healing:
            sections.append(self.healing)
        if self.letta_blocks:
            sections.append(self.letta_blocks)
        if self.mem0_context:
            sections.append(self.mem0_context)
        if self.user_model:
            sections.append(self.user_model)
        if self.ai_model:
            sections.append(self.ai_model)

        if not sections:
            return ""

        return "\n\n[MEMORY]\n" + "\n\n".join(sections)


class SnapshotManager:
    """
    Manages the lifecycle of memory snapshots.

    Flow:
    1. Session starts → capture() builds snapshot from all memory sources
    2. Snapshot is frozen → injected into every system prompt
    3. Mid-session writes go to live store, NOT the snapshot
    4. Session ends → snapshot is discarded
    5. Next session → new snapshot from updated live store
    """

    def __init__(self):
        self._snapshots: dict[str, MemorySnapshot] = {}

    async def capture(
        self,
        session_id: str,
        user_id: str,
        memory,          # SupabaseMemory instance
        letta=None,      # LettaMemory instance (optional)
        mem0=None,        # Mem0Memory instance (optional)
        user_modeling=None,  # UserModeling instance (optional)
    ) -> MemorySnapshot:
        """
        Build and freeze a memory snapshot from all sources.
        Called once at session start. Returns the frozen snapshot.
        """
        snapshot = MemorySnapshot(session_id=session_id, user_id=user_id)

        # 1. Supabase profile + lessons + healing (separated)
        profile, lessons, healing = await self._fetch_supabase_sections(
            memory, user_id
        )
        snapshot.profile = profile
        snapshot.lessons = lessons
        snapshot.healing = healing

        # 2. Letta memory blocks
        if letta and letta.available:
            try:
                snapshot.letta_blocks = await letta.get_all_blocks()
            except Exception as e:
                logger.warning(f"[SNAPSHOT] Letta fetch failed (non-fatal): {e}")

        # 3. Mem0 knowledge (broad query for session start)
        if mem0:
            try:
                snapshot.mem0_context = await mem0.get_context(
                    user_id, query="general context"
                )
            except Exception as e:
                logger.warning(f"[SNAPSHOT] Mem0 fetch failed (non-fatal): {e}")

        # 4. User modeling (dual-peer)
        if user_modeling:
            try:
                user_repr = await user_modeling.get_user_representation(user_id)
                ai_repr = await user_modeling.get_ai_representation(user_id)
                if user_repr:
                    snapshot.user_model = f"[USER MODEL]\n{user_repr}"
                if ai_repr:
                    snapshot.ai_model = f"[AI SELF-MODEL]\n{ai_repr}"
            except Exception as e:
                logger.warning(f"[SNAPSHOT] User modeling fetch failed (non-fatal): {e}")

        # Freeze it — no more mutations
        snapshot.freeze()
        self._snapshots[session_id] = snapshot

        return snapshot

    def get(self, session_id: str) -> Optional[MemorySnapshot]:
        """Get the frozen snapshot for a session."""
        return self._snapshots.get(session_id)

    def discard(self, session_id: str) -> None:
        """Discard snapshot when session ends."""
        removed = self._snapshots.pop(session_id, None)
        if removed:
            logger.info(f"[SNAPSHOT] Discarded for session {session_id}")

    async def _fetch_supabase_sections(
        self, memory, user_id: str
    ) -> tuple[str, str, str]:
        """
        Fetch Supabase memory as separate sections.
        Returns (profile_str, lessons_str, healing_str).
        """
        profile = ""
        lessons = ""
        healing = ""

        if not memory._client:
            return profile, lessons, healing

        # Profile
        try:
            result = await memory._client.table("mem_profile").select(
                "key, value, category, confidence"
            ).eq("user_id", user_id).execute()

            if result.data:
                lines = []
                for row in result.data:
                    tag = f" [{row['confidence']}]" if row.get("confidence") else ""
                    lines.append(f"- {row['key']}: {row['value']}{tag}")
                profile = "[USER PROFILE]\n" + "\n".join(lines)
        except Exception as e:
            logger.error(f"[SNAPSHOT] Profile fetch failed: {e}")

        # Lessons
        try:
            result = await memory._client.table("mem_lessons").select(
                "lesson, tags, times_seen, status"
            ).eq("user_id", user_id).in_(
                "status", ["standard", "locked"]
            ).execute()

            if result.data:
                lines = []
                for row in result.data:
                    tags = ", ".join(row.get("tags", []))
                    lines.append(
                        f"- {row['lesson']} (seen {row['times_seen']}x, "
                        f"{row['status']}) [{tags}]"
                    )
                lessons = "[PROVEN LESSONS]\n" + "\n".join(lines)
        except Exception as e:
            logger.error(f"[SNAPSHOT] Lessons fetch failed: {e}")

        # Healing
        try:
            result = await memory._client.table("mem_healing").select(
                "error_type, severity, trigger_context, prevention_rule"
            ).eq("user_id", user_id).eq("resolved", False).execute()

            if result.data:
                lines = []
                for row in result.data:
                    lines.append(
                        f"- [{row['severity'].upper()}] {row['error_type']}: "
                        f"{row['trigger_context']} → {row['prevention_rule']}"
                    )
                healing = "[ACTIVE WARNINGS]\n" + "\n".join(lines)
        except Exception as e:
            logger.error(f"[SNAPSHOT] Healing fetch failed: {e}")

        return profile, lessons, healing
