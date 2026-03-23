# ============================================
# CHAMP V3 — Context Builder
# Assembles the enriched system prompt:
#   persona + mode instructions
# Injected into every LiteLLM request.
#
# Context Compaction (AIOSCP context.compact):
#   When total tokens approach the model's window,
#   older messages are pruned to keep recent context.
# ============================================

import logging

from brain.models import ChatMessage, OutputMode

logger = logging.getLogger(__name__)

# Rough token estimate: 1 token ≈ 4 chars (English text average)
CHARS_PER_TOKEN = 4

# Model context windows (tokens)
MODEL_CONTEXT_WINDOWS = {
    "claude-sonnet": 200_000,
    "gemini-flash": 1_000_000,
    "gpt-4o": 128_000,
    "deepseek": 64_000,
}
DEFAULT_CONTEXT_WINDOW = 128_000

# Compaction triggers at this % of the context window
COMPACTION_THRESHOLD = 0.80

# After compaction, keep this many recent messages minimum
MIN_MESSAGES_AFTER_COMPACT = 10


# Mode instruction suffixes — injected after persona
MODE_INSTRUCTIONS = {
    OutputMode.VIBE: (
        "\n\n[OUTPUT MODE: VIBE]\n"
        "Respond in 2-6 sentences max. Punchy, playful, confident. "
        "Keep momentum and energy high. No headers, no lists unless "
        "absolutely necessary."
    ),
    OutputMode.BUILD: (
        "\n\n[OUTPUT MODE: BUILD]\n"
        "Use clear headers and steps. Start with an analogy, then get "
        "technical. One decision at a time, no overload. Structured and "
        "actionable."
    ),
    OutputMode.SPEC: (
        "\n\n[OUTPUT MODE: SPEC]\n"
        "Deliver copy/paste ready output. Minimal commentary. "
        "If anything is assumed, label it. This is a deliverable, "
        "not a discussion."
    ),
}


def _estimate_tokens(text: str) -> int:
    """Rough token count from character length."""
    return len(text) // CHARS_PER_TOKEN


def _estimate_messages_tokens(messages: list[ChatMessage]) -> int:
    """Estimate total tokens across all messages."""
    total = 0
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        total += _estimate_tokens(content)
    return total


class ContextBuilder:
    """
    Assembles the final message list sent to LiteLLM.

    Replaces any existing system message with the enriched version:
    persona + mode instructions.

    Includes context compaction: when the total context approaches
    the model's window limit, older conversation messages are pruned
    to prevent overflow. System prompt and recent messages are preserved.
    """

    def build(
        self,
        original_messages: list[ChatMessage],
        persona: str,
        mode: OutputMode,
        memory_context: str = "",
        model: str = "",
    ) -> list[ChatMessage]:
        """Build the enriched message list with optional compaction."""
        # Build system prompt: persona + memory + mode
        system_content = persona + memory_context + MODE_INSTRUCTIONS[mode]

        # Strip existing system messages
        conversation_messages = [
            msg for msg in original_messages if msg.role != "system"
        ]

        # Context compaction check
        system_tokens = _estimate_tokens(system_content)
        conversation_tokens = _estimate_messages_tokens(conversation_messages)
        total_tokens = system_tokens + conversation_tokens

        context_window = MODEL_CONTEXT_WINDOWS.get(model, DEFAULT_CONTEXT_WINDOW)
        threshold = int(context_window * COMPACTION_THRESHOLD)

        if total_tokens > threshold and len(conversation_messages) > MIN_MESSAGES_AFTER_COMPACT:
            # Compact: keep system + last N messages that fit
            budget = threshold - system_tokens
            kept = []
            running = 0

            # Walk backwards from most recent, keeping messages until budget exhausted
            for msg in reversed(conversation_messages):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                msg_tokens = _estimate_tokens(content)
                if running + msg_tokens > budget and len(kept) >= MIN_MESSAGES_AFTER_COMPACT:
                    break
                kept.append(msg)
                running += msg_tokens

            kept.reverse()
            dropped = len(conversation_messages) - len(kept)

            logger.info(
                f"[COMPACT] Context at {total_tokens}/{context_window} tokens "
                f"({total_tokens * 100 // context_window}%). "
                f"Dropped {dropped} older messages, kept {len(kept)}."
            )

            # Add a compaction notice so the LLM knows context was trimmed
            compaction_notice = ChatMessage(
                role="system",
                content=(
                    f"[CONTEXT COMPACTED] {dropped} older messages were removed "
                    f"to stay within context limits. Recent conversation preserved."
                ),
            )

            conversation_messages = [compaction_notice, *kept]
        else:
            logger.debug(
                f"Context built: {len(system_content)} chars system, "
                f"{len(conversation_messages)} conversation msgs, "
                f"~{total_tokens} tokens, mode={mode.value}"
            )

        # Assemble: enriched system + conversation
        final_messages = [
            ChatMessage(role="system", content=system_content),
            *conversation_messages,
        ]

        return final_messages
