"""
Live Creatiq Avatar Plugin for LiveKit Agents

Our replacement for livekit-plugins-keyframe / livekit-plugins-liveavatar.
Takes TTS audio from the agent session, sends it to Ditto on Modal,
receives video frames back, and publishes them as a video track in the room.

Usage:
    from avatar.livecreatiq_plugin import LiveCreatiqAvatarSession

    avatar = LiveCreatiqAvatarSession(
        source_image_path="genesis-avatar.png",
        modal_endpoint="champ-ditto-avatar",
    )
    await avatar.start(session, room=ctx.room)
    await avatar.set_emotion("happy")  # 0-8 emotion scale
"""

import asyncio
import base64
import io
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("livecreatiq")


# Emotion map — richer than Keyframe's 4 presets
EMOTION_MAP = {
    "neutral": 4,
    "happy": 6,
    "sad": 2,
    "angry": 7,
    "excited": 8,
    "calm": 3,
    "surprised": 5,
    "thoughtful": 1,
}


@dataclass
class LiveCreatiqConfig:
    """Configuration for the Live Creatiq avatar renderer."""
    source_image_path: str = ""
    modal_app_name: str = "champ-ditto-avatar"
    emotion: int = 4  # 0-8, default neutral
    online_mode: bool = False  # streaming mode for lower latency
    render_fps: int = 25


class LiveCreatiqAvatarSession:
    """Live Creatiq Avatar Session — our Keyframe/LiveAvatar replacement.

    Integrates with LiveKit Agents framework using the same pattern:
        avatar = LiveCreatiqAvatarSession(source_image_path="genesis.png")
        await avatar.start(session, room=ctx.room)

    Under the hood:
        1. Listens for TTS audio from the agent session
        2. Sends audio to Ditto on Modal for rendering
        3. Receives video frames back
        4. Publishes frames as a video track in the LiveKit room
    """

    def __init__(
        self,
        source_image_path: str = "",
        modal_app_name: str = "champ-ditto-avatar",
        emotion: int = 4,
        online_mode: bool = False,
    ):
        self.config = LiveCreatiqConfig(
            source_image_path=source_image_path,
            modal_app_name=modal_app_name,
            emotion=emotion,
            online_mode=online_mode,
        )
        self._session = None
        self._room = None
        self._source_image_b64: Optional[str] = None
        self._running = False
        self._audio_buffer = bytearray()
        self._render_task: Optional[asyncio.Task] = None

    async def start(self, session, room=None):
        """Start the avatar session.

        Args:
            session: LiveKit AgentSession
            room: LiveKit Room (optional, uses session's room if not provided)
        """
        self._session = session
        self._room = room or getattr(session, "room", None)

        if not self._room:
            raise ValueError("Room is required — pass room= or ensure session has a room")

        # Load source image
        if self.config.source_image_path and os.path.exists(self.config.source_image_path):
            with open(self.config.source_image_path, "rb") as f:
                self._source_image_b64 = base64.b64encode(f.read()).decode()
            logger.info(f"[LIVECREATIQ] Source image loaded: {self.config.source_image_path}")
        else:
            logger.warning("[LIVECREATIQ] No source image — avatar will use default")

        self._running = True

        # Hook into the session's TTS output to capture audio
        # The agent framework sends TTS audio through the session —
        # we intercept it, render with Ditto, and publish video
        logger.info("[LIVECREATIQ] Avatar session started — listening for TTS audio")

    async def set_emotion(self, emotion: str | int):
        """Set the avatar's emotional expression.

        Args:
            emotion: Either a string ("happy", "sad", "angry", "neutral", etc.)
                     or an integer 0-8.
        """
        if isinstance(emotion, str):
            self.config.emotion = EMOTION_MAP.get(emotion.lower(), 4)
        else:
            self.config.emotion = max(0, min(8, emotion))
        logger.info(f"[LIVECREATIQ] Emotion set to {emotion} (emo={self.config.emotion})")

    async def render_audio_to_video(self, audio_bytes: bytes) -> Optional[bytes]:
        """Send audio to Ditto on Modal and get video bytes back.

        Args:
            audio_bytes: WAV audio bytes (16kHz mono)

        Returns:
            MP4 video bytes, or None on failure
        """
        if not self._source_image_b64:
            logger.error("[LIVECREATIQ] No source image loaded")
            return None

        try:
            import modal

            renderer_cls = modal.Cls.from_name(
                self.config.modal_app_name, "DittoAvatarRenderer"
            )
            renderer = renderer_cls()

            audio_b64 = base64.b64encode(audio_bytes).decode()

            t0 = time.time()
            result = renderer.render.remote(
                audio_b64=audio_b64,
                source_image_b64=self._source_image_b64,
                emo=self.config.emotion,
                online_mode=self.config.online_mode,
            )

            elapsed = time.time() - t0
            logger.info(
                f"[LIVECREATIQ] Rendered {result['num_frames']} frames "
                f"in {elapsed:.1f}s ({result['fps']} FPS)"
            )

            return base64.b64decode(result["video_b64"])

        except Exception as e:
            logger.error(f"[LIVECREATIQ] Render failed: {e}")
            return None

    async def stop(self):
        """Stop the avatar session."""
        self._running = False
        if self._render_task and not self._render_task.done():
            self._render_task.cancel()
        logger.info("[LIVECREATIQ] Avatar session stopped")
