"""
CHAMP Avatar — Gaussian Splat Pipeline (Phase 7)

3D Gaussian Splatting avatar creation and animation:

  train_splat.py              — 2-min video → FLAME-rigged 3DGS via GaussianAvatars
  motion_driver.py            — Apply 52 blendshapes + head pose to rigged Gaussians
  instant_preview.py          — Single image → 3DGS preview in seconds (FaceLift)
  virtual_capture_studio.py   — 3 photos → 96 synthetic views (replaces camera rig)
  splat_export.py             — Export .ply/.splat for browser-side gsplat.js
  personalive_renderer.py     — Zero-training instant avatar via PersonaLive

The pipeline:
  3 selfies → Virtual Capture Studio (96 views) → GaussianAvatars training
  → FLAME-rigged 3DGS → audio-driven motion → WebRTC DataChannel → browser rendering

Alternative (zero-training):
  1 selfie → PersonaLive → instant streaming avatar (server GPU, 2D, 10-30 FPS)
"""

from .train_splat import SplatTrainer, SplatTrainingConfig, SplatTrainingResult
from .motion_driver import SplatMotionDriver, MotionFrame
from .instant_preview import InstantPreviewGenerator
from .virtual_capture_studio import VirtualCaptureStudio, CaptureResult
from .splat_export import SplatExporter, ExportFormat
from .personalive_renderer import PersonaLiveRenderer, PersonaLiveConfig

__all__ = [
    "SplatTrainer",
    "SplatTrainingConfig",
    "SplatTrainingResult",
    "SplatMotionDriver",
    "MotionFrame",
    "InstantPreviewGenerator",
    "VirtualCaptureStudio",
    "CaptureResult",
    "SplatExporter",
    "ExportFormat",
    "PersonaLiveRenderer",
    "PersonaLiveConfig",
]
