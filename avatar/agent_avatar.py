"""
CHAMP Avatar Lab — Standalone agent for testing avatar rendering.

This is a SEPARATE agent entrypoint that doesn't touch the main agent.py.
It runs a minimal voice agent with the avatar renderer attached.

Usage:
    cd champ_v3
    python avatar/agent_avatar.py dev

This starts a LiveKit agent that:
1. Connects to the room
2. Runs a simple voice agent (OpenAI Realtime, no tools)
3. Initializes the avatar renderer
4. Publishes animated video frames as a WebRTC video track
5. Frontend AvatarLab.tsx (or VoiceCall.tsx) picks up the video track

Test at: http://localhost:3000/avatar-lab
"""

import asyncio
import logging
import sys
import os

# Add parent dir to path so we can import from champ_v3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import openai

from avatar.renderer import ChampAvatarRenderer
from avatar.controller import AvatarStateController
from avatar.states import AvatarState
from avatar import config

logger = logging.getLogger("champ.avatar.lab")

# ── Simple voice agent for testing ──────────────────────────────────────

AVATAR_LAB_INSTRUCTION = """
You are Champ, a personal AI assistant. This is a test session for the avatar system.
Talk naturally. Keep responses conversational and medium length so we can test
lip sync, expressions, and state transitions.
When asked about the avatar, explain that you're testing the new animated face system.
"""


class AvatarLabAgent(Agent):
    """Minimal agent — just voice, no tools. For testing avatar rendering."""
    def __init__(self):
        super().__init__(
            instructions=AVATAR_LAB_INSTRUCTION,
            llm=openai.realtime.RealtimeModel(
                voice="ash",
                temperature=0.8,
            ),
        )


# ── Entrypoint ──────────────────────────────────────────────────────────

async def entrypoint(ctx: agents.JobContext):
    """
    Avatar Lab entrypoint.
    Mirrors the main agent.py pattern but adds avatar rendering.
    """
    logger.info("=" * 60)
    logger.info("CHAMP Avatar Lab — Starting")
    logger.info("=" * 60)

    session = AgentSession()

    # Initialize the avatar renderer
    renderer = ChampAvatarRenderer(
        reference_image=str(config.REFERENCE_IMAGE),
        width=config.VIDEO_WIDTH,
        height=config.VIDEO_HEIGHT,
        fps=config.VIDEO_FPS,
    )
    await renderer.initialize()

    # Set up the avatar state controller (bridges room events → renderer)
    controller = AvatarStateController(renderer, ctx.room)
    await controller.start()

    # Wire the renderer as the avatar for this session
    # The renderer implements VideoGenerator interface:
    #   push_audio(), clear_buffer(), __aiter__()
    # LiveKit's AvatarRunner will orchestrate audio/video sync

    from livekit.agents.voice.avatar import AvatarRunner, AvatarOptions, QueueAudioOutput

    # Create audio output that feeds the renderer
    audio_output = QueueAudioOutput()

    avatar_options = AvatarOptions(
        video_width=config.VIDEO_WIDTH,
        video_height=config.VIDEO_HEIGHT,
        video_fps=config.VIDEO_FPS,
        audio_sample_rate=config.AUDIO_INPUT_SAMPLE_RATE,
        audio_channels=config.AUDIO_INPUT_CHANNELS,
    )

    avatar_runner = AvatarRunner(
        room=ctx.room,
        audio_recv=audio_output,
        video_gen=renderer,
        options=avatar_options,
    )
    await avatar_runner.start()

    # Start the voice session
    await session.start(
        room=ctx.room,
        agent=AvatarLabAgent(),
        room_input_options=RoomInputOptions(
            text_enabled=True,
        ),
    )

    await ctx.connect()

    await session.generate_reply(
        instructions="Greet the user. Say 'Avatar Lab is live — you should be seeing my animated face right now. How do I look?'",
    )

    logger.info("Avatar Lab session active")

    # Cleanup on disconnect
    @ctx.room.on("disconnected")
    def on_disconnect():
        asyncio.create_task(renderer.close())
        asyncio.create_task(controller.close())


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cli = agents.cli.WorkerOptions(
        entrypoint_fnc=entrypoint,
    )
    agents.cli.run_app(cli)