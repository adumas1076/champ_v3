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

import os
from pathlib import Path

from livekit.agents.llm import ChatContext
from livekit.plugins import openai

from operators.base import BaseOperator

# ---- Load Champ's core persona from file ----
_PERSONA_DIR = Path(__file__).resolve().parent.parent / "persona"
_CORE_PERSONA_PATH = _PERSONA_DIR / "compiled" / "champ_prompt.md"

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
- ALWAYS respond in English. Never switch languages.
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


def _get_voice_model():
    """
    Select voice model based on CHAMP_VOICE_ENGINE env var.

    CHAMP_VOICE_ENGINE=openai  → OpenAI Realtime "ash" (default)
    CHAMP_VOICE_ENGINE=gemini  → Google Gemini Live
    CHAMP_VOICE_ENGINE=dual    → Our Qwen3-TTS + Orpheus dual engine (future)
    """
    voice_engine = os.getenv("CHAMP_VOICE_ENGINE", "openai")

    if voice_engine == "gemini":
        from livekit.plugins import google
        import logging
        logging.getLogger("champ.operator").info("[VOICE] Gemini Live mode")
        return google.realtime.RealtimeModel(
            voice="Puck",
            temperature=0.8,
            modalities=["AUDIO"],
        )

    if voice_engine == "cocreatiq":
        import logging
        logging.getLogger("champ.operator").info(
            "[VOICE] Cocreatiq mode — Grok brain + OmniVoice custom voice"
        )
        # Return None — we'll set LLM and TTS separately on AgentSession
        return None

    if voice_engine == "dual":
        try:
            from avatar.voice import VoiceEngine
            import logging
            logging.getLogger("champ.operator").info(
                "[VOICE] Dual engine mode — Qwen3-TTS + Orpheus"
            )
        except ImportError:
            import logging
            logging.getLogger("champ.operator").warning(
                "[VOICE] Dual engine requested but avatar.voice not available, "
                "falling back to OpenAI Realtime"
            )

    # Default: OpenAI Realtime
    from openai.types.beta.realtime.session import TurnDetection

    return openai.realtime.RealtimeModel(
        voice="ash",
        temperature=0.8,
        modalities=["text", "audio"],
        turn_detection=TurnDetection(
            type="semantic_vad",
            eagerness="low",
            create_response=True,
            interrupt_response=False,
        ),
    )


def get_cocreatiq_llm():
    """Grok as LLM via OpenAI-compatible API."""
    return openai.LLM(
        model="grok-3-mini",
        base_url="https://api.x.ai/v1",
        api_key=os.getenv("XAI_API_KEY", ""),
        temperature=0.7,
    )


def get_cocreatiq_tts():
    """Custom TTS that hits our Modal voice engine with CHAMP's voice."""
    voice_url = os.getenv("COCREATIQ_VOICE_URL", "")
    voice_key = os.getenv("COCREATIQ_VOICE_KEY", "")

    return openai.TTS(
        model="tts-1",
        voice="alloy",
        base_url=voice_url,
        api_key=voice_key,
    )


class ChampOperator(BaseOperator):
    """
    Champ — Anthony's personal AI agent.
    First operator on the OS. Full access to everything.

    INPUT:   All channels (voice, text, video, screen share)
    THINK:   Claude Sonnet (primary), full persona, all modes
    ACT:     All OS tools, no restrictions
    RESPOND: OpenAI Realtime or Dual Engine (Qwen3-TTS + Orpheus)
             Set CHAMP_VOICE_ENGINE=dual to use cloned voices
    """

    greeting = CHAMP_GREETING

    def __init__(self, chat_ctx: ChatContext = None) -> None:
        voice_model = _get_voice_model()
        voice_engine = os.getenv("CHAMP_VOICE_ENGINE", "openai")

        if voice_engine == "cocreatiq" and voice_model is None:
            # Cocreatiq mode: Grok LLM + custom TTS (set on AgentSession)
            super().__init__(
                instructions=CHAMP_INSTRUCTIONS,
                llm=get_cocreatiq_llm(),
                tts=get_cocreatiq_tts(),
                chat_ctx=chat_ctx,
                tool_permissions=None,
            )
        else:
            # OpenAI Realtime or Gemini (combined LLM+TTS)
            super().__init__(
                instructions=CHAMP_INSTRUCTIONS,
                llm=voice_model,
                chat_ctx=chat_ctx,
                tool_permissions=None,
            )