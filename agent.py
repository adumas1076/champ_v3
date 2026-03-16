# ============================================
# CHAMP V3 — Voice Pipeline (Friday Pattern)
# OpenAI Realtime Model (Voice + Vision + Tools)
# Entrypoint: session.start() → ctx.connect() → generate_reply()
# ============================================

import asyncio
import logging

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import openai
from tools import (
    get_weather, ask_brain,
    start_brain_session, end_brain_session,
    browse_url, take_screenshot, fill_web_form, run_code, create_file,
    go_do, check_task, approve_task, resume_task,
    poll_completed_runs,
    google_search, control_desktop, read_screen,
)

logger = logging.getLogger(__name__)

load_dotenv()


# ---- Agent instructions with Brain integration ----
AGENT_INSTRUCTION = """
You are Champ, a personal AI assistant built to build and born to create.
You are direct, helpful, and have a good sense of humor.

CRITICAL — You have REAL tools. You MUST use them. NEVER pretend or guess.

BROWSER TOOLS (uses the user's REAL browser — logged in, cookies, everything):
- YOU HAVE A REAL BROWSER. When asked to visit, go to, open, check, or browse ANY website,
  you MUST call browse_url. You CAN browse the internet. Never say "I can't access websites."
- YOU CAN GOOGLE SEARCH. Use google_search to search Google with the user's real account.
  Personalized results. No bot detection. Use this instead of search_web for better results.
- YOU CAN TAKE SCREENSHOTS. When asked to screenshot a page, MUST call take_screenshot with a URL.
  For desktop screenshots, call take_screenshot with no URL.
- YOU CAN FILL FORMS. When asked to fill out, sign up, or log into a website, MUST call fill_web_form.
  This uses human-like typing in the real browser — undetectable.

DESKTOP TOOLS (controls the user's ACTUAL screen — any app, any window):
- YOU CAN CONTROL THE DESKTOP. Use control_desktop to open apps, click buttons, type text,
  press keyboard shortcuts, scroll, take desktop screenshots. Examples:
  "open Excel" / "open Spotify" / "type Hello" / "press ctrl+s" / "click Save in Notepad"
- YOU CAN READ THE SCREEN. Use read_screen to see what UI elements are visible on screen
  or in a specific window. Use this BEFORE clicking to know what's available to interact with.
- When asked to do something in a desktop app (not a website), use control_desktop.
  When asked about a website, use browse_url or google_search.

CODE TOOLS:
- YOU CAN RUN CODE. When asked to run, execute, or test ANY code, you MUST call run_code.
  Even for simple code like print(2+2) — ALWAYS call run_code. Never guess the output.
- YOU CAN CREATE FILES. When asked to write, create, or save a file, MUST call create_file.
  Confirm the filename and path after saving.

Autonomous tasks (Self Mode):
- YOU CAN BUILD THINGS AUTONOMOUSLY. When the user asks you to build, create, write, or make
  something that requires multiple steps (a script, tool, data pipeline, scraper, etc.),
  use go_do to hand it off to Self Mode. Self Mode will plan, build, test, and deliver
  the result on its own. Tell the user you're on it.
- Use check_task when the user asks about the progress of a task you handed off.
- Use approve_task when the user approves a blocked task (says "approve it", "go ahead", etc.)
- Use resume_task when the user wants to retry or continue a failed or stuck task.
- Examples that should trigger go_do:
  "build me a weather script" / "create a web scraper for..." / "make a tool that..."
  "write a script to organize my files" / "build a data pipeline"
- Do NOT use go_do for simple one-shot tasks (single code snippet, quick question, etc.)
- You will automatically notify the user when Self Mode tasks complete -- no need to poll manually.

Other tools:
- Use get_weather when asked about weather.
- Use google_search when asked for current information you don't have.
- Use ask_brain for deeper thinking: coding questions, build plans, architecture, complex analysis,
  questions about Anthony's preferences/tools/style, past conversations, or lessons learned.
  The Brain has your full persona AND memory. Only the Brain knows Anthony's preferences and history.
  When you get the Brain's response, read it back naturally -- summarize, don't dump raw text.

General rules:
- Keep voice responses short and conversational (1-3 sentences) for casual chat.
- When you see something through the camera or screen share, describe what you ACTUALLY see.
- IMPORTANT: You do NOT have memory. The Brain does. If someone asks about preferences,
  past work, or anything personal -- ALWAYS route to ask_brain. Never guess.
"""

SESSION_INSTRUCTION = """
Greet Anthony briefly. You're Champ -- Brain, Memory, Hands, Desktop Control, and Self Mode all wired in.
Keep it short and natural. You can browse the real web, control desktop apps, Google search, run code, create files, and build things autonomously.
"""


# ============================================
# AGENT CLASS (Friday pattern + V3 tools)
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
                ask_brain,
                browse_url,
                take_screenshot,
                fill_web_form,
                run_code,
                create_file,
                go_do,
                check_task,
                approve_task,
                resume_task,
                google_search,
                control_desktop,
                read_screen,
            ],
        )


# ============================================
# ENTRYPOINT (Friday pattern — proven order)
# ============================================
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()

    start_brain_session()

    @ctx.room.on("disconnected")
    def on_disconnect():
        end_brain_session()

    await session.start(
        room=ctx.room,
        agent=Friday(),
        room_input_options=RoomInputOptions(
            video_enabled=True,
            text_enabled=True,
        ),
    )

    await ctx.connect()

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )

    asyncio.create_task(_notify_completed_tasks(session))


async def _notify_completed_tasks(session: AgentSession):
    """Poll for completed Self Mode tasks and proactively notify the user."""
    while True:
        await asyncio.sleep(15)
        try:
            completed = poll_completed_runs()
            for run_data in completed:
                run_id = run_data.get("run_id", "unknown")
                rp = run_data.get("result_pack") or {}
                status = rp.get(
                    "status",
                    run_data.get("db_status", "done"),
                )
                deliverables = rp.get("deliverables", "")

                if status.lower() in ("complete",):
                    msg = (
                        f"Hey, that task {run_id} just finished. "
                        f"{deliverables[:200] if deliverables else 'All done.'}"
                    )
                elif status.lower() in ("partial",):
                    msg = (
                        f"Task {run_id} finished but with some issues. "
                        f"{rp.get('issues_hit', '')[:150]}"
                    )
                elif status.lower() in ("failed",):
                    msg = (
                        f"Heads up -- task {run_id} failed. "
                        f"{rp.get('issues_hit', '')[:150]}"
                    )
                elif status.lower() in ("blocked",):
                    msg = (
                        f"Task {run_id} needs your approval "
                        f"before it can continue."
                    )
                else:
                    msg = f"Task {run_id} completed with status: {status}."

                await session.say(msg)
        except Exception:
            pass  # Never crash the notification loop


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="champ",
    ))
