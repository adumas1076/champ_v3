"""
CHAMP Avatar — Instant 3DGS Preview

Generates a 3D Gaussian Splat preview from a single photo in seconds.

Two approaches (tried in order):
  1. FaceLift (ICCV 2025): 1 photo → 6 views → 3DGS head (~3-10 seconds)
  2. Placeholder: Generates a minimal splat from face landmarks

This instant preview is shown to the user immediately while the full
GaussianAvatars training runs in background (20-60 minutes).

The preview splat is REPLACED by the production splat when training completes.

Flow:
  User uploads selfie → InstantPreviewGenerator → preview.ply (3 seconds)
  Meanwhile: VirtualCaptureStudio + SplatTrainer → splat.ply (20-60 min)
  When training done: splat.ply replaces preview.ply

Wraps: FaceLift (https://github.com/...)
"""

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

from .. import config

logger = logging.getLogger("champ.avatar.splat.instant_preview")


class InstantPreviewGenerator:
    """
    Generates an instant 3DGS preview from a single photo.

    Usage:
        gen = InstantPreviewGenerator()
        preview_path = gen.generate(
            image_path="selfie.jpg",
            avatar_id="anthony",
        )
        # Returns path to preview.ply in ~3-10 seconds
    """

    def __init__(self, output_dir: str | Path | None = None):
        self.output_dir = Path(output_dir) if output_dir else config.AVATARS_DIR
        self._facelift_available = self._check_facelift()

    def _check_facelift(self) -> bool:
        """Check if FaceLift repo is available."""
        fl_dir = config.FACELIFT_DIR
        if not fl_dir.exists():
            logger.info(
                f"FaceLift not found at {fl_dir}. "
                f"Instant preview will use placeholder generation."
            )
            return False
        return True

    def generate(
        self,
        image_path: str,
        avatar_id: str,
        timeout_sec: int = config.INSTANT_PREVIEW_TIMEOUT_SEC,
    ) -> str:
        """
        Generate instant 3DGS preview from a single photo.

        Args:
            image_path: Path to selfie/headshot image
            avatar_id: Avatar identifier
            timeout_sec: Maximum time to wait for generation

        Returns:
            Path to preview.ply file
        """
        start_time = time.time()
        avatar_dir = self.output_dir / avatar_id
        splat_dir = avatar_dir / config.SPLAT_DIR_NAME
        splat_dir.mkdir(parents=True, exist_ok=True)
        preview_path = splat_dir / "preview.ply"

        if self._facelift_available:
            try:
                result = self._generate_facelift(image_path, preview_path, timeout_sec)
                elapsed = time.time() - start_time
                logger.info(f"FaceLift preview generated in {elapsed:.1f}s → {result}")
                return result
            except Exception as e:
                logger.warning(f"FaceLift failed ({e}), falling back to placeholder")

        # Placeholder generation
        result = self._generate_placeholder(image_path, preview_path)
        elapsed = time.time() - start_time
        logger.info(f"Placeholder preview generated in {elapsed:.1f}s → {result}")
        return result

    def _generate_facelift(
        self, image_path: str, output_path: Path, timeout_sec: int
    ) -> str:
        """Generate preview using FaceLift."""
        fl_dir = config.FACELIFT_DIR

        # FaceLift expected interface:
        # python run.py --input image.jpg --output preview.ply
        cmd = [
            sys.executable,
            str(fl_dir / "run.py"),
            "--input", str(image_path),
            "--output", str(output_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=str(fl_dir),
            )

            if result.returncode != 0:
                raise RuntimeError(f"FaceLift failed: {result.stderr}")

            if not output_path.exists():
                raise RuntimeError("FaceLift did not produce output file")

            return str(output_path)

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"FaceLift timed out after {timeout_sec}s")

    def _generate_placeholder(self, image_path: str, output_path: Path) -> str:
        """
        Generate a placeholder 3DGS from face landmarks.

        Creates a simple head-shaped Gaussian cloud that approximates
        the face from the photo. Good enough for instant feedback.
        """
        # Detect face region for color sampling
        face_colors = self._sample_face_colors(image_path)

        # Generate head-shaped Gaussian cloud
        num_gaussians = 2000
        positions, colors, scales, rotations, opacities = self._generate_head_cloud(
            num_gaussians, face_colors
        )

        # Write PLY
        self._write_splat_ply(
            output_path, positions, colors, scales, rotations, opacities
        )

        return str(output_path)

    def _sample_face_colors(self, image_path: str) -> np.ndarray:
        """Sample skin/hair colors from the face region of an image."""
        try:
            from PIL import Image
            img = Image.open(image_path).convert("RGB")
            img_array = np.array(img)

            # Simple center crop for face region (face is usually centered in selfies)
            h, w = img_array.shape[:2]
            face_region = img_array[
                int(h * 0.2):int(h * 0.8),
                int(w * 0.25):int(w * 0.75),
            ]

            # Sample random colors from face region
            flat = face_region.reshape(-1, 3)
            indices = np.random.choice(len(flat), min(100, len(flat)), replace=False)
            return flat[indices].astype(np.float32) / 255.0

        except Exception:
            # Default skin-tone palette
            return np.array([
                [0.85, 0.72, 0.62],
                [0.78, 0.65, 0.55],
                [0.90, 0.78, 0.68],
                [0.30, 0.22, 0.18],  # Hair
                [0.20, 0.15, 0.12],  # Hair dark
            ], dtype=np.float32)

    def _generate_head_cloud(
        self, num_gaussians: int, face_colors: np.ndarray
    ) -> tuple:
        """Generate Gaussians arranged in a rough head shape."""
        # Ellipsoid head shape parameters
        head_rx, head_ry, head_rz = 0.12, 0.15, 0.12

        # Generate positions on/in ellipsoid
        positions = np.zeros((num_gaussians, 3), dtype=np.float32)

        # Face region (front 60% of Gaussians)
        n_face = int(num_gaussians * 0.6)
        theta = np.random.uniform(-0.4 * np.pi, 0.4 * np.pi, n_face)
        phi = np.random.uniform(-0.5 * np.pi, 0.5 * np.pi, n_face)
        r = np.random.uniform(0.85, 1.0, n_face)
        positions[:n_face, 0] = r * head_rx * np.sin(theta) * np.cos(phi)
        positions[:n_face, 1] = r * head_ry * np.sin(phi)
        positions[:n_face, 2] = r * head_rz * np.cos(theta) * np.cos(phi)

        # Hair region (back/top 25%)
        n_hair = int(num_gaussians * 0.25)
        theta = np.random.uniform(0.3 * np.pi, 1.7 * np.pi, n_hair)
        phi = np.random.uniform(-0.3 * np.pi, 0.7 * np.pi, n_hair)
        r = np.random.uniform(0.95, 1.15, n_hair)
        start = n_face
        positions[start:start + n_hair, 0] = r * head_rx * 1.1 * np.sin(theta) * np.cos(phi)
        positions[start:start + n_hair, 1] = r * head_ry * 1.05 * np.sin(phi)
        positions[start:start + n_hair, 2] = r * head_rz * 1.1 * np.cos(theta) * np.cos(phi)

        # Neck region (bottom 15%)
        n_neck = num_gaussians - n_face - n_hair
        start = n_face + n_hair
        neck_y = np.random.uniform(-0.22, -0.12, n_neck)
        neck_r = np.random.uniform(0.04, 0.07, n_neck)
        neck_theta = np.random.uniform(0, 2 * np.pi, n_neck)
        positions[start:, 0] = neck_r * np.cos(neck_theta)
        positions[start:, 1] = neck_y
        positions[start:, 2] = neck_r * np.sin(neck_theta)

        # Colors — sample from face colors palette
        color_indices = np.random.randint(0, len(face_colors), num_gaussians)
        # Hair gets darker colors
        dark_indices = np.where(face_colors.mean(axis=1) < 0.4)[0]
        if len(dark_indices) > 0:
            color_indices[n_face:n_face + n_hair] = np.random.choice(
                dark_indices, n_hair
            )

        # Convert RGB to SH DC coefficients (c = (color - 0.5) / 0.2822)
        colors_rgb = face_colors[color_indices]
        colors_sh = (colors_rgb - 0.5) / 0.2822

        # Scales (log space) — small for detail
        scales = np.full((num_gaussians, 3), -4.0, dtype=np.float32)
        scales += np.random.randn(num_gaussians, 3).astype(np.float32) * 0.3

        # Rotations (quaternion) — mostly identity with slight variation
        rotations = np.zeros((num_gaussians, 4), dtype=np.float32)
        rotations[:, 0] = 1.0  # w component
        rotations += np.random.randn(num_gaussians, 4).astype(np.float32) * 0.05
        # Normalize quaternions
        norms = np.linalg.norm(rotations, axis=1, keepdims=True)
        rotations /= np.maximum(norms, 1e-8)

        # Opacities (sigmoid space)
        opacities = np.full(num_gaussians, 2.0, dtype=np.float32)  # sigmoid(2) ≈ 0.88

        return positions, colors_sh, scales, rotations, opacities

    def _write_splat_ply(
        self,
        path: Path,
        positions: np.ndarray,
        colors: np.ndarray,
        scales: np.ndarray,
        rotations: np.ndarray,
        opacities: np.ndarray,
    ):
        """Write Gaussian Splat PLY file in standard 3DGS format."""
        num = len(positions)

        header = f"""ply
format binary_little_endian 1.0
element vertex {num}
property float x
property float y
property float z
property float nx
property float ny
property float nz
property float f_dc_0
property float f_dc_1
property float f_dc_2
property float opacity
property float scale_0
property float scale_1
property float scale_2
property float rot_0
property float rot_1
property float rot_2
property float rot_3
end_header
"""

        with open(path, "wb") as f:
            f.write(header.encode("ascii"))

            normals = np.zeros((num, 3), dtype=np.float32)

            for i in range(num):
                f.write(positions[i].tobytes())
                f.write(normals[i].tobytes())
                f.write(colors[i].astype(np.float32).tobytes())
                f.write(np.float32(opacities[i]).tobytes())
                f.write(scales[i].tobytes())
                f.write(rotations[i].tobytes())

    @property
    def available(self) -> bool:
        """True if FaceLift is available (not just placeholder)."""
        return self._facelift_available
