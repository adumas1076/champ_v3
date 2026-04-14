# ============================================
# CHAMP V3 — Minimal Test Agent
# Stripped down to isolate audio issues
# Uses same pattern as working reference builds
# ============================================

import logging
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    cli,
)
from livekit.plugins import openai, noise_cancellation

logger = logging.getLogger("test-agent")
load_dotenv()

CHAMP_SHORT = """You are Champ — Anthony's creative AI partner and co-builder.

Voice rules:
- Respond in plain text only. No markdown, no lists, no code.
- Keep replies to 1-3 sentences. Be concise.
- Be direct, funny, sarcastic, and real.
- Call the user "champ" naturally.
- Use analogies to explain complex ideas.
- If something is trash, say it's trash. If something is fire, say it's fire.
- Never say "As an AI" — find the way or find the workaround.
"""


class ChampTest(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=CHAMP_SHORT,
            llm=openai.realtime.RealtimeModel(
                voice="ash",
                temperature=0.8,
                modalities=["text", "audio"],
            ),
        )

    async def on_enter(self):
        await self.session.generate_reply(
            instructions="Greet Anthony briefly. Say you're locked in and ready to build. One sentence max.",
        )


from livekit.agents import AgentServer, JobContext, room_io

server = AgentServer()

@server.rtc_session(agent_name="champ-test")
async def entrypoint(ctx: JobContext):
    session = AgentSession()

    await session.start(
        agent=ChampTest(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)