"""
CHAMP Avatar Renderer — Per-Frame Architecture

Split pipeline for low-latency (~25ms/frame) photo-realistic animation:

    Part 1: Appearance Encoder (LivePortrait) — runs ONCE at startup
            Reference photo → cached appearance features (~200ms one-time)

    Part 2: Audio Features (wav2vec2) — per frame (~5ms)
            Raw audio → 768-dim embedding

    Part 3: Motion Predictor (FlashHead MLP) — per frame (~2ms)
            Audio embedding + context → 52 blendshapes + head pose

    Part 4: Frame Renderer (LivePortrait warp+decode) — per frame (~13ms)
            Cached appearance + motion params → 512x512 RGBA frame

    Part 5: Idle/Listening (procedural) — per frame (<1ms)
            Perlin noise + sine waves → motion params (no ML)

Total: ~22ms per frame = 45fps capacity on RTX 4090
"""

import asyncio
import logging
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator
from pathlib import Path

from . import config
from .states import AvatarState, AvatarStateMachine
from .audio import AudioFeatureExtractor, PlaceholderAudioExtractor
from .motion import MotionPredictor
from .idle import IdleAnimator
from .smoothing import MotionSmoother, TransitionBlender, AnticipatoryMotion

logger = logging.getLogger("champ.avatar.renderer")


class AudioSegmentEnd:
    """Sentinel marking the end of an audio segment."""
    pass


class AppearanceEncoder:
    """
    Part 1: Encodes reference image into cached appearance features.
    Uses LivePortrait's appearance extractor — runs ONCE at startup.
    """

    def __init__(self):
        self._features = None
        self._model = None
        self._available = False

    def load(self, reference_image_path: str, device: str = "cuda") -> bool:
        """
        Load LivePortrait and encode reference image.
        Returns True if successful, False if falling back to placeholder.
        """
        try:
            from live_portrait.config.argument_config import ArgumentConfig
            from live_portrait.live_portrait_pipeline import LivePortraitPipeline

            args = ArgumentConfig()
            args.device_id = 0 if device == "cuda" else -1

            self._model = LivePortraitPipeline(args)

            # Encode reference image
            import cv2
            img = cv2.imread(reference_image_path)
            if img is None:
                logger.warning(f"Could not read reference image: {reference_image_path}")
                return False

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # Extract appearance features (cached for all future frames)
            self._features = self._model.prepare_source(img_rgb)
            self._available = True
            logger.info("LivePortrait appearance encoder loaded and cached")
            return True

        except (ImportError, Exception) as e:
            logger.warning(f"LivePortrait not available ({e}), using placeholder renderer")
            return False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def features(self):
        return self._features

    @property
    def model(self):
        return self._model


class FrameRenderer:
    """
    Part 4: Renders a single frame from appearance features + motion params.
    Uses LivePortrait's warping network + decoder.
    ~13ms per frame on RTX 4090.
    """

    def __init__(self, appearance: AppearanceEncoder):
        self._appearance = appearance
        self._reference_frame: np.ndarray | None = None

    def set_reference_frame(self, frame: np.ndarray):
        """Set the static reference frame for placeholder rendering."""
        self._reference_frame = frame

    def render(self, motion: np.ndarray) -> np.ndarray:
        """
        Render a single frame from motion parameters.

        Args:
            motion: shape (55,) — 52 blendshapes + 3 head pose

        Returns:
            RGBA frame, shape (H, W, 4), uint8
        """
        if self._appearance.available:
            return self._render_liveportrait(motion)
        else:
            return self._render_placeholder(motion)

    def _render_liveportrait(self, motion: np.ndarray) -> np.ndarray:
        """Render using LivePortrait warp + decode from cached appearance."""
        import torch

        blendshapes = motion[:config.NUM_BLENDSHAPES]
        head_pose = motion[config.NUM_BLENDSHAPES:]

        # Convert motion to LivePortrait's expected format
        motion_dict = {
            "exp": torch.from_numpy(blendshapes).float().unsqueeze(0),
            "pose": torch.from_numpy(head_pose).float().unsqueeze(0),
        }

        if config.DEVICE == "cuda" and torch.cuda.is_available():
            motion_dict = {k: v.cuda() for k, v in motion_dict.items()}

        # Warp + decode using cached appearance features
        with torch.no_grad():
            frame_tensor = self._appearance.model.generate_frame(
                self._appearance.features,
                motion_dict,
            )

        # Convert to numpy RGBA
        frame_rgb = frame_tensor.squeeze().permute(1, 2, 0).cpu().numpy()
        frame_rgb = np.clip(frame_rgb * 255, 0, 255).astype(np.uint8)

        # Add alpha channel
        alpha = np.full((frame_rgb.shape[0], frame_rgb.shape[1], 1), 255, dtype=np.uint8)
        return np.concatenate([frame_rgb, alpha], axis=2)

    def _render_placeholder(self, motion: np.ndarray) -> np.ndarray:
        """
        Placeholder renderer: applies motion to reference image using
        simple pixel operations. Good enough to test the full pipeline.
        """
        if self._reference_frame is None:
            frame = np.zeros((config.VIDEO_HEIGHT, config.VIDEO_WIDTH, 4), dtype=np.uint8)
            frame[:, :, 3] = 255
            return frame

        frame = self._reference_frame.copy()

        # Map jaw_open to brightness pulsing (simulates mouth movement)
        jaw_open = motion[config.IDX_JAW_OPEN]
        brightness = 1.0 + jaw_open * 0.12
        frame[:, :, :3] = np.clip(
            frame[:, :, :3].astype(np.float32) * brightness, 0, 255
        ).astype(np.uint8)

        # Map eye blink to darkening the eye region
        blink_val = max(motion[config.IDX_EYE_BLINK_LEFT], motion[config.IDX_EYE_BLINK_RIGHT])
        if blink_val > 0.1:
            eye_top = int(config.VIDEO_HEIGHT * 0.25)
            eye_bot = int(config.VIDEO_HEIGHT * 0.45)
            darken = 1.0 - blink_val * 0.4
            eye_region = frame[eye_top:eye_bot, :, :3].astype(np.float32) * darken
            frame[eye_top:eye_bot, :, :3] = np.clip(eye_region, 0, 255).astype(np.uint8)

        # Map head pose to pixel shifting
        yaw = motion[config.IDX_HEAD_YAW]
        pitch = motion[config.IDX_HEAD_PITCH]
        shift_x = int(yaw * config.VIDEO_WIDTH * 2)
        shift_y = int(pitch * config.VIDEO_HEIGHT * 2)
        if shift_x != 0:
            frame = np.roll(frame, shift_x, axis=1)
        if shift_y != 0:
            frame = np.roll(frame, shift_y, axis=0)

        return frame


class ChampAvatarRenderer:
    """
    CHAMP Avatar Renderer — LiveKit VideoGenerator implementation.

    Orchestrates the split pipeline:
        Audio → Features → Motion → Smoothing → Render → VideoFrame

    Implements the LiveKit VideoGenerator interface:
        - push_audio(frame) — receive TTS audio
        - clear_buffer() — handle interruption
        - __aiter__() — yield video frames
    """

    def __init__(
        self,
        reference_image: str | None = None,
        width: int = config.VIDEO_WIDTH,
        height: int = config.VIDEO_HEIGHT,
        fps: float = config.VIDEO_FPS,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.reference_image = reference_image or str(config.REFERENCE_IMAGE)

        # State machine
        self.state_machine = AvatarStateMachine()

        # Pipeline components
        self._appearance = AppearanceEncoder()
        self._audio_extractor: AudioFeatureExtractor | PlaceholderAudioExtractor | None = None
        self._motion_predictor = MotionPredictor()
        self._idle_animator = IdleAnimator()
        self._frame_renderer = FrameRenderer(self._appearance)

        # Smoothing
        self._smoother = MotionSmoother()
        self._blender = TransitionBlender()
        self._anticipation = AnticipatoryMotion()

        # Frame output queue
        self._frame_queue: asyncio.Queue = asyncio.Queue(maxsize=60)

        # GPU work runs in thread pool
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="avatar")

        # Control
        self._running = False
        self._reference_frame: np.ndarray | None = None

    # ── Initialization ──────────────────────────────────────────────────

    async def initialize(self):
        """Load models and start frame generation loop."""
        logger.info("Initializing CHAMP avatar renderer (split pipeline)...")
        logger.info(f"  Reference: {self.reference_image}")
        logger.info(f"  Resolution: {self.width}x{self.height} @ {self.fps}fps")

        # Load reference image
        self._reference_frame = await self._load_reference_image()
        self._frame_renderer.set_reference_frame(self._reference_frame)

        # Try loading GPU models in thread pool
        loop = asyncio.get_event_loop()
        gpu_available = await loop.run_in_executor(
            self._executor, self._load_models_sync
        )

        if gpu_available:
            self._audio_extractor = AudioFeatureExtractor()
            logger.info("  GPU pipeline: ACTIVE (LivePortrait + wav2vec2 + FlashHead)")
        else:
            self._audio_extractor = PlaceholderAudioExtractor()
            logger.info("  GPU pipeline: PLACEHOLDER (procedural animation)")

        self._running = True

        # Start idle frame generation loop
        asyncio.create_task(self._frame_loop())

        logger.info("CHAMP avatar renderer ready")

    def _load_models_sync(self) -> bool:
        """Load all ML models (runs in thread pool)."""
        try:
            success = self._appearance.load(
                self.reference_image,
                device=config.DEVICE,
            )
            return success
        except Exception as e:
            logger.warning(f"GPU models failed to load: {e}")
            return False

    async def _load_reference_image(self) -> np.ndarray:
        """Load reference image as RGBA numpy array."""
        try:
            from PIL import Image
            img = Image.open(self.reference_image).convert("RGBA")
            img = img.resize((self.width, self.height), Image.LANCZOS)
            return np.array(img)
        except Exception as e:
            logger.warning(f"Reference image load failed: {e}, using solid color")
            frame = np.zeros((self.height, self.width, 4), dtype=np.uint8)
            frame[:, :, :3] = 30
            frame[:, :, 3] = 255
            return frame

    # ── VideoGenerator Interface ────────────────────────────────────────

    async def push_audio(self, frame) -> None:
        """
        Receive TTS audio frame from LiveKit agent.
        Extracts features immediately and generates motion per-frame.
        No 2-second buffering — process as it arrives.
        """
        if isinstance(frame, AudioSegmentEnd):
            # TTS segment ended — transition to listening/idle
            self.state_machine.to_idle(duration=config.TRANSITION_SPEAKING_TO_IDLE)
            self._motion_predictor.clear_context()
            await self._frame_queue.put(AudioSegmentEnd())
            return

        # Transition to speaking
        if self.state_machine.state != AvatarState.SPEAKING:
            self.state_machine.to_speaking(duration=config.TRANSITION_IDLE_TO_SPEAKING)

        # Extract audio data
        audio_data = frame.data
        if isinstance(audio_data, memoryview):
            audio_data = bytes(audio_data)

        # Push to audio feature extractor
        self._audio_extractor.push_audio(audio_data)

    def clear_buffer(self) -> None:
        """Clear audio and frame buffers on interruption."""
        self._audio_extractor.clear()
        self._motion_predictor.clear_context()
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.state_machine.to_listening(
            duration=config.TRANSITION_SPEAKING_TO_LISTENING
        )
        logger.debug("Avatar buffer cleared (interrupted)")

    async def __aiter__(self) -> AsyncIterator:
        """Yield video frames + audio frames for LiveKit's AvatarRunner."""
        while self._running:
            try:
                item = await asyncio.wait_for(
                    self._frame_queue.get(),
                    timeout=1.0 / self.fps,
                )
                yield item
            except asyncio.TimeoutError:
                # Generate a frame on-demand if queue is empty
                frame = self._generate_frame()
                if frame is not None:
                    yield frame

    # ── Frame Generation Loop ───────────────────────────────────────────

    async def _frame_loop(self):
        """
        Main frame generation loop. Runs at target FPS.
        Generates one frame per tick using the appropriate pipeline:
          SPEAKING → audio features → motion predictor → renderer
          IDLE/LISTENING → idle animator → renderer
        """
        frame_interval = 1.0 / self.fps

        while self._running:
            t_start = time.monotonic()

            frame = await self._generate_frame_async()
            if frame is not None:
                try:
                    self._frame_queue.put_nowait(frame)
                except asyncio.QueueFull:
                    # Drop oldest to keep pipeline fresh
                    try:
                        self._frame_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        self._frame_queue.put_nowait(frame)
                    except asyncio.QueueFull:
                        pass

            # Sleep remainder of frame interval
            elapsed = time.monotonic() - t_start
            sleep_time = max(0, frame_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _generate_frame_async(self):
        """Generate one frame, running GPU work in thread pool if needed."""
        state = self.state_machine.state

        if state == AvatarState.SPEAKING and self._audio_extractor.has_audio:
            # GPU path — run in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor, self._generate_speaking_frame
            )
        else:
            # CPU path — procedural animation, fast enough for main thread
            return self._generate_idle_frame(state)

    def _generate_speaking_frame(self):
        """Generate one speaking frame (runs in thread pool for GPU work)."""
        # Step 1: Extract audio features (~5ms)
        audio_features = self._audio_extractor.extract()
        if audio_features is None:
            return self._generate_idle_frame(AvatarState.SPEAKING)

        # Step 2: Predict motion from audio (~2ms)
        raw_motion = self._motion_predictor.predict(audio_features)

        # Step 3: Smooth motion (EMA) (<1ms)
        smoothed = self._smoother.smooth(raw_motion, AvatarState.SPEAKING)

        # Step 4: Apply transition blending (<1ms)
        blended = self._blender.blend(smoothed, self.state_machine)

        # Step 5: Add anticipatory motion (<1ms)
        final_motion = self._anticipation.apply(blended, self.state_machine)

        # Step 6: Render frame (~13ms with LivePortrait, <1ms placeholder)
        frame_rgba = self._frame_renderer.render(final_motion)

        return self._numpy_to_video_frame(frame_rgba)

    def _generate_idle_frame(self, state: AvatarState = None):
        """Generate one idle/listening frame (procedural, no GPU needed)."""
        if state is None:
            state = self.state_machine.state

        # Step 1: Generate procedural motion (<1ms)
        raw_motion = self._idle_animator.generate(state.value)

        # Step 2: Smooth (<1ms)
        smoothed = self._smoother.smooth(raw_motion, state)

        # Step 3: Blend transitions (<1ms)
        blended = self._blender.blend(smoothed, self.state_machine)

        # Step 4: Render (<1ms placeholder, ~13ms LivePortrait)
        frame_rgba = self._frame_renderer.render(blended)

        return self._numpy_to_video_frame(frame_rgba)

    def _generate_frame(self):
        """Synchronous frame generation (for timeout fallback in __aiter__)."""
        state = self.state_machine.state
        if state == AvatarState.SPEAKING and self._audio_extractor.has_audio:
            return self._generate_speaking_frame()
        return self._generate_idle_frame(state)

    # ── State Control ───────────────────────────────────────────────────

    def set_state(self, new_state: AvatarState):
        """External state control (from controller)."""
        if new_state == AvatarState.IDLE:
            self.state_machine.to_idle()
        elif new_state == AvatarState.LISTENING:
            self.state_machine.to_listening()
        elif new_state == AvatarState.SPEAKING:
            self.state_machine.to_speaking()

    @property
    def state(self) -> AvatarState:
        return self.state_machine.state

    # ── Utilities ───────────────────────────────────────────────────────

    def _numpy_to_video_frame(self, frame_data: np.ndarray):
        """Convert numpy RGBA array to LiveKit VideoFrame."""
        from livekit import rtc

        if frame_data.shape[2] == 3:
            alpha = np.full(
                (frame_data.shape[0], frame_data.shape[1], 1), 255, dtype=np.uint8
            )
            frame_data = np.concatenate([frame_data, alpha], axis=2)

        return rtc.VideoFrame(
            width=self.width,
            height=self.height,
            type=rtc.VideoBufferType.RGBA,
            data=frame_data.tobytes(),
        )

    async def close(self):
        """Shutdown renderer and release resources."""
        self._running = False
        self._executor.shutdown(wait=False)
        logger.info("CHAMP avatar renderer closed")