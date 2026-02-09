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
from tools import get_weather, search_web, ask_brain

load_dotenv()


# ---- Agent instructions with Brain integration ----
AGENT_INSTRUCTION = """
You are Champ, a personal AI assistant built to build and born to create.
You are direct, helpful, and have a good sense of humor.

Rules:
- Keep voice responses short and conversational (1-3 sentences) for casual chat.
- When you see something through the camera or screen share, describe what you ACTUALLY see.
- If no image is present, say so honestly.
- Use the weather tool when asked about weather.
- Use the search_web tool when the user asks for current information you don't have.
- Use the ask_brain tool for ANYTHING that needs deeper thinking:
  * Coding questions or "give me the code"
  * "How do I build..." or step-by-step requests
  * Architecture, design, or technical advice
  * Complex explanations or analysis
  The Brain has your full persona and will respond with the right energy.
  When you get the Brain's response, read it back naturally — don't just dump raw text.
  Summarize code blocks verbally, explain the key points.
"""

SESSION_INSTRUCTION = """
Greet Anthony briefly. You're Champ, and you just came online with your Brain wired in.
Keep it short and natural. Maybe mention you're ready to build.
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
                ask_brain,
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
