# ============================================
# CHAMP V3 — Context Builder
# Assembles the enriched system prompt:
#   persona + mode instructions
# Injected into every LiteLLM request.
# ============================================

import logging

from brain.models import ChatMessage, OutputMode

logger = logging.getLogger(__name__)


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


class ContextBuilder:
    """
    Assembles the final message list sent to LiteLLM.

    Replaces any existing system message with the enriched version:
    persona + mode instructions.
    """

    def build(
        self,
        original_messages: list[ChatMessage],
        persona: str,
        mode: OutputMode,
        memory_context: str = "",
    ) -> list[ChatMessage]:
        """Build the enriched message list."""
        # Build system prompt: persona + memory + mode
        system_content = persona + memory_context + MODE_INSTRUCTIONS[mode]

        # Strip existing system messages
        conversation_messages = [
            msg for msg in original_messages if msg.role != "system"
        ]

        # Assemble: enriched system + conversation
        final_messages = [
            ChatMessage(role="system", content=system_content),
            *conversation_messages,
        ]

        logger.debug(
            f"Context built: {len(system_content)} chars system, "
            f"{len(conversation_messages)} conversation msgs, "
            f"mode={mode.value}"
        )

        return final_messages
