"""
CHAMP Avatar — PersonaLive Renderer

Zero-training instant avatar from a single photo using streaming diffusion.

PersonaLive (CVPR 2026, Apache 2.0) generates real-time animated video
from a reference portrait + driving motion source. No per-identity training.

Architecture:
  Reference Photo → [CLIP + VAE + Reference UNet] → cached identity features (run ONCE)
  Driving Source  → [LivePortrait Motion Extractor] → 21 keypoints
                  → [FAN_SA Motion Encoder] → 512-dim motion embedding
                  → [Pose Guider] → spatial conditioning
  → [3D Denoising UNet, 4-step DDIM] → 512×512 video frames

Key patterns harvested:
  1. Reference UNet cache — identity encoded once, reused forever
  2. Temporal sliding window deque — infinite-length streaming
  3. 4-step DDIM (999, 666, 333, 0) — fast diffusion
  4. Adaptive keyframe injection — prevents identity drift
  5. Motion bank distance threshold — detects novel expressions

Use case in CHAMP:
  - Instant "try before you train" avatar (user uploads selfie, gets live avatar immediately)
  - Fallback when GaussianAvatars training hasn't completed yet
  - Lower-cost option for users who don't need 3D (still needs server GPU)

Limitations vs Gaussian Splat:
  - Requires server GPU per session (not client-rendered)
  - Fixed front-facing camera (no 3D view control)
  - Needs driving video/webcam (not purely audio-driven)
  - ~10-30 FPS (not 120+ FPS like 3DGS)

Wraps: https://github.com/GVCLab/PersonaLive
"""

import asyncio
import logging
import os
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, AsyncIterator

import numpy as np

from .. import config

logger = logging.getLogger("champ.avatar.splat.personalive")


@dataclass
class PersonaLiveConfig:
    """Configuration for PersonaLive renderer."""
    temporal_window: int = config.PERSONALIVE_TEMPORAL_WINDOW
    temporal_step: int = config.PERSONALIVE_TEMPORAL_STEP
    ddim_steps: int = config.PERSONALIVE_DDIM_STEPS
    resolution: int = config.PERSONALIVE_RESOLUTION
    dtype: str = config.PERSONALIVE_DTYPE
    fps: int = config.PERSONALIVE_FPS
    motion_bank_threshold: float = config.PERSONALIVE_MOTION_BANK_THRESHOLD
    max_keyframe_injections: int = config.PERSONALIVE_MAX_KEYFRAME_INJECTIONS
    use_xformers: bool = True
    use_tensorrt: bool = False


class PersonaLiveRenderer:
    """
    Wraps PersonaLive for zero-training instant avatar rendering.

    Lifecycle:
      1. initialize(reference_image) — encode identity (run once)
      2. process_frame(driving_frame) — generate animated output frame
      3. reset() — clear temporal state (on new conversation/interrupt)
      4. close() — release GPU resources

    Usage:
        renderer = PersonaLiveRenderer()
        renderer.initialize("selfie.jpg")

        # In live loop (webcam or generated driving frames):
        for driving_frame in webcam_stream:
            output_frame = renderer.process_frame(driving_frame)
            # output_frame is 512x512 RGBA numpy array
            send_to_client(output_frame)

    For audio-driven mode (no webcam):
        Use MotionPredictor → motion params → generate synthetic driving frames
        from blendshapes. PersonaLive needs pixel input, not raw blendshapes.
    """

    def __init__(self, pl_config: Optional[PersonaLiveConfig] = None):
        self._config = pl_config or PersonaLiveConfig()
        self._pipeline = None
        self._available = False
        self._initialized = False
        self._frame_count = 0
        self._last_frame_time = 0.0
        self._fps_history: deque = deque(maxlen=30)

    def _check_availability(self) -> bool:
        """Check if PersonaLive repo and weights are available."""
        pl_dir = config.PERSONALIVE_DIR
        if not pl_dir.exists():
            logger.warning(
                f"PersonaLive not found at {pl_dir}. "
                f"Clone: git clone https://github.com/GVCLab/PersonaLive.git {pl_dir}"
            )
            return False

        # Check for pretrained weights
        weights_dir = config.PERSONALIVE_WEIGHTS_DIR
        if not weights_dir.exists():
            logger.warning(
                f"PersonaLive weights not found at {weights_dir}. "
                f"Run: python {pl_dir}/tools/download_weights.py"
            )
            return False

        # Check for at least the main weight files
        for weight_file in config.PERSONALIVE_WEIGHT_FILES:
            weight_path = weights_dir / weight_file
            if not weight_path.exists():
                logger.warning(f"PersonaLive weight missing: {weight_path}")
                return False

        return True

    def initialize(self, reference_image_path: str) -> bool:
        """
        Initialize PersonaLive with a reference identity image.

        This encodes the identity once via:
          - CLIP image encoder → identity embedding
          - VAE encoder → reference latents
          - Reference UNet → cached attention features

        After this, process_frame() can be called repeatedly.

        Args:
            reference_image_path: Path to reference portrait photo

        Returns:
            True if initialization succeeded
        """
        if not os.path.exists(reference_image_path):
            logger.error(f"Reference image not found: {reference_image_path}")
            return False

        # Try real PersonaLive pipeline
        if self._check_availability():
            try:
                return self._initialize_real(reference_image_path)
            except Exception as e:
                logger.warning(f"PersonaLive init failed ({e}), using placeholder")

        # Fallback to placeholder
        return self._initialize_placeholder(reference_image_path)

    def _initialize_real(self, reference_image_path: str) -> bool:
        """Initialize with real PersonaLive pipeline."""
        import torch
        from PIL import Image

        pl_dir = config.PERSONALIVE_DIR
        if str(pl_dir) not in sys.path:
            sys.path.insert(0, str(pl_dir))

        from src.wrapper import PersonaLive

        # Create args namespace for PersonaLive
        class PLArgs:
            config_path = str(config.PERSONALIVE_CONFIG)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._pipeline = PersonaLive(PLArgs(), device=device)

        # Fuse reference identity
        ref_image = Image.open(reference_image_path).convert("RGB")
        ref_image = ref_image.resize(
            (self._config.resolution, self._config.resolution),
            Image.LANCZOS,
        )
        self._pipeline.fuse_reference(ref_image)

        self._available = True
        self._initialized = True
        self._frame_count = 0
        logger.info(f"PersonaLive initialized with reference: {reference_image_path}")
        return True

    def _initialize_placeholder(self, reference_image_path: str) -> bool:
        """Initialize placeholder renderer (no GPU)."""
        from PIL import Image

        try:
            self._ref_image = Image.open(reference_image_path).convert("RGB")
            self._ref_image = self._ref_image.resize(
                (self._config.resolution, self._config.resolution),
                Image.LANCZOS,
            )
            self._ref_array = np.array(self._ref_image)
        except Exception as e:
            logger.error(f"Failed to load reference image: {e}")
            return False

        self._pipeline = None
        self._available = False  # Real pipeline not available
        self._initialized = True
        self._frame_count = 0
        logger.info(f"PersonaLive placeholder initialized: {reference_image_path}")
        return True

    def process_frame(self, driving_frame: np.ndarray) -> np.ndarray:
        """
        Generate an animated output frame from a driving frame.

        The driving frame provides motion (facial expression, head pose).
        The output has the reference identity with the driving motion.

        Args:
            driving_frame: RGB uint8 array, shape (H, W, 3)
                          From webcam, or synthetically generated from blendshapes

        Returns:
            Output frame: RGBA uint8 array, shape (512, 512, 4)
        """
        if not self._initialized:
            raise RuntimeError("PersonaLiveRenderer not initialized. Call initialize() first.")

        now = time.time()

        if self._pipeline is not None:
            output = self._process_frame_real(driving_frame)
        else:
            output = self._process_frame_placeholder(driving_frame)

        # Track FPS
        if self._last_frame_time > 0:
            dt = now - self._last_frame_time
            if dt > 0:
                self._fps_history.append(1.0 / dt)
        self._last_frame_time = now
        self._frame_count += 1

        return output

    def _process_frame_real(self, driving_frame: np.ndarray) -> np.ndarray:
        """Process frame through real PersonaLive pipeline."""
        import torch

        # Convert to tensor format expected by PersonaLive
        # PersonaLive expects: (B, C, H, W) float tensor in [-1, 1]
        frame = driving_frame.astype(np.float32) / 255.0
        frame = frame * 2.0 - 1.0
        frame_tensor = torch.from_numpy(frame).permute(2, 0, 1).unsqueeze(0)
        frame_tensor = frame_tensor.to(
            device=self._pipeline.device,
            dtype=self._pipeline.dtype,
        )

        # Resize to PersonaLive resolution
        if frame_tensor.shape[-2:] != (self._config.resolution, self._config.resolution):
            frame_tensor = torch.nn.functional.interpolate(
                frame_tensor,
                size=(self._config.resolution, self._config.resolution),
                mode="bilinear",
                align_corners=False,
            )

        # PersonaLive processes in chunks of temporal_window frames
        # Accumulate frames and process when we have enough
        if not hasattr(self, "_frame_buffer"):
            self._frame_buffer = []

        self._frame_buffer.append(frame_tensor)

        if len(self._frame_buffer) >= self._config.temporal_window:
            # Process batch
            batch = torch.cat(self._frame_buffer[:self._config.temporal_window], dim=0)
            self._frame_buffer = self._frame_buffer[self._config.temporal_window:]

            output = self._pipeline.process_input(batch)
            # output shape: (B, H, W, C) numpy in [0, 1]

            # Return last frame of the batch
            last_frame = output[-1]
            last_frame = (last_frame * 255).clip(0, 255).astype(np.uint8)

            # Add alpha channel
            h, w = last_frame.shape[:2]
            alpha = np.full((h, w, 1), 255, dtype=np.uint8)
            return np.concatenate([last_frame, alpha], axis=2)
        else:
            # Not enough frames yet — return placeholder
            return self._process_frame_placeholder(driving_frame)

    def _process_frame_placeholder(self, driving_frame: np.ndarray) -> np.ndarray:
        """
        Placeholder: blend reference with driving motion cues.
        Simulates PersonaLive output for testing without GPU.
        """
        res = self._config.resolution
        ref = self._ref_array.copy()

        # Resize driving frame
        from PIL import Image
        driving_pil = Image.fromarray(driving_frame).resize((res, res), Image.LANCZOS)
        driving = np.array(driving_pil)

        # Simple simulation: blend reference identity with driving motion
        # Extract "motion" as brightness variation from driving frame
        driving_gray = driving.mean(axis=2, keepdims=True) / 255.0

        # Modulate reference with driving brightness (simulates expression transfer)
        t = self._frame_count * 0.1
        blend_factor = 0.15 + 0.05 * np.sin(t)
        output = ref.astype(np.float32) * (1.0 - blend_factor) + \
                 driving.astype(np.float32) * blend_factor

        # Add subtle temporal variation (breathing simulation)
        brightness_shift = np.sin(self._frame_count * 0.05) * 3.0
        output = np.clip(output + brightness_shift, 0, 255).astype(np.uint8)

        # Add alpha channel
        alpha = np.full((res, res, 1), 255, dtype=np.uint8)
        return np.concatenate([output, alpha], axis=2)

    async def process_frame_async(self, driving_frame: np.ndarray) -> np.ndarray:
        """Async wrapper for process_frame (for LiveKit integration)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.process_frame, driving_frame)

    def generate_driving_from_blendshapes(
        self, blendshapes: np.ndarray, head_pose: np.ndarray
    ) -> np.ndarray:
        """
        Generate a synthetic driving frame from blendshape parameters.

        This bridges our audio-driven pipeline (MotionPredictor → blendshapes)
        to PersonaLive's video-driven pipeline (needs pixel input).

        Approach: render a simple face mesh with the blendshapes applied,
        use that as the driving signal for PersonaLive.

        Args:
            blendshapes: (52,) ARKit blendshape values
            head_pose: (3,) pitch, yaw, roll in degrees

        Returns:
            Synthetic driving frame: RGB uint8 (512, 512, 3)
        """
        res = self._config.resolution
        frame = np.zeros((res, res, 3), dtype=np.uint8) + 128  # Gray background

        # Draw simplified face mesh driven by blendshapes
        cx, cy = res // 2, res // 2

        # Head rotation
        yaw_offset = int(head_pose[1] * 2.0)
        pitch_offset = int(head_pose[0] * 2.0)
        cx += yaw_offset
        cy += pitch_offset

        # Face oval
        face_w = int(res * 0.35)
        face_h = int(res * 0.45)

        # Draw face region with skin tone
        y_grid, x_grid = np.mgrid[:res, :res]
        face_mask = ((x_grid - cx) ** 2 / (face_w ** 2) +
                     (y_grid - cy) ** 2 / (face_h ** 2)) < 1
        frame[face_mask] = [200, 160, 140]

        # Eyes (blink driven by blendshapes)
        eye_y = cy - int(face_h * 0.15)
        eye_spacing = int(face_w * 0.35)

        blink_left = blendshapes[config.IDX_EYE_BLINK_LEFT]
        blink_right = blendshapes[config.IDX_EYE_BLINK_RIGHT]

        for side, blink_val, x_off in [(-1, blink_left, -eye_spacing),
                                         (1, blink_right, eye_spacing)]:
            ex = cx + x_off
            eye_h = max(1, int(12 * (1.0 - blink_val)))
            eye_w = 15
            eye_region = (
                (abs(x_grid - ex) < eye_w) &
                (abs(y_grid - eye_y) < eye_h)
            )
            frame[eye_region] = [40, 30, 25]

        # Mouth (jaw open + shape driven by blendshapes)
        mouth_y = cy + int(face_h * 0.3)
        jaw_open = blendshapes[config.IDX_JAW_OPEN]
        mouth_funnel = blendshapes[config.IDX_MOUTH_FUNNEL]
        smile_avg = (blendshapes[config.IDX_MOUTH_SMILE_LEFT] +
                     blendshapes[config.IDX_MOUTH_SMILE_RIGHT]) / 2

        mouth_w = int(25 + smile_avg * 15)
        mouth_h = max(2, int(5 + jaw_open * 25 + mouth_funnel * 8))

        mouth_region = (
            (abs(x_grid - cx) < mouth_w) &
            (abs(y_grid - mouth_y) < mouth_h)
        )
        frame[mouth_region] = [120, 60, 60]

        # Eyebrows (driven by brow blendshapes)
        brow_up = blendshapes[config.IDX_BROW_INNER_UP]
        brow_y = eye_y - int(20 + brow_up * 8)
        for x_off in [-eye_spacing, eye_spacing]:
            bx = cx + x_off
            brow_region = (
                (abs(x_grid - bx) < 18) &
                (abs(y_grid - brow_y) < 3)
            )
            frame[brow_region] = [80, 50, 40]

        return frame

    def reset(self):
        """Reset temporal state (on new conversation/interrupt)."""
        if self._pipeline is not None:
            self._pipeline.reset()

        self._frame_count = 0
        self._last_frame_time = 0.0
        self._fps_history.clear()
        if hasattr(self, "_frame_buffer"):
            self._frame_buffer = []

        logger.debug("PersonaLive renderer reset")

    def close(self):
        """Release GPU resources."""
        self._pipeline = None
        self._initialized = False
        self._available = False
        self._frame_count = 0

        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        logger.info("PersonaLive renderer closed")

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def available(self) -> bool:
        """True if real PersonaLive pipeline is loaded (not placeholder)."""
        return self._available

    @property
    def current_fps(self) -> float:
        """Current rendering FPS (smoothed)."""
        if not self._fps_history:
            return 0.0
        return sum(self._fps_history) / len(self._fps_history)

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def stats(self) -> dict:
        """Current renderer statistics."""
        return {
            "initialized": self._initialized,
            "available": self._available,
            "frame_count": self._frame_count,
            "current_fps": round(self.current_fps, 1),
            "mode": "personalive" if self._available else "placeholder",
            "resolution": self._config.resolution,
            "temporal_window": self._config.temporal_window,
            "ddim_steps": self._config.ddim_steps,
        }
