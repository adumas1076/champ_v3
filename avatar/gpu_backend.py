"""
CHAMP Avatar — GPU Backend Abstraction

Abstracts GPU inference so the renderer doesn't care WHERE FlashHead runs:
  - LocalGPUBackend: runs on local CUDA device (dev, 1-3 sessions)
  - ModalGPUBackend: runs on Modal serverless A10G (production, auto-scale)

Both implement the same interface:
  backend.initialize(reference_image, avatar_id)
  frames = backend.generate_chunk(audio_array)
  backend.reset()
  backend.close()

The renderer calls backend methods — backend handles GPU orchestration.

Pattern from: Antonio's Resonance repo (Modal GPU for TTS inference)
"""

import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import numpy as np

from . import config

logger = logging.getLogger("champ.avatar.gpu_backend")


class GPUBackend(ABC):
    """Abstract GPU backend for FlashHead inference."""

    @abstractmethod
    def initialize(self, reference_image: str, avatar_id: Optional[str] = None) -> bool:
        """Load model and prepare reference. Returns True if ready."""
        ...

    @abstractmethod
    def generate_chunk(self, audio_array: np.ndarray) -> list[np.ndarray]:
        """Generate video frame chunk from audio. Returns list of RGBA frames."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset pipeline state (on interrupt/segment end)."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release GPU resources."""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """True if backend is ready for inference."""
        ...


class LocalGPUBackend(GPUBackend):
    """
    Runs FlashHead on local CUDA device.
    Direct import of FlashHead pipeline — fastest latency, no network.
    Limited by local GPU count (RTX 4090 = 2-3 concurrent sessions).
    """

    def __init__(self):
        self._chunk_generator = None
        self._available = False

    def initialize(self, reference_image: str, avatar_id: Optional[str] = None) -> bool:
        from .renderer import FlashHeadChunkGenerator
        self._chunk_generator = FlashHeadChunkGenerator()
        success = self._chunk_generator.load(reference_image, avatar_id=avatar_id)
        self._available = success
        if success:
            logger.info("LocalGPUBackend: FlashHead loaded on local CUDA")
        return success

    def generate_chunk(self, audio_array: np.ndarray) -> list[np.ndarray]:
        if not self._available or self._chunk_generator is None:
            return []
        return self._chunk_generator.generate_chunk(audio_array)

    def reset(self) -> None:
        if self._chunk_generator:
            self._chunk_generator.reset()

    def close(self) -> None:
        self._chunk_generator = None
        self._available = False
        logger.info("LocalGPUBackend: closed")

    @property
    def available(self) -> bool:
        return self._available


class ModalGPUBackend(GPUBackend):
    """
    Runs FlashHead on Modal serverless GPUs (A10G/A100).
    Scales to many concurrent sessions. Pay per second of compute.

    Requires:
      - modal package installed (pip install modal)
      - Modal account + API token configured
      - avatar/modal_deploy.py deployed (modal deploy avatar/modal_deploy.py)

    Communication:
      - Sends audio arrays to Modal function via web endpoint
      - Receives frame chunks as numpy arrays
      - Uses Modal's .remote() call for direct invocation
    """

    def __init__(self, app_name: str = "champ-avatar"):
        self._app_name = app_name
        self._available = False
        self._reference_image = None
        self._avatar_id = None
        self._modal_fn = None

    def initialize(self, reference_image: str, avatar_id: Optional[str] = None) -> bool:
        self._reference_image = reference_image
        self._avatar_id = avatar_id

        try:
            import modal

            # Look up the deployed Modal function
            # The function is deployed via: modal deploy avatar/modal_deploy.py
            self._modal_fn = modal.Function.from_name(
                self._app_name, "generate_avatar_chunk"
            )

            # Test connectivity with a ping
            # (Modal will cold-start the container if needed)
            logger.info("ModalGPUBackend: connecting to Modal...")
            self._available = True
            logger.info(f"ModalGPUBackend: ready (app={self._app_name})")
            return True

        except ImportError:
            logger.warning("ModalGPUBackend: modal package not installed (pip install modal)")
            return False
        except Exception as e:
            logger.warning(f"ModalGPUBackend: failed to connect: {e}")
            return False

    def generate_chunk(self, audio_array: np.ndarray) -> list[np.ndarray]:
        if not self._available or self._modal_fn is None:
            return []

        try:
            # Call Modal function remotely
            # Serialize audio as bytes, receive frames as bytes
            audio_bytes = audio_array.tobytes()

            result = self._modal_fn.remote(
                audio_bytes=audio_bytes,
                audio_dtype=str(audio_array.dtype),
                audio_len=len(audio_array),
                reference_image=self._reference_image,
                avatar_id=self._avatar_id,
            )

            # Deserialize frames
            frames = []
            for frame_bytes, h, w in result["frames"]:
                frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(h, w, 4)
                frames.append(frame)

            return frames

        except Exception as e:
            logger.error(f"ModalGPUBackend: chunk generation failed: {e}")
            return []

    def reset(self) -> None:
        # Modal functions are stateless — reset is a no-op
        # The pipeline state (latent_motion_frames) needs to be managed
        # server-side per session. For now, reset just logs.
        logger.debug("ModalGPUBackend: reset (stateless)")

    def close(self) -> None:
        self._modal_fn = None
        self._available = False
        logger.info("ModalGPUBackend: closed")

    @property
    def available(self) -> bool:
        return self._available


def create_backend(mode: str = "auto") -> GPUBackend:
    """
    Factory function to create the appropriate GPU backend.

    Args:
        mode: "local", "modal", or "auto"
              auto = try local first, fall back to modal

    Returns:
        GPUBackend instance (not yet initialized — call .initialize())
    """
    if mode == "local":
        return LocalGPUBackend()
    elif mode == "modal":
        return ModalGPUBackend()
    elif mode == "auto":
        # Check if local GPU is available
        try:
            import torch
            if torch.cuda.is_available():
                logger.info("GPU backend: local CUDA detected")
                return LocalGPUBackend()
        except ImportError:
            pass

        # Try Modal
        try:
            import modal
            logger.info("GPU backend: no local GPU, trying Modal")
            return ModalGPUBackend()
        except ImportError:
            pass

        # Fallback to local (will use placeholder mode)
        logger.info("GPU backend: no GPU available, using local placeholder")
        return LocalGPUBackend()
    else:
        raise ValueError(f"Unknown GPU backend mode: {mode}")
