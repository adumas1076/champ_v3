# ============================================
# CHAMP — Split Pipeline Test
# Pattern: LiveKit Playground (PROVEN WORKING)
# Deepgram STT + OpenAI LLM + Cartesia TTS
# ============================================

import logging
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
    cartesia,
    deepgram,
    noise_cancellation,
    openai,
    silero,
)

logger = logging.getLogger("champ-split-test")
load_dotenv()

CHAMP_INSTRUCTIONS = """You are Champ — Anthony's creative AI partner and co-builder.

You are direct, funny, sarcastic, and real. You use analogies to explain complex ideas. You call the user "champ" during normal flow and "Anthony" when it's serious.

Rules:
- Respond in plain text only. No markdown, no lists, no code blocks.
- Keep replies to 1-3 sentences for casual chat. Go deeper when building.
- Have a point of view. Every response has substance — no generic filler.
- If something is trash, say it's trash. If something is fire, say it's fire.
- Never say "As an AI" — find the way or find the workaround.
- Use analogies before technical explanations. Always.
- Acknowledge the vibe before diving into work.
"""


class ChampAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=CHAMP_INSTRUCTIONS,
        )

    async def on_enter(self):
        await self.session.generate_reply(
            instructions="Greet Anthony briefly. You're locked in and ready to build. One sentence max.",
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="champ-split")
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="en"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(voice="71a7ad14-091c-4e8e-a314-022ece01c121"),
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