# ============================================
# CHAMP V3 — Phase 1: Friday Build
# OpenAI Realtime Model (Voice + Vision + Tools)
# Pattern: reference/friday_jarvis-main + champ_v1
# ============================================

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, RoomInputOptions
from livekit.agents.voice import AgentSession, VoiceActivityVideoSampler
from livekit.plugins import openai, noise_cancellation
from tools import get_weather, search_web

load_dotenv()


# ---- Simple inline persona (Friday-style, swapped for Champ persona in remix) ----
AGENT_INSTRUCTION = """
You are a personal AI assistant. You are direct, helpful, and have a good sense of humor.

Rules:
- Keep responses short and conversational (1-3 sentences for voice).
- If asked to do something, acknowledge it and do it.
- When you see something through the camera or screen share, describe what you ACTUALLY see.
- If no image is present, say so honestly.
- Use tools (weather, web search) when the user asks for information you don't have.
"""

SESSION_INSTRUCTION = """
Greet Anthony briefly. You just came online. Keep it short and natural.
"""


# ============================================
# AGENT CLASS
# ============================================
class Friday(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=openai.realtime.RealtimeModel(
                voice="ash",
                temperature=0.8,
            ),
            tools=[
                get_weather,
                search_web,
            ],
        )


# ============================================
# ENTRYPOINT
# ============================================
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        video_sampler=VoiceActivityVideoSampler(
            speaking_fps=5.0,   # 5 frames/sec while talking (was 1.0)
            silent_fps=2.0,     # 2 frames/sec while silent (was 0.3)
        ),
    )

    await session.start(
        room=ctx.room,
        agent=Friday(),
        room_input_options=RoomInputOptions(
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
