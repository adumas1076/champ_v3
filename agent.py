# ============================================
# CHAMP V3 — OS Entrypoint
# The OS spins up operators.
# Currently: Champ (single operator, mastering it).
# Future: Multi-operator via registry.
#
# Architecture:
#   USER talks to OPERATOR
#   OPERATOR runs ON the OS
#   OS is invisible underneath
#
# Core Loop (every interaction):
#   INPUT   → Ears + Eyes receive
#   THINK   → Brain + Mind process
#   ACT     → Hands do the work
#   RESPOND → Voice + Avatar answer
# ============================================

import asyncio
import logging

from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import AgentSession, RoomInputOptions
# noise_cancellation disabled — was causing choppy audio on Hetzner
# from livekit.plugins import noise_cancellation
from tools import start_brain_session, end_brain_session, poll_completed_runs

# ---- Operator imports ----
from operators.champ import ChampOperator
from operators.registry import registry

logger = logging.getLogger(__name__)

load_dotenv()

# ---- Register operators with the OS ----
# Currently just Champ. Add more here as they're built.
registry.register("champ", ChampOperator)
# registry.register("billy", BillyOperator)    # Future
# registry.register("sadie", SadieOperator)    # Future
# registry.register_config("genesis")          # Future (YAML-only)

# Default operator — the one that answers when the OS starts
DEFAULT_OPERATOR = "champ"


# ============================================
# OS ENTRYPOINT
# Spins up the operator, connects to room,
# manages session lifecycle.
# ============================================
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()

    # Start Brain session (OS-level — memory, persona, learning)
    start_brain_session()

    @ctx.room.on("disconnected")
    def on_disconnect():
        end_brain_session()

    # Spawn the operator from registry
    operator = registry.spawn(DEFAULT_OPERATOR)

    await session.start(
        room=ctx.room,
        agent=operator,
        room_input_options=RoomInputOptions(
            video_enabled=True,
            text_enabled=True,
        ),
    )

    await ctx.connect()

    # Enable Audio RED (Redundant Encoding) to reduce choppiness
    # Sends redundant audio packets so dropped ones don't cause gaps
    for pub in ctx.room.local_participant.track_publications.values():
        if pub.track and pub.track.kind == rtc.TrackKind.KIND_AUDIO:
            await pub.track.set_red_enabled(True)

    # Generate the operator's greeting
    await session.generate_reply(
        instructions=getattr(operator, "greeting", "Greet the user briefly."),
    )

    # Start background notification loop (Self Mode task completion)
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