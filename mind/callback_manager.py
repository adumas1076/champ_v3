# ============================================
# Conversation Matrix — Callback Manager
# Stores and retrieves callback-worthy moments.
# Fed by: Post-Hook 3 (Callback Extractor)
# Feeds: Pre-Hook 7 (Callback Injection)
# ============================================

import logging
from dataclasses import dataclass
from typing import Optional

from brain.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class Callback:
    """A callback-worthy conversation moment."""
    id: str
    callback_type: str       # laughter | strong_agreement | unresolved | roast_moment | inside_joke | analogy_landed
    trigger_text: str         # what the AI said
    user_reaction: str        # what the user said back
    context_summary: str      # brief context
    engagement_score: float   # 0.0 to 1.0
    times_called_back: int
    session_id: str


class CallbackManager:
    """
    Manages callback-worthy moments for conversation memory.

    Stores moments that landed (user laughed, agreed strongly,
    or disagreed and left it hanging). Retrieves them for
    injection into future turns so the AI can reference them.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._supabase = None

    async def connect(self) -> bool:
        """Connect to Supabase."""
        try:
            from brain.memory import SupabaseMemory
            mem = SupabaseMemory(self.settings)
            await mem.connect()
            self._supabase = mem._client
            logger.info("[CALLBACKS] Connected to Supabase")
            return True
        except Exception as e:
            logger.warning(f"[CALLBACKS] Supabase connection failed: {e}")
            return False

    async def store(
        self,
        session_id: str,
        user_id: str,
        operator_name: str,
        callback_type: str,
        trigger_text: str,
        user_reaction: str = "",
        context_summary: str = "",
        engagement_score: float = 0.5,
    ) -> Optional[str]:
        """
        Store a new callback-worthy moment.

        Returns the callback ID if stored, None if failed.
        """
        if not self._supabase:
            logger.warning("[CALLBACKS] Not connected — skipping store")
            return None

        try:
            result = self._supabase.table("conv_callbacks").insert({
                "session_id": session_id,
                "user_id": user_id,
                "operator_name": operator_name,
                "callback_type": callback_type,
                "trigger_text": trigger_text[:500],
                "user_reaction": (user_reaction or "")[:500],
                "context_summary": (context_summary or "")[:200],
                "engagement_score": engagement_score,
            }).execute()

            callback_id = result.data[0]["id"] if result.data else None
            logger.info(
                f"[CALLBACKS] Stored: {callback_type} (score={engagement_score:.2f}) "
                f"id={callback_id}"
            )
            return callback_id

        except Exception as e:
            logger.error(f"[CALLBACKS] Store failed: {e}")
            return None

    async def get_active(
        self,
        user_id: str,
        session_id: str = "",
        operator_name: str = "champ",
        limit: int = 5,
    ) -> list[Callback]:
        """
        Get active callbacks for injection into conversation context.

        Returns top callbacks by engagement score.
        Mixes: recent session callbacks + all-time best + inside jokes.
        """
        if not self._supabase:
            return []

        try:
            result = (
                self._supabase.table("conv_callbacks")
                .select("*")
                .eq("user_id", user_id)
                .eq("operator_name", operator_name)
                .eq("status", "active")
                .order("engagement_score", desc=True)
                .limit(limit)
                .execute()
            )

            callbacks = [
                Callback(
                    id=row["id"],
                    callback_type=row["callback_type"],
                    trigger_text=row["trigger_text"],
                    user_reaction=row.get("user_reaction", ""),
                    context_summary=row.get("context_summary", ""),
                    engagement_score=row.get("engagement_score", 0.5),
                    times_called_back=row.get("times_called_back", 0),
                    session_id=row.get("session_id", ""),
                )
                for row in (result.data or [])
            ]

            logger.debug(f"[CALLBACKS] Retrieved {len(callbacks)} active callbacks")
            return callbacks

        except Exception as e:
            logger.error(f"[CALLBACKS] Retrieval failed: {e}")
            return []

    async def mark_called_back(self, callback_id: str) -> None:
        """Mark a callback as used (increment counter)."""
        if not self._supabase:
            return

        try:
            self._supabase.rpc("increment_callback", {
                "p_callback_id": callback_id,
            }).execute()
        except Exception:
            # Non-fatal — if RPC doesn't exist yet, just log
            try:
                self._supabase.table("conv_callbacks").update({
                    "times_called_back": "times_called_back + 1",  # raw SQL needed
                    "last_called_back": "now()",
                }).eq("id", callback_id).execute()
            except Exception as e:
                logger.debug(f"[CALLBACKS] Mark called back failed: {e}")

    async def cleanup_stale(
        self,
        user_id: str,
        max_age_days: int = 30,
    ) -> int:
        """
        Mark old unused callbacks as stale.

        Callbacks that were never called back after 30 days
        probably aren't worth keeping active.
        """
        if not self._supabase:
            return 0

        try:
            result = (
                self._supabase.table("conv_callbacks")
                .update({"status": "stale"})
                .eq("user_id", user_id)
                .eq("status", "active")
                .eq("times_called_back", 0)
                .lt("created_at", f"now() - interval '{max_age_days} days'")
                .execute()
            )

            count = len(result.data) if result.data else 0
            if count:
                logger.info(f"[CALLBACKS] Cleaned up {count} stale callbacks")
            return count

        except Exception as e:
            logger.error(f"[CALLBACKS] Cleanup failed: {e}")
            return 0

    def format_for_injection(self, callbacks: list[Callback]) -> str:
        """
        Format callbacks for system prompt injection.

        This string gets injected so the AI knows what to reference.
        """
        if not callbacks:
            return ""

        lines = ["[CALLBACK CONTEXT — Reference these naturally when relevant]"]

        for cb in callbacks:
            label = cb.callback_type.replace("_", " ").title()
            used = f" (referenced {cb.times_called_back}x)" if cb.times_called_back > 0 else ""
            lines.append(
                f"- [{label}] \"{cb.trigger_text[:80]}\" — "
                f"{cb.context_summary[:80]}{used}"
            )

        return "\n".join(lines)
