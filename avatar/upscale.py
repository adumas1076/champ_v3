"""
CHAMP Avatar — Frame Upscaler

Upscales 512x512 frames to higher resolution using Real-ESRGAN.
Supports 2x (1024x1024) and 4x (2048x2048) scaling.

Falls back to bilinear interpolation if Real-ESRGAN is not available.

Usage:
    upscaler = FrameUpscaler(scale=4)
    upscaler.load()  # Load Real-ESRGAN model
    big_frame = upscaler.upscale(small_frame)  # (512,512,4) -> (2048,2048,4)
    big_batch = upscaler.upscale_batch(frames)  # List of frames
"""

import logging
import numpy as np
from pathlib import Path

from . import config

logger = logging.getLogger("champ.avatar.upscale")

# Real-ESRGAN model URLs
REALESRGAN_MODELS = {
    "RealESRGAN_x4plus": {
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "filename": "RealESRGAN_x4plus.pth",
        "scale": 4,
    },
    "RealESRGAN_x2plus": {
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        "filename": "RealESRGAN_x2plus.pth",
        "scale": 2,
    },
}


class FrameUpscaler:
    """
    Upscales avatar frames using Real-ESRGAN or bilinear fallback.

    Args:
        scale: Upscale factor (2 or 4)
        model_dir: Directory containing Real-ESRGAN weights
    """

    def __init__(
        self,
        scale: int = config.VIDEO_UPSCALE_FACTOR,
        model_dir: str | Path | None = None,
    ):
        self.scale = scale
        self.model_dir = Path(model_dir) if model_dir else config.MODELS_DIR / "realesrgan"
        self._model = None
        self._available = False
        self._use_gpu = False

    def load(self) -> bool:
        """
        Load Real-ESRGAN model. Returns True if successful.
        Falls back to bilinear if unavailable.
        """
        try:
            import torch
            from basicsr.archs.rrdbnet_arch import RRDBNet
            from realesrgan import RealESRGANer

            # Select model based on scale
            if self.scale == 4:
                model_info = REALESRGAN_MODELS["RealESRGAN_x4plus"]
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                               num_block=23, num_grow_ch=32, scale=4)
            elif self.scale == 2:
                model_info = REALESRGAN_MODELS["RealESRGAN_x2plus"]
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                               num_block=23, num_grow_ch=32, scale=2)
            else:
                logger.warning(f"Unsupported scale {self.scale}, using bilinear")
                return False

            model_path = self.model_dir / model_info["filename"]
            if not model_path.exists():
                logger.warning(
                    f"Real-ESRGAN weights not found at {model_path}. "
                    f"Run: python -m avatar.setup to download."
                )
                return False

            # Determine device
            device = "cuda" if torch.cuda.is_available() else "cpu"
            half = device == "cuda"  # fp16 only on GPU

            self._model = RealESRGANer(
                scale=self.scale,
                model_path=str(model_path),
                model=model,
                tile=0,  # No tiling for small frames (512x512)
                tile_pad=10,
                pre_pad=0,
                half=half,
                device=device,
            )

            self._available = True
            self._use_gpu = device == "cuda"
            logger.info(
                f"Real-ESRGAN loaded ({self.scale}x, device={device}, "
                f"output={512*self.scale}x{512*self.scale})"
            )
            return True

        except ImportError as e:
            logger.info(f"Real-ESRGAN not available ({e}), using bilinear fallback")
            return False
        except Exception as e:
            logger.warning(f"Real-ESRGAN failed to load: {e}, using bilinear fallback")
            return False

    def upscale(self, frame: np.ndarray) -> np.ndarray:
        """
        Upscale a single frame.

        Args:
            frame: RGBA uint8, shape (H, W, 4)

        Returns:
            Upscaled RGBA uint8, shape (H*scale, W*scale, 4)
        """
        if self._available and self._model is not None:
            return self._upscale_realesrgan(frame)
        else:
            return self._upscale_bilinear(frame)

    def upscale_batch(self, frames: list[np.ndarray]) -> list[np.ndarray]:
        """Upscale a batch of frames."""
        return [self.upscale(f) for f in frames]

    def _upscale_realesrgan(self, frame: np.ndarray) -> np.ndarray:
        """Upscale using Real-ESRGAN model."""
        # Real-ESRGAN expects BGR uint8 without alpha
        has_alpha = frame.shape[2] == 4
        if has_alpha:
            rgb = frame[:, :, :3]
            alpha = frame[:, :, 3]
        else:
            rgb = frame

        # RGB -> BGR for Real-ESRGAN (OpenCV convention)
        bgr = rgb[:, :, ::-1]

        # Upscale
        output_bgr, _ = self._model.enhance(bgr, outscale=self.scale)

        # BGR -> RGB
        output_rgb = output_bgr[:, :, ::-1]

        # Restore alpha channel (upscale with bilinear)
        if has_alpha:
            from PIL import Image
            alpha_pil = Image.fromarray(alpha)
            new_h, new_w = output_rgb.shape[:2]
            alpha_upscaled = np.array(alpha_pil.resize((new_w, new_h), Image.LANCZOS))
            output_rgba = np.concatenate(
                [output_rgb, alpha_upscaled[:, :, np.newaxis]], axis=2
            )
            return output_rgba
        else:
            return output_rgb

    def _upscale_bilinear(self, frame: np.ndarray) -> np.ndarray:
        """Fallback: upscale using PIL bilinear interpolation."""
        from PIL import Image

        h, w = frame.shape[:2]
        new_h, new_w = h * self.scale, w * self.scale

        if frame.shape[2] == 4:
            mode = "RGBA"
        else:
            mode = "RGB"

        pil_img = Image.fromarray(frame, mode=mode)
        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
        return np.array(pil_img)

    @property
    def available(self) -> bool:
        """True if Real-ESRGAN is loaded (not bilinear fallback)."""
        return self._available

    @property
    def output_size(self) -> tuple[int, int]:
        """Output dimensions for current scale factor."""
        return (config.VIDEO_WIDTH * self.scale, config.VIDEO_HEIGHT * self.scale)
