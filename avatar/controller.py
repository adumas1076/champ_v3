"""
CHAMP Avatar State Controller
Bridges LiveKit agent session events to avatar animation states.

Listens to:
    - Agent speaking started/ended → SPEAKING/IDLE
    - User speaking started/ended → LISTENING
    - VAD events → LISTENING/IDLE
    - Interruption → clear buffer, LISTENING

Mirrors HeyGen LiveAvatar's event protocol:
    agent-control: avatar.interrupt, avatar.start_listening, avatar.stop_listening
    agent-response: avatar.speak_started, avatar.speak_ended, user.speak_started, etc.
"""

import asyncio
import logging
import json

from livekit import rtc

from . import config
from .states import AvatarState
from .renderer import ChampAvatarRenderer

logger = logging.getLogger("champ.avatar.controller")


class AvatarStateController:
    """
    Connects LiveKit room events to the avatar renderer's state machine.

    Usage:
        controller = AvatarStateController(renderer, room)
        await controller.start()
    """

    def __init__(self, renderer: ChampAvatarRenderer, room: rtc.Room):
        self._renderer = renderer
        self._room = room
        self._idle_timer: asyncio.Task | None = None

    async def start(self):
        """Register event listeners on the LiveKit room."""
        self._room.on("active_speakers_changed", self._on_active_speakers)
        self._room.on("data_received", self._on_data_received)

        # Start in idle
        self._renderer.set_state(AvatarState.IDLE)
        logger.info("Avatar state controller started")

    async def _on_active_speakers(self, speakers: list):
        """
        LiveKit fires this when active speakers change.
        If user is speaking → avatar should be LISTENING.
        If nobody speaking → start idle timer.
        """
        has_user_speaking = False
        for speaker in speakers:
            # Skip agent/avatar participants
            identity = getattr(speaker, "identity", "") or ""
            if not identity.startswith(("agent", "champ", "avatar")):
                audio_level = getattr(speaker, "audio_level", 0)
                if audio_level > 0.01:
                    has_user_speaking = True
                    break

        if has_user_speaking:
            self._cancel_idle_timer()
            if self._renderer.state != AvatarState.SPEAKING:
                self._renderer.set_state(AvatarState.LISTENING)
        else:
            self._start_idle_timer()

    async def _on_data_received(self, data: bytes, participant, kind):
        """
        Handle data channel messages for avatar control.
        Mirrors HeyGen's agent-control topic protocol.
        """
        try:
            msg = json.loads(data.decode("utf-8"))
            event_type = msg.get("event_type", "")

            if event_type == "avatar.interrupt":
                self._renderer.clear_buffer()
                self._renderer.set_state(AvatarState.LISTENING)
                logger.debug("Avatar interrupted via data channel")

            elif event_type == "avatar.start_listening":
                self._renderer.set_state(AvatarState.LISTENING)

            elif event_type == "avatar.stop_listening":
                self._renderer.set_state(AvatarState.IDLE)

        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    def _start_idle_timer(self):
        """After 3s of silence, transition to idle."""
        self._cancel_idle_timer()
        self._idle_timer = asyncio.create_task(self._idle_after_delay())

    def _cancel_idle_timer(self):
        if self._idle_timer and not self._idle_timer.done():
            self._idle_timer.cancel()
            self._idle_timer = None

    async def _idle_after_delay(self):
        """Wait 3 seconds, then go to idle if still listening."""
        try:
            await asyncio.sleep(3.0)
            if self._renderer.state == AvatarState.LISTENING:
                self._renderer.set_state(AvatarState.IDLE)
        except asyncio.CancelledError:
            pass

    async def close(self):
        """Cleanup."""
        self._cancel_idle_timer()
        logger.info("Avatar state controller closed")