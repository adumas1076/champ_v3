# ============================================
# CHAMP V3 — Transcript Logger
# Harvested from Genesis/Skipper V5 transcript system
# Accumulates messages in real-time during a conversation
# ============================================

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class TranscriptLogger:
    """
    Accumulates conversation entries in real-time.

    Each entry is structured as:
    {
        "timestamp": ISO-8601 string,
        "seconds": seconds elapsed since session start,
        "speaker": "user" | "champ",
        "text": message content,
        "type": "message" | "tool_call" | "tool_result"
    }

    Used by BrainPipeline to build full transcripts that get
    persisted to call_transcripts via SupabaseMemory.persist_transcript().
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._entries: list[dict] = []
        self._start_time = datetime.now(timezone.utc)
        self._closed = False

        # Running counts
        self._user_count = 0
        self._agent_count = 0
        self._tool_call_count = 0

        logger.debug(f"TranscriptLogger initialized for session {session_id}")

    def _seconds_elapsed(self) -> float:
        """Seconds since session start."""
        delta = datetime.now(timezone.utc) - self._start_time
        return round(delta.total_seconds(), 2)

    def _append(self, speaker: str, text: str, entry_type: str) -> None:
        """Add an entry to the transcript."""
        if self._closed:
            logger.warning(
                f"TranscriptLogger for {self.session_id} is closed — "
                f"ignoring {entry_type} from {speaker}"
            )
            return

        self._entries.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seconds": self._seconds_elapsed(),
            "speaker": speaker,
            "text": text,
            "type": entry_type,
        })

    # ---- Public Logging Methods ----

    def log_user(self, text: str) -> None:
        """Log a user message."""
        self._append("user", text, "message")
        self._user_count += 1

    def log_agent(self, text: str) -> None:
        """Log a Champ (assistant) message."""
        self._append("champ", text, "message")
        self._agent_count += 1

    def log_tool_call(self, name: str, args: Optional[dict] = None) -> None:
        """Log an outbound tool call."""
        text = f"[tool_call] {name}"
        if args:
            try:
                text += f" | {json.dumps(args, default=str)[:500]}"
            except (TypeError, ValueError):
                text += f" | {str(args)[:500]}"
        self._append("champ", text, "tool_call")
        self._tool_call_count += 1

    def log_tool_result(self, name: str, result: Optional[str] = None) -> None:
        """Log a tool result coming back."""
        text = f"[tool_result] {name}"
        if result:
            text += f" | {str(result)[:500]}"
        self._append("champ", text, "tool_result")

    # ---- Output Methods ----

    def get_full_text(self) -> str:
        """
        Plain text transcript, one line per entry.
        Format: [HH:MM:SS] speaker: text
        """
        lines = []
        for entry in self._entries:
            seconds = int(entry.get("seconds", 0))
            h, remainder = divmod(seconds, 3600)
            m, s = divmod(remainder, 60)
            timestamp = f"{h:02d}:{m:02d}:{s:02d}"
            speaker = entry["speaker"].upper()
            lines.append(f"[{timestamp}] {speaker}: {entry['text']}")
        return "\n".join(lines)

    def get_structured_transcript(self) -> list[dict]:
        """Return the full list of transcript entries as JSON-serializable dicts."""
        return list(self._entries)

    def get_stats(self) -> dict:
        """Return message counts and duration."""
        return {
            "message_count": len(self._entries),
            "user_message_count": self._user_count,
            "agent_message_count": self._agent_count,
            "tool_call_count": self._tool_call_count,
            "duration_seconds": int(self._seconds_elapsed()),
        }

    def close(self) -> None:
        """Finalize the transcript — no more entries accepted."""
        self._closed = True
        stats = self.get_stats()
        logger.info(
            f"TranscriptLogger closed for {self.session_id} | "
            f"{stats['message_count']} entries, "
            f"{stats['duration_seconds']}s duration"
        )
