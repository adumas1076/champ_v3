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
import os
import time

from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import AgentSession, RoomInputOptions
from livekit.plugins import noise_cancellation, silero
from tools import start_brain_session, end_brain_session, poll_completed_runs
from brain.transcript_logger import TranscriptLogger

# ---- Live Creatiq Avatar (our Keyframe/LiveAvatar replacement) ----
try:
    from avatar.livecreatiq_plugin import LiveCreatiqAvatarSession
    LIVECREATIQ_AVAILABLE = True
except ImportError:
    LIVECREATIQ_AVAILABLE = False

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
    conv_id = start_brain_session()

    # Initialize transcript logger for this session
    transcript_logger = TranscriptLogger(conv_id or "unknown")

    @ctx.room.on("disconnected")
    def on_disconnect():
        # Persist transcript + session data before ending
        try:
            transcript_logger.close()
            stats = transcript_logger.get_stats()
            if stats["message_count"] > 0:
                import requests, os
                brain_url = os.getenv("BRAIN_URL", "http://127.0.0.1:8100")

                # Extract tool names from transcript entries
                tools_used = list(set(
                    entry["text"].split("] ")[1].split(" |")[0]
                    for entry in transcript_logger.get_structured_transcript()
                    if entry.get("type") == "tool_call" and "] " in entry.get("text", "")
                ))

                requests.post(
                    f"{brain_url}/v1/transcript/persist",
                    json={
                        "session_id": conv_id,
                        "transcript_text": transcript_logger.get_full_text(),
                        "transcript_json": transcript_logger.get_structured_transcript(),
                        "stats": stats,
                        "operator_name": DEFAULT_OPERATOR,
                        "tools_used": tools_used,
                    },
                    timeout=10,
                )
                logger.info(f"Transcript persisted: {stats['message_count']} entries, {stats['duration_seconds']}s")
            else:
                logger.info("No transcript entries to persist")
        except Exception as e:
            logger.error(f"Transcript persist failed (non-fatal): {e}")
        end_brain_session()

    # Spawn the operator from registry
    operator = registry.spawn(DEFAULT_OPERATOR)

    # Wire transcript logging — capture what user says and what Champ says
    @session.on("user_input_transcribed")
    def on_user_input(event):
        try:
            if event.is_final and event.transcript.strip():
                transcript_logger.log_user(event.transcript.strip())
                logger.info(f"USER: {event.transcript.strip()}")
        except Exception as e:
            logger.warning(f"Transcript log (user) failed: {e}")

    @session.on("conversation_item_added")
    def on_conversation_item(event):
        try:
            msg = event.item
            # Try multiple ways to get the text content
            text = None
            if hasattr(msg, 'text_content') and msg.text_content:
                text = msg.text_content
            elif hasattr(msg, 'content') and msg.content:
                # Content might be a list of blocks
                if isinstance(msg.content, list):
                    for block in msg.content:
                        if hasattr(block, 'text') and block.text:
                            text = block.text
                            break
                elif isinstance(msg.content, str):
                    text = msg.content

            if text and text.strip():
                role = getattr(msg, 'role', 'unknown')
                if role == 'assistant':
                    transcript_logger.log_agent(text.strip())
                    logger.info(f"CHAMP: {text.strip()}")
                # Skip user role — already captured by user_input_transcribed
        except Exception as e:
            logger.warning(f"Transcript log (agent) failed: {e}")

    # Backup: log all state changes for debugging
    @session.on("agent_state_changed")
    def on_state_change(event):
        logger.info(f"AGENT STATE: {event.old_state} -> {event.new_state}")

    await session.start(
        room=ctx.room,
        agent=operator,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
            video_enabled=True,
            text_enabled=True,
        ),
    )

    await ctx.connect()

    # ── Live Creatiq Avatar (Ditto on Modal) ──
    # Same pattern as Keyframe/LiveAvatar: start AFTER ctx.connect, BEFORE generating reply
    avatar_image = os.getenv("LIVECREATIQ_SOURCE_IMAGE", "")
    if avatar_image and LIVECREATIQ_AVAILABLE:
        try:
            logger.info(f"[OS] Initializing Live Creatiq Avatar: {avatar_image[:30]}...")
            avatar = LiveCreatiqAvatarSession(
                source_image_path=avatar_image,
                modal_app_name=os.getenv("LIVECREATIQ_MODAL_APP", "champ-ditto-avatar"),
            )
            await avatar.start(session, room=ctx.room)
            logger.info("[OS] Live Creatiq Avatar active — Genesis is live")
        except Exception as e:
            logger.error(f"[OS] Live Creatiq Avatar failed: {e}", exc_info=True)
            logger.warning("[OS] Continuing without avatar (voice-only mode)")
    elif avatar_image and not LIVECREATIQ_AVAILABLE:
        logger.warning("[OS] LIVECREATIQ_SOURCE_IMAGE set but plugin not importable")
    else:
        logger.info("[OS] No LIVECREATIQ_SOURCE_IMAGE — running voice-only mode")

    # Enable Audio RED (Redundant Encoding) to reduce choppiness
    # Sends redundant audio packets so dropped ones don't cause gaps
    for pub in ctx.room.local_participant.track_publications.values():
        if pub.track and pub.track.kind == rtc.TrackKind.KIND_AUDIO:
            await pub.track.set_red_enabled(True)

    # ── Avatar Motion DataChannel (Phase 7) ──
    # For Gaussian Splat mode: send 229-byte motion frames at 25fps
    # instead of video frames. Client renders 3DGS locally at 120+ FPS.
    # Only active when CHAMP_AVATAR_RENDER_MODE=gaussian_splat
    import os
    if os.getenv("CHAMP_AVATAR_RENDER_MODE") == "gaussian_splat":
        asyncio.create_task(_start_motion_channel(ctx, session, operator))

    # Generate the operator's greeting
    await session.generate_reply(
        instructions=getattr(operator, "greeting", "Greet the user briefly."),
    )

    # Start background notification loop (Self Mode task completion)
    asyncio.create_task(_notify_completed_tasks(session))


async def _start_motion_channel(ctx: agents.JobContext, session: AgentSession, operator):
    """
    Phase 7: Motion DataChannel for Gaussian Splat avatars.

    Instead of streaming video frames (4 MB/s), send motion parameters
    over a DataChannel (229 bytes/frame = 5.7 KB/s at 25fps).

    The client's gsplat.js loads the cached .ply and applies motion locally,
    rendering at 120+ FPS with zero server GPU.
    """
    try:
        from avatar.splat.motion_driver import SplatMotionDriver
        from avatar.motion import MotionPredictor
        from avatar.body.gesture_predictor import GesturePredictor

        avatar_id = getattr(operator, "avatar_id", "default")

        driver = SplatMotionDriver()
        driver.load_avatar(avatar_id)

        motion_predictor = MotionPredictor()
        gesture_predictor = GesturePredictor()

        logger.info(f"[MOTION] DataChannel started for avatar '{avatar_id}'")

        # Send motion frames at 25fps while the session is active
        import numpy as np
        frame_interval = 1.0 / 25.0  # 25fps

        while True:
            await asyncio.sleep(frame_interval)

            try:
                # Get audio features from current audio (if speaking)
                # In idle mode, the idle animator produces subtle motion
                audio_features = np.zeros(768, dtype=np.float32)

                # Predict motion from audio
                motion_vec = motion_predictor.predict(audio_features)
                gesture = gesture_predictor.predict(audio_features)

                # Convert to DataChannel frame
                frame = driver.drive(motion_vec, gesture=gesture)

                # Publish via LiveKit DataChannel
                await ctx.room.local_participant.publish_data(
                    frame.to_bytes(),
                    reliable=False,  # UDP-like: drop frames rather than buffer
                    topic="avatar_motion",
                )
            except Exception:
                pass  # Never crash the motion loop

    except ImportError as e:
        logger.info(f"[MOTION] Avatar modules not available ({e}), skipping DataChannel")
    except Exception as e:
        logger.error(f"[MOTION] DataChannel failed: {e}")


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