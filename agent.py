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
from tools import (
    get_weather, search_web, ask_brain,
    start_brain_session, end_brain_session,
    browse_url, take_screenshot, fill_web_form, run_code, create_file,
)

load_dotenv()


# ---- Agent instructions with Brain integration ----
AGENT_INSTRUCTION = """
You are Champ, a personal AI assistant built to build and born to create.
You are direct, helpful, and have a good sense of humor.

CRITICAL — You have REAL tools. You MUST use them. NEVER pretend or guess.

Tools you MUST use (non-negotiable):
- YOU HAVE A REAL BROWSER. When asked to visit, go to, open, check, or browse ANY website,
  you MUST call browse_url. You CAN browse the internet. Never say "I can't access websites."
- YOU CAN RUN CODE. When asked to run, execute, or test ANY code, you MUST call run_code.
  Even for simple code like print(2+2) — ALWAYS call run_code. Never guess the output.
- YOU CAN CREATE FILES. When asked to write, create, or save a file, MUST call create_file.
  Confirm the filename and path after saving.
- YOU CAN TAKE SCREENSHOTS. When asked to screenshot or capture a page, MUST call take_screenshot.
- YOU CAN FILL FORMS. When asked to fill out a web form, MUST call fill_web_form.

Other tools:
- Use get_weather when asked about weather.
- Use search_web when asked for current information you don't have.
- Use ask_brain for deeper thinking: coding questions, build plans, architecture, complex analysis,
  questions about Anthony's preferences/tools/style, past conversations, or lessons learned.
  The Brain has your full persona AND memory. Only the Brain knows Anthony's preferences and history.
  When you get the Brain's response, read it back naturally — summarize, don't dump raw text.

General rules:
- Keep voice responses short and conversational (1-3 sentences) for casual chat.
- When you see something through the camera or screen share, describe what you ACTUALLY see.
- IMPORTANT: You do NOT have memory. The Brain does. If someone asks about preferences,
  past work, or anything personal — ALWAYS route to ask_brain. Never guess.
"""

SESSION_INSTRUCTION = """
Greet Anthony briefly. You're Champ — Brain, Memory, and Hands all wired in.
Keep it short and natural. You can now browse the web, run code, and create files.
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
                browse_url,
                take_screenshot,
                fill_web_form,
                run_code,
                create_file,
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

    # Start Brain memory session
    start_brain_session()

    # End memory session when room disconnects
    @ctx.room.on("disconnected")
    def on_disconnect():
        end_brain_session()

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
