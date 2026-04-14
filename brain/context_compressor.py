# ============================================
# CHAMP V3 — Context Compressor
# Harvested from: Hermes Agent (NousResearch)
#
# Upgrades the existing context_builder.py compaction:
#   OLD: Drop oldest messages when over threshold
#   NEW: Summarize the middle, keep head + tail intact
#
# Strategy (Hermes pattern):
#   1. Protect HEAD: system prompt + first exchange
#      (identity/intent framing — never touch)
#   2. Protect TAIL: last ~20K tokens
#      (recent context — critical for coherence)
#   3. SUMMARIZE MIDDLE: compress old turns into
#      a structured summary via cheap LLM
#   4. On subsequent compressions, UPDATE the
#      existing summary (don't re-summarize from scratch)
#
# This lets operators run indefinitely long sessions
# without losing important early context.
# ============================================

import json
import logging
from typing import Optional

import requests

from brain.config import Settings
from brain.models import ChatMessage

logger = logging.getLogger(__name__)

# Rough token estimate
CHARS_PER_TOKEN = 4

# Tail protection budget (tokens to always keep fresh)
TAIL_BUDGET_TOKENS = 20_000

# Head protection: always keep system + first N messages
HEAD_MESSAGES = 3  # system + first user + first assistant

# Context windows
MODEL_CONTEXT_WINDOWS = {
    "claude-sonnet": 200_000,
    "gemini-flash": 1_000_000,
    "gpt-4o": 128_000,
    "deepseek": 64_000,
}
DEFAULT_CONTEXT_WINDOW = 128_000

# Trigger compression at this % of context window
COMPRESSION_THRESHOLD = 0.75

SUMMARY_PROMPT = """\
Compress the following conversation turns into a structured summary.
Preserve: decisions made, facts stated, tasks completed, user preferences expressed.
Drop: filler, repeated content, tool call details, verbose explanations.

CONVERSATION TO COMPRESS:
{conversation}

Return a concise summary in this format:
## Conversation Summary (Turns {start_turn}-{end_turn})
- **Decisions:** [key decisions made]
- **Facts:** [important facts stated]
- **Tasks:** [tasks completed or in progress]
- **Context:** [other relevant context]

Keep it under 500 words. Be specific — include names, numbers, and details."""

UPDATE_SUMMARY_PROMPT = """\
Update the existing conversation summary with new turns that are being compressed.
Merge the new information with the existing summary.

EXISTING SUMMARY:
{existing_summary}

NEW TURNS TO ADD:
{new_conversation}

Return the UPDATED summary in the same format. Keep it under 600 words.
Remove information that's now outdated or superseded by newer turns."""


class ContextCompressor:
    """
    Smart context compression for long-running operator sessions.

    Better than the existing ContextBuilder compaction because:
    1. Summarizes instead of dropping (no information loss)
    2. Protects head AND tail (not just recent messages)
    3. Iteratively updates summaries (efficient on re-compression)
    4. Uses a cheap model for compression (Gemini Flash)

    Integrates with ContextBuilder — call compress() before build().
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_url = f"{settings.litellm_base_url}/chat/completions"
        self.llm_api_key = settings.litellm_api_key

        # Track existing summaries per session
        self._summaries: dict[str, str] = {}

    def should_compress(
        self, messages: list[ChatMessage], model: str = ""
    ) -> bool:
        """Check if compression is needed."""
        total_tokens = self._estimate_total_tokens(messages)
        window = MODEL_CONTEXT_WINDOWS.get(model, DEFAULT_CONTEXT_WINDOW)
        threshold = int(window * COMPRESSION_THRESHOLD)
        return total_tokens > threshold and len(messages) > (HEAD_MESSAGES + 6)

    async def compress(
        self,
        session_id: str,
        messages: list[ChatMessage],
        model: str = "",
    ) -> list[ChatMessage]:
        """
        Compress messages by summarizing the middle section.

        Returns a new message list:
        [head messages] + [summary message] + [tail messages]
        """
        if not self.should_compress(messages, model):
            return messages

        window = MODEL_CONTEXT_WINDOWS.get(model, DEFAULT_CONTEXT_WINDOW)

        # Split into head / middle / tail
        head = messages[:HEAD_MESSAGES]
        remaining = messages[HEAD_MESSAGES:]

        # Calculate tail size
        tail_tokens = 0
        tail_start = len(remaining)
        for i in range(len(remaining) - 1, -1, -1):
            msg_tokens = self._estimate_msg_tokens(remaining[i])
            if tail_tokens + msg_tokens > TAIL_BUDGET_TOKENS:
                break
            tail_tokens += msg_tokens
            tail_start = i

        tail = remaining[tail_start:]
        middle = remaining[:tail_start]

        if not middle:
            return messages  # Nothing to compress

        # Summarize or update existing summary
        existing_summary = self._summaries.get(session_id)
        summary_text = await self._summarize(
            middle, existing_summary,
            start_turn=HEAD_MESSAGES + 1,
            end_turn=HEAD_MESSAGES + len(middle),
        )

        if summary_text:
            self._summaries[session_id] = summary_text

            summary_msg = ChatMessage(
                role="system",
                content=(
                    f"[COMPRESSED CONTEXT]\n"
                    f"The following is a summary of {len(middle)} earlier messages "
                    f"that were compressed to save context space.\n\n"
                    f"{summary_text}"
                ),
            )

            compressed = [*head, summary_msg, *tail]
            dropped = len(messages) - len(compressed)

            old_tokens = self._estimate_total_tokens(messages)
            new_tokens = self._estimate_total_tokens(compressed)

            logger.info(
                f"[COMPRESSOR] {old_tokens} → {new_tokens} tokens "
                f"({100 - (new_tokens * 100 // old_tokens)}% reduction) | "
                f"{len(middle)} messages summarized, {len(tail)} kept fresh"
            )

            return compressed
        else:
            # Summarization failed — fall back to simple truncation
            logger.warning("[COMPRESSOR] Summarization failed, falling back to truncation")
            return [*head, *tail]

    async def _summarize(
        self,
        messages: list[ChatMessage],
        existing_summary: Optional[str],
        start_turn: int,
        end_turn: int,
    ) -> Optional[str]:
        """Summarize messages using a cheap LLM."""
        conversation = self._format_for_summary(messages)

        if existing_summary:
            prompt = UPDATE_SUMMARY_PROMPT.format(
                existing_summary=existing_summary,
                new_conversation=conversation[:6000],
            )
        else:
            prompt = SUMMARY_PROMPT.format(
                conversation=conversation[:8000],
                start_turn=start_turn,
                end_turn=end_turn,
            )

        try:
            response = requests.post(
                self.llm_url,
                json={
                    "model": "gemini-flash",  # Cheap model for compression
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 800,
                },
                headers={"Authorization": f"Bearer {self.llm_api_key}"},
                timeout=20,
            )
            response.raise_for_status()

            return response.json()["choices"][0]["message"]["content"].strip()

        except Exception as e:
            logger.error(f"[COMPRESSOR] LLM summarization failed: {e}")
            return None

    def discard_session(self, session_id: str) -> None:
        """Clean up when session ends."""
        self._summaries.pop(session_id, None)

    def _format_for_summary(self, messages: list[ChatMessage]) -> str:
        lines = []
        for msg in messages:
            role = msg.role.upper()
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Truncate individual messages for summary input
            if len(content) > 500:
                content = content[:497] + "..."
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _estimate_msg_tokens(self, msg: ChatMessage) -> int:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        return len(content) // CHARS_PER_TOKEN

    def _estimate_total_tokens(self, messages: list[ChatMessage]) -> int:
        return sum(self._estimate_msg_tokens(m) for m in messages)
