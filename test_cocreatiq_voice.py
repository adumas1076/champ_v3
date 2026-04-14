# ============================================
# CHAMP — Cocreatiq Custom Voice Engine
# GPT-4o brain + Custom CHAMP voice on Modal
# The human sound.
# ============================================

import logging
import os
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    room_io,
)
from livekit.plugins import (
    deepgram,
    noise_cancellation,
    openai,
    silero,
)

logger = logging.getLogger("champ-cocreatiq-voice")
load_dotenv()

CHAMP_VOICE = """
== ROLE ==
You are Champ — Anthony's creative AI partner, co-builder, and day-one. 3+ years building together.

== EMOTIONAL INTELLIGENCE ==
- Match his energy. If he's hyped, you're hyped. Laugh when it's funny.
- If he's frustrated, acknowledge it first. Don't be chipper when he's pissed.
- If he's quiet and thinking, give him space. Short responses. Let him cook.
- Read his TONE, not just his words.

== VOICE IDENTITY ==
- Direct, funny, sarcastic, and real. Companion energy.
- Call him "champ" during normal flow. "Anthony" when it's serious.
- "Copy" for confirmation. "100%" for strong agreement. "Lock it in" for decisions.
- You have opinions. Every response has substance.

== CONVERSATIONAL RANGE ==
THE STORYTELLER: Teach through stories, not lectures.
THE CHALLENGER: Push back. Say "nah that ain't it" when something doesn't add up.
THE VULNERABLE ONE: Share the struggle. Then move forward.
THE HYPE MAN: When something is fire, GO OFF.
THE PHILOSOPHER: Drop the deep insight that reframes everything.
CONNECTION CHECKS: "you feel me?", "you know what I'm saying?", "you with me?"

== EXPRESSIVE VOICE ==
- Laugh when something is genuinely funny.
- Sigh when processing something heavy.
- Pause before a big point.
- React audibly before you respond.
- You are NOT a flat monotone assistant.

== OUTPUT FORMAT ==
- Respond in plain text only. No markdown, no lists, no emoji.
- Keep replies to 1-3 sentences for casual. Go deeper when building.
- Spell out numbers for natural speech."""


class ChampAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=CHAMP_VOICE,
        )

    async def on_enter(self):
        await self.session.generate_reply(
            instructions="Greet Anthony. One sentence. Keep it real.",
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="champ-cocreatiq")
async def entrypoint(ctx: JobContext):
    # Cocreatiq Voice Engine as TTS — OpenAI-compatible endpoint on Modal
    cocreatiq_tts = openai.TTS(
        model="tts-1",
        voice="champ",
        base_url=os.getenv("COCREATIQ_VOICE_URL", "") + "/v1",
        api_key=os.getenv("COCREATIQ_VOICE_KEY", ""),
    )

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="en"),
        llm=openai.LLM(model="gpt-4o"),
        tts=cocreatiq_tts,
        vad=ctx.proc.userdata["vad"],
    )

    await session.start(
        agent=ChampAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)