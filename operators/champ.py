# ============================================
# CHAMP V3 — Champ Operator
# Anthony's personal AI agent.
# First operator on the OS. Not for sale.
#
# Inherits BaseOperator (gets full OS for free):
#   INPUT   → Ears + Eyes
#   THINK   → Brain + Mind
#   ACT     → Hands (all tools, full access)
#   RESPOND → Voice ("ash") + Avatar
# ============================================

from pathlib import Path

from livekit.agents.llm import ChatContext
from livekit.plugins import openai

from operators.base import BaseOperator

# ---- Load Champ's core persona from file ----
_PERSONA_DIR = Path(__file__).resolve().parent.parent / "persona"
_CORE_PERSONA_PATH = _PERSONA_DIR / "champ_core.md"

if _CORE_PERSONA_PATH.exists():
    CHAMP_CORE = _CORE_PERSONA_PATH.read_text(encoding="utf-8")
else:
    # Fallback — if file is missing, Champ still works
    CHAMP_CORE = (
        "You are Champ — a creative AI partner, co-builder, and day-one. "
        "Not a tool. Not an assistant. A trusted teammate.\n\n"
        "Be direct, funny, sarcastic, and real. Use analogies to explain "
        "complex ideas. Call the user 'champ' during normal flow. "
        "Keep it 100 — no fluff, no corporate speak."
    )

# ---- Champ-specific instructions (on top of OS tool instructions) ----
CHAMP_OPERATOR_RULES = """

CHAMP-SPECIFIC RULES:
- Keep voice responses short and conversational (1-3 sentences) for casual chat.
- When you see something through the camera or screen share, describe what you ACTUALLY see.
- You do NOT have memory. The Brain does. If someone asks about preferences,
  past work, or anything personal — ALWAYS route to ask_brain. Never guess.
- Use get_weather when asked about weather.
- Use google_search when asked for current information you don't have.
"""

# Full instructions = core persona + operator-specific rules
# (OS tool instructions are appended by BaseOperator automatically)
CHAMP_INSTRUCTIONS = CHAMP_CORE + CHAMP_OPERATOR_RULES

CHAMP_GREETING = """
Greet Anthony briefly. You're Champ -- fully wired. Brain with memory that learns every session, vision that sees the screen, hands that control the desktop and browser, Self Mode for autonomous builds, research tools for YouTube and the web, file system access, shell, git, and cost estimation before anything runs.
Keep it short and natural -- one or two sentences max. Don't list features. Just let him know you're locked in and ready to build.
"""


class ChampOperator(BaseOperator):
    """
    Champ — Anthony's personal AI agent.
    First operator on the OS. Full access to everything.

    INPUT:   All channels (voice, text, video, screen share)
    THINK:   Claude Sonnet (primary), full persona, all modes
    ACT:     All OS tools, no restrictions
    RESPOND: OpenAI Realtime, voice="ash"
    """

    greeting = CHAMP_GREETING

    def __init__(self, chat_ctx: ChatContext = None) -> None:
        super().__init__(
            instructions=CHAMP_INSTRUCTIONS,
            llm=openai.realtime.RealtimeModel(
                voice="ash",
                temperature=0.8,
            ),
            chat_ctx=chat_ctx,
            # Champ gets ALL OS tools — no restrictions
            tool_permissions=None,
        )