"""
CHAMP Avatar Renderer — Dual Architecture

Two rendering pipelines, selected by config.RENDER_MODE:

  FLASHHEAD_FULL (default, best quality):
    Audio chunks → FlashHead diffusion pipeline → 28 video frames per chunk
    ~0.29s inference for ~1.1s of video (3.8x realtime on RTX 4090 Lite)
    Full diffusion-generated frames — NOT warping a photo.

  SPLIT_PIPELINE (legacy):
    Per-frame: wav2vec2 → FlashHead MLP → LivePortrait warp+decode
    ~22ms per frame. Lower quality (photo warping, not diffusion).

  PLACEHOLDER (no GPU):
    Procedural pixel effects on reference image. For dev/testing.

All modes share: state machine, idle animation, LiveKit VideoGenerator interface.
"""

import asyncio
import logging
import sys
import time
import numpy as np
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator
from pathlib import Path

from . import config
from .config import RenderMode
from .states import AvatarState, AvatarStateMachine
from .audio import AudioFeatureExtractor, PlaceholderAudioExtractor, ChunkAudioAccumulator
from .motion import MotionPredictor
from .idle import IdleAnimator
from .smoothing import MotionSmoother, TransitionBlender, AnticipatoryMotion

logger = logging.getLogger("champ.avatar.renderer")


class AudioSegmentEnd:
    """Sentinel marking the end of an audio segment."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# FlashHead Full Diffusion Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class FlashHeadChunkGenerator:
    """
    Generates video frame chunks using FlashHead's full diffusion pipeline.

    Takes raw 16kHz audio arrays and produces batches of ~28 video frames
    per chunk. The pipeline maintains latent motion frames between chunks
    for temporal continuity.

    Pattern from: SoulX-FlashHead/gradio_app_streaming.py
    API from: SoulX-FlashHead/flash_head/inference.py
    """

    def __init__(self):
        self._pipeline = None
        self._available = False
        self._chunk_count = 0

    def load(self, reference_image_path: str) -> bool:
        """
        Initialize FlashHead pipeline and prepare the reference image.
        Returns True if successful, False if unavailable.
        """
        try:
            # Add FlashHead source to Python path
            flashhead_src = str(config.FLASHHEAD_SRC_DIR)
            if flashhead_src not in sys.path:
                sys.path.insert(0, flashhead_src)

            from flash_head.inference import (
                get_pipeline, get_base_data, get_infer_params,
                get_audio_embedding, run_pipeline,
            )

            # Store references to the API functions
            self._get_audio_embedding = get_audio_embedding
            self._run_pipeline = run_pipeline

            # Initialize pipeline (single GPU)
            logger.info("Loading FlashHead pipeline...")
            self._pipeline = get_pipeline(
                world_size=1,
                ckpt_dir=str(config.FLASHHEAD_DIR),
                model_type=config.FLASHHEAD_MODEL_TYPE,
                wav2vec_dir=str(config.WAV2VEC2_DIR),
            )

            # Prepare reference image (encodes into VAE latent space)
            logger.info(f"Encoding reference image: {reference_image_path}")
            get_base_data(
                self._pipeline,
                cond_image_path_or_dir=reference_image_path,
                base_seed=config.FLASHHEAD_SEED,
                use_face_crop=config.FLASHHEAD_USE_FACE_CROP,
            )

            self._infer_params = get_infer_params()
            self._available = True
            logger.info(
                f"FlashHead pipeline ready "
                f"(model={config.FLASHHEAD_MODEL_TYPE}, "
                f"chunk={self._infer_params['frame_num']} frames, "
                f"fps={self._infer_params['tgt_fps']})"
            )
            return True

        except Exception as e:
            logger.warning(f"FlashHead pipeline not available: {e}")
            self._available = False
            return False

    def generate_chunk(self, audio_array: np.ndarray) -> list[np.ndarray]:
        """
        Generate one chunk of video frames from audio.

        Args:
            audio_array: float32 numpy array at 16kHz (full deque context,
                        up to 8 seconds). FlashHead handles windowing internally.

        Returns:
            List of RGBA frames (H, W, 4) uint8. Typically ~28 usable frames.
            Returns empty list on failure.
        """
        if not self._available or self._pipeline is None:
            return []

        try:
            import torch

            # Compute audio embedding with context windows
            # For streaming: use start/end indices to select the right window
            params = self._infer_params
            frame_num = params['frame_num']
            motion_frames_num = params['motion_frames_num']

            audio_emb = self._get_audio_embedding(
                self._pipeline,
                audio_array,
                audio_start_idx=-1,  # Let FlashHead handle windowing
                audio_end_idx=-1,
            )

            # Run diffusion pipeline → video frames
            # Returns tensor of shape (frame_num, H, W, 3) uint8
            frames_tensor = self._run_pipeline(self._pipeline, audio_emb)

            # Convert to numpy and skip motion continuity frames
            # First `motion_frames_num` frames are for continuity, skip them
            # (except on the very first chunk)
            if self._chunk_count == 0:
                start_idx = 0
            else:
                start_idx = motion_frames_num

            frames = []
            for i in range(start_idx, frames_tensor.shape[0]):
                frame_rgb = frames_tensor[i].cpu().numpy().astype(np.uint8)
                # Add alpha channel
                alpha = np.full(
                    (frame_rgb.shape[0], frame_rgb.shape[1], 1), 255, dtype=np.uint8
                )
                frame_rgba = np.concatenate([frame_rgb, alpha], axis=2)
                frames.append(frame_rgba)

            self._chunk_count += 1
            logger.debug(
                f"FlashHead chunk {self._chunk_count}: "
                f"{len(frames)} frames from {len(audio_array)} audio samples"
            )
            return frames

        except Exception as e:
            logger.error(f"FlashHead chunk generation failed: {e}")
            return []

    def reset(self):
        """Reset chunk counter and pipeline state (on interrupt/clear)."""
        self._chunk_count = 0
        # Reset latent motion frames in pipeline if available
        if self._pipeline is not None and hasattr(self._pipeline, 'latent_motion_frames'):
            self._pipeline.latent_motion_frames = None
        logger.debug("FlashHead chunk generator reset")

    @property
    def available(self) -> bool:
        return self._available


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy Split Pipeline Components (kept for SPLIT_PIPELINE mode)
# ═══════════════════════════════════════════════════════════════════════════════

class AppearanceEncoder:
    """
    Part 1 (SPLIT_PIPELINE only): Encodes reference image into cached
    appearance features using LivePortrait. Runs ONCE at startup.
    """

    def __init__(self):
        self._features = None
        self._model = None
        self._available = False

    def load(self, reference_image_path: str, device: str = "cuda") -> bool:
        try:
            from live_portrait.config.argument_config import ArgumentConfig
            from live_portrait.live_portrait_pipeline import LivePortraitPipeline

            args = ArgumentConfig()
            args.device_id = 0 if device == "cuda" else -1
            self._model = LivePortraitPipeline(args)

            import cv2
            img = cv2.imread(reference_image_path)
            if img is None:
                logger.warning(f"Could not read reference image: {reference_image_path}")
                return False

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
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
    Part 4 (SPLIT_PIPELINE only): Renders a single frame from appearance
    features + motion params using LivePortrait warp+decode.
    Also handles placeholder rendering for PLACEHOLDER mode.
    """

    def __init__(self, appearance: AppearanceEncoder):
        self._appearance = appearance
        self._reference_frame: np.ndarray | None = None

    def set_reference_frame(self, frame: np.ndarray):
        self._reference_frame = frame

    def render(self, motion: np.ndarray) -> np.ndarray:
        if self._appearance.available:
            return self._render_liveportrait(motion)
        else:
            return self._render_placeholder(motion)

    def _render_liveportrait(self, motion: np.ndarray) -> np.ndarray:
        import torch

        blendshapes = motion[:config.NUM_BLENDSHAPES]
        head_pose = motion[config.NUM_BLENDSHAPES:]

        motion_dict = {
            "exp": torch.from_numpy(blendshapes).float().unsqueeze(0),
            "pose": torch.from_numpy(head_pose).float().unsqueeze(0),
        }

        if config.DEVICE == "cuda" and torch.cuda.is_available():
            motion_dict = {k: v.cuda() for k, v in motion_dict.items()}

        with torch.no_grad():
            frame_tensor = self._appearance.model.generate_frame(
                self._appearance.features,
                motion_dict,
            )

        frame_rgb = frame_tensor.squeeze().permute(1, 2, 0).cpu().numpy()
        frame_rgb = np.clip(frame_rgb * 255, 0, 255).astype(np.uint8)

        alpha = np.full((frame_rgb.shape[0], frame_rgb.shape[1], 1), 255, dtype=np.uint8)
        return np.concatenate([frame_rgb, alpha], axis=2)

    def _render_placeholder(self, motion: np.ndarray) -> np.ndarray:
        if self._reference_frame is None:
            frame = np.zeros((config.VIDEO_HEIGHT, config.VIDEO_WIDTH, 4), dtype=np.uint8)
            frame[:, :, 3] = 255
            return frame

        frame = self._reference_frame.copy()

        jaw_open = motion[config.IDX_JAW_OPEN]
        brightness = 1.0 + jaw_open * 0.12
        frame[:, :, :3] = np.clip(
            frame[:, :, :3].astype(np.float32) * brightness, 0, 255
        ).astype(np.uint8)

        blink_val = max(motion[config.IDX_EYE_BLINK_LEFT], motion[config.IDX_EYE_BLINK_RIGHT])
        if blink_val > 0.1:
            eye_top = int(config.VIDEO_HEIGHT * 0.25)
            eye_bot = int(config.VIDEO_HEIGHT * 0.45)
            darken = 1.0 - blink_val * 0.4
            eye_region = frame[eye_top:eye_bot, :, :3].astype(np.float32) * darken
            frame[eye_top:eye_bot, :, :3] = np.clip(eye_region, 0, 255).astype(np.uint8)

        yaw = motion[config.IDX_HEAD_YAW]
        pitch = motion[config.IDX_HEAD_PITCH]
        shift_x = int(yaw * config.VIDEO_WIDTH * 2)
        shift_y = int(pitch * config.VIDEO_HEIGHT * 2)
        if shift_x != 0:
            frame = np.roll(frame, shift_x, axis=1)
        if shift_y != 0:
            frame = np.roll(frame, shift_y, axis=0)

        return frame


# ═══════════════════════════════════════════════════════════════════════════════
# Main Renderer (Orchestrator)
# ═══════════════════════════════════════════════════════════════════════════════

class ChampAvatarRenderer:
    """
    CHAMP Avatar Renderer — LiveKit VideoGenerator implementation.

    Routes to the appropriate pipeline based on config.RENDER_MODE:
      - FLASHHEAD_FULL: chunk-based diffusion (best quality)
      - SPLIT_PIPELINE: per-frame warp (legacy)
      - PLACEHOLDER: procedural (no GPU)

    Implements the LiveKit VideoGenerator interface:
        - push_audio(frame) — receive TTS audio
        - clear_buffer() — handle interruption
        - __aiter__() — yield video frames
    """

    def __init__(
        self,
        reference_image: str | None = None,
        avatar_id: str | None = None,
        width: int = config.VIDEO_WIDTH,
        height: int = config.VIDEO_HEIGHT,
        fps: float = config.VIDEO_FPS,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.render_mode = config.RENDER_MODE

        # Resolve reference: avatar_id (multi-ref) > reference_image > config default
        if avatar_id:
            from .training.avatar_registry import AvatarRegistry
            registry = AvatarRegistry()
            self.reference_image = registry.get_reference_path(avatar_id)
            self._avatar_id = avatar_id
            logger.info(f"Using avatar '{avatar_id}': {self.reference_image}")
        else:
            self.reference_image = reference_image or str(config.REFERENCE_IMAGE)
            self._avatar_id = None

        # State machine
        self.state_machine = AvatarStateMachine()

        # Idle animation (shared across all modes)
        self._idle_animator = IdleAnimator()
        self._smoother = MotionSmoother()
        self._blender = TransitionBlender()
        self._anticipation = AnticipatoryMotion()

        # FlashHead full pipeline components (FLASHHEAD_FULL mode)
        self._chunk_generator: FlashHeadChunkGenerator | None = None
        self._chunk_audio: ChunkAudioAccumulator | None = None
        self._speaking_frame_buffer: deque = deque()  # Buffered frames from chunks

        # Split pipeline components (SPLIT_PIPELINE mode)
        self._appearance = AppearanceEncoder()
        self._audio_extractor: AudioFeatureExtractor | PlaceholderAudioExtractor | None = None
        self._motion_predictor = MotionPredictor()
        self._frame_renderer = FrameRenderer(self._appearance)

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
        logger.info(f"Initializing CHAMP avatar renderer (mode={self.render_mode.value})...")
        logger.info(f"  Reference: {self.reference_image}")
        logger.info(f"  Resolution: {self.width}x{self.height} @ {self.fps}fps")

        # Load reference image (needed for placeholder/idle rendering)
        self._reference_frame = await self._load_reference_image()
        self._frame_renderer.set_reference_frame(self._reference_frame)

        # Initialize based on render mode
        loop = asyncio.get_event_loop()

        if self.render_mode == RenderMode.FLASHHEAD_FULL:
            success = await loop.run_in_executor(
                self._executor, self._load_flashhead_full
            )
            if success:
                self._chunk_audio = ChunkAudioAccumulator()
                logger.info("  Pipeline: FLASHHEAD FULL DIFFUSION (chunk-based)")
            else:
                # Fall back to placeholder
                self.render_mode = RenderMode.PLACEHOLDER
                self._audio_extractor = PlaceholderAudioExtractor()
                logger.info("  Pipeline: PLACEHOLDER (FlashHead failed to load)")

        elif self.render_mode == RenderMode.SPLIT_PIPELINE:
            success = await loop.run_in_executor(
                self._executor, self._load_split_pipeline
            )
            if success:
                self._audio_extractor = AudioFeatureExtractor()
                logger.info("  Pipeline: SPLIT (LivePortrait + wav2vec2 + FlashHead MLP)")
            else:
                self.render_mode = RenderMode.PLACEHOLDER
                self._audio_extractor = PlaceholderAudioExtractor()
                logger.info("  Pipeline: PLACEHOLDER (split pipeline failed to load)")

        else:
            self._audio_extractor = PlaceholderAudioExtractor()
            logger.info("  Pipeline: PLACEHOLDER (procedural animation)")

        self._running = True
        asyncio.create_task(self._frame_loop())
        logger.info("CHAMP avatar renderer ready")

    def _load_flashhead_full(self) -> bool:
        """Load FlashHead full diffusion pipeline (runs in thread pool)."""
        self._chunk_generator = FlashHeadChunkGenerator()
        return self._chunk_generator.load(self.reference_image)

    def _load_split_pipeline(self) -> bool:
        """Load legacy split pipeline (runs in thread pool)."""
        return self._appearance.load(self.reference_image, device=config.DEVICE)

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
        Routes to appropriate audio handler based on render mode.
        """
        if isinstance(frame, AudioSegmentEnd):
            self.state_machine.to_idle(duration=config.TRANSITION_SPEAKING_TO_IDLE)
            if self.render_mode == RenderMode.FLASHHEAD_FULL:
                # Flush any remaining audio as a final chunk
                if self._chunk_audio and self._chunk_audio.has_audio:
                    await self._generate_flashhead_chunk()
                if self._chunk_generator:
                    self._chunk_generator.reset()
            else:
                self._motion_predictor.clear_context()
            await self._frame_queue.put(AudioSegmentEnd())
            return

        # Transition to speaking
        if self.state_machine.state != AvatarState.SPEAKING:
            self.state_machine.to_speaking(duration=config.TRANSITION_IDLE_TO_SPEAKING)

        # Extract raw audio bytes
        audio_data = frame.data
        if isinstance(audio_data, memoryview):
            audio_data = bytes(audio_data)

        if self.render_mode == RenderMode.FLASHHEAD_FULL:
            # Accumulate audio for chunk-based generation
            self._chunk_audio.push_audio(audio_data)

            # When enough audio for a chunk, generate frames
            if self._chunk_audio.has_chunk_ready():
                await self._generate_flashhead_chunk()
        else:
            # Per-frame extraction (split pipeline / placeholder)
            self._audio_extractor.push_audio(audio_data)

    async def _generate_flashhead_chunk(self):
        """Generate a chunk of frames from accumulated audio (runs in thread pool)."""
        audio_array = self._chunk_audio.consume_chunk()
        loop = asyncio.get_event_loop()
        frames = await loop.run_in_executor(
            self._executor,
            self._chunk_generator.generate_chunk,
            audio_array,
        )

        # Push generated frames into the speaking frame buffer
        for frame_rgba in frames:
            self._speaking_frame_buffer.append(frame_rgba)

        logger.debug(
            f"Chunk generated: {len(frames)} frames, "
            f"buffer={len(self._speaking_frame_buffer)}"
        )

    def clear_buffer(self) -> None:
        """Clear audio and frame buffers on interruption."""
        if self.render_mode == RenderMode.FLASHHEAD_FULL:
            if self._chunk_audio:
                self._chunk_audio.clear()
            if self._chunk_generator:
                self._chunk_generator.reset()
            self._speaking_frame_buffer.clear()
        else:
            if self._audio_extractor:
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
        """Yield video frames for LiveKit's AvatarRunner."""
        while self._running:
            try:
                item = await asyncio.wait_for(
                    self._frame_queue.get(),
                    timeout=1.0 / self.fps,
                )
                yield item
            except asyncio.TimeoutError:
                frame = self._generate_frame()
                if frame is not None:
                    yield frame

    # ── Frame Generation Loop ───────────────────────────────────────────

    async def _frame_loop(self):
        """
        Main frame generation loop. Runs at target FPS.
        FLASHHEAD_FULL: yields pre-generated frames from buffer
        SPLIT_PIPELINE: generates per-frame via motion+warp
        PLACEHOLDER: generates per-frame via procedural effects
        """
        frame_interval = 1.0 / self.fps

        while self._running:
            t_start = time.monotonic()

            frame = await self._generate_frame_async()
            if frame is not None:
                try:
                    self._frame_queue.put_nowait(frame)
                except asyncio.QueueFull:
                    try:
                        self._frame_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        self._frame_queue.put_nowait(frame)
                    except asyncio.QueueFull:
                        pass

            elapsed = time.monotonic() - t_start
            sleep_time = max(0, frame_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _generate_frame_async(self):
        """Generate one frame based on current state and render mode."""
        state = self.state_machine.state

        if state == AvatarState.SPEAKING:
            if self.render_mode == RenderMode.FLASHHEAD_FULL:
                # Consume pre-generated frames from the buffer
                if self._speaking_frame_buffer:
                    frame_rgba = self._speaking_frame_buffer.popleft()
                    return self._numpy_to_video_frame(frame_rgba)
                else:
                    # Buffer empty — generate idle frame while waiting for next chunk
                    return self._generate_idle_frame(state)

            elif self.render_mode == RenderMode.SPLIT_PIPELINE:
                if self._audio_extractor and self._audio_extractor.has_audio:
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        self._executor, self._generate_speaking_frame_split
                    )

        # IDLE / LISTENING — procedural animation (all modes)
        return self._generate_idle_frame(state)

    def _generate_speaking_frame_split(self):
        """Generate one speaking frame via split pipeline (legacy, runs in thread pool)."""
        audio_features = self._audio_extractor.extract()
        if audio_features is None:
            return self._generate_idle_frame(AvatarState.SPEAKING)

        raw_motion = self._motion_predictor.predict(audio_features)
        smoothed = self._smoother.smooth(raw_motion, AvatarState.SPEAKING)
        blended = self._blender.blend(smoothed, self.state_machine)
        final_motion = self._anticipation.apply(blended, self.state_machine)
        frame_rgba = self._frame_renderer.render(final_motion)

        return self._numpy_to_video_frame(frame_rgba)

    def _generate_idle_frame(self, state: AvatarState = None):
        """Generate one idle/listening frame (procedural, no GPU needed)."""
        if state is None:
            state = self.state_machine.state

        raw_motion = self._idle_animator.generate(state.value)
        smoothed = self._smoother.smooth(raw_motion, state)
        blended = self._blender.blend(smoothed, self.state_machine)
        frame_rgba = self._frame_renderer.render(blended)

        return self._numpy_to_video_frame(frame_rgba)

    def _generate_frame(self):
        """Synchronous frame generation (for timeout fallback in __aiter__)."""
        state = self.state_machine.state

        if state == AvatarState.SPEAKING:
            if self.render_mode == RenderMode.FLASHHEAD_FULL:
                if self._speaking_frame_buffer:
                    frame_rgba = self._speaking_frame_buffer.popleft()
                    return self._numpy_to_video_frame(frame_rgba)
            elif self.render_mode == RenderMode.SPLIT_PIPELINE:
                if self._audio_extractor and self._audio_extractor.has_audio:
                    return self._generate_speaking_frame_split()

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
        self._speaking_frame_buffer.clear()
        self._executor.shutdown(wait=False)
        logger.info("CHAMP avatar renderer closed")
