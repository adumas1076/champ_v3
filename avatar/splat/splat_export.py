"""
CHAMP Avatar — Splat Export

Exports 3D Gaussian Splat models for browser-side rendering via gsplat.js.

Two export formats:
  1. PLY — Standard 3DGS format (larger, universal)
  2. SPLAT — Compressed format (smaller, optimized for web)

Also handles:
  - Size validation (max 200MB for browser delivery)
  - Gaussian pruning (remove low-opacity Gaussians to reduce size)
  - Compression for faster download
  - Metadata embedding for client-side rendering hints
"""

import gzip
import json
import logging
import os
import struct
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

from .. import config

logger = logging.getLogger("champ.avatar.splat.export")


class ExportFormat(Enum):
    """Export format for browser delivery."""
    PLY = "ply"                # Standard 3DGS PLY (larger, universal)
    SPLAT = "splat"            # Compressed web format (smaller, faster load)
    COMPRESSED_PLY = "ply.gz"  # Gzipped PLY (good compression, broad support)


# Standard PLY properties for 3DGS
PLY_PROPERTIES = [
    ("x", "float"), ("y", "float"), ("z", "float"),
    ("nx", "float"), ("ny", "float"), ("nz", "float"),
    ("f_dc_0", "float"), ("f_dc_1", "float"), ("f_dc_2", "float"),
    ("opacity", "float"),
    ("scale_0", "float"), ("scale_1", "float"), ("scale_2", "float"),
    ("rot_0", "float"), ("rot_1", "float"), ("rot_2", "float"), ("rot_3", "float"),
]

# Bytes per Gaussian in PLY format
BYTES_PER_GAUSSIAN_PLY = len(PLY_PROPERTIES) * 4  # 17 floats × 4 bytes = 68 bytes

# Bytes per Gaussian in compressed SPLAT format
# Position (3×4) + Color (4×1) + Scale (3×2) + Rotation (4×1) = 26 bytes
BYTES_PER_GAUSSIAN_SPLAT = 26


class SplatExporter:
    """
    Exports Gaussian Splat models for browser rendering.

    Usage:
        exporter = SplatExporter()

        # Export for web delivery
        web_path = exporter.export_for_web(
            splat_path="models/avatars/anthony/splat/splat.ply",
            output_path="exports/anthony.splat",
            format=ExportFormat.SPLAT,
        )

        # Get metadata for client
        meta = exporter.get_client_metadata("models/avatars/anthony/splat/splat.ply")
        # → {"num_gaussians": 150000, "file_size_mb": 3.8, "format": "splat", ...}
    """

    def export_for_web(
        self,
        splat_path: str,
        output_path: Optional[str] = None,
        format: ExportFormat = ExportFormat.SPLAT,
        max_gaussians: Optional[int] = None,
        prune_opacity_threshold: float = 0.005,
    ) -> str:
        """
        Export splat file optimized for browser delivery.

        Args:
            splat_path: Path to source .ply splat file
            output_path: Output path (auto-generated if None)
            format: Export format (PLY, SPLAT, or COMPRESSED_PLY)
            max_gaussians: Max Gaussians to keep (prunes by opacity if exceeded)
            prune_opacity_threshold: Remove Gaussians with opacity below this

        Returns:
            Path to exported file
        """
        source = Path(splat_path)
        if not source.exists():
            raise FileNotFoundError(f"Splat file not found: {splat_path}")

        # Read source PLY
        gaussians = self._read_ply(source)
        original_count = len(gaussians["positions"])

        # Prune low-opacity Gaussians
        gaussians = self._prune_by_opacity(gaussians, prune_opacity_threshold)

        # Limit Gaussian count if needed
        if max_gaussians and len(gaussians["positions"]) > max_gaussians:
            gaussians = self._prune_to_count(gaussians, max_gaussians)

        pruned_count = len(gaussians["positions"])
        if pruned_count < original_count:
            logger.info(
                f"Pruned: {original_count} → {pruned_count} Gaussians "
                f"({pruned_count/original_count*100:.1f}%)"
            )

        # Generate output path
        if output_path is None:
            suffix = f".{format.value}"
            output_path = str(source.with_suffix(suffix))

        # Export in requested format
        if format == ExportFormat.PLY:
            self._write_ply(output_path, gaussians)
        elif format == ExportFormat.SPLAT:
            self._write_splat(output_path, gaussians)
        elif format == ExportFormat.COMPRESSED_PLY:
            self._write_compressed_ply(output_path, gaussians)

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)

        if file_size_mb > config.SPLAT_MAX_FILE_SIZE_MB:
            logger.warning(
                f"Exported file ({file_size_mb:.1f}MB) exceeds "
                f"max size ({config.SPLAT_MAX_FILE_SIZE_MB}MB). "
                f"Consider increasing pruning or reducing max_gaussians."
            )

        logger.info(
            f"Exported: {format.value} → {output_path} "
            f"({pruned_count} Gaussians, {file_size_mb:.1f}MB)"
        )

        return output_path

    def get_client_metadata(self, splat_path: str) -> dict:
        """
        Get metadata for the browser client to use when loading the splat.

        Returns dict with rendering hints, file info, and configuration.
        """
        source = Path(splat_path)
        if not source.exists():
            return {"error": f"File not found: {splat_path}"}

        file_size_bytes = os.path.getsize(splat_path)
        gaussians = self._read_ply(source)
        num_gaussians = len(gaussians["positions"])

        # Compute bounding box
        positions = gaussians["positions"]
        bbox_min = positions.min(axis=0).tolist()
        bbox_max = positions.max(axis=0).tolist()
        center = ((positions.min(axis=0) + positions.max(axis=0)) / 2).tolist()

        return {
            "num_gaussians": num_gaussians,
            "file_size_bytes": file_size_bytes,
            "file_size_mb": round(file_size_bytes / (1024 * 1024), 2),
            "format": "ply",
            "bbox_min": bbox_min,
            "bbox_max": bbox_max,
            "center": center,
            "sh_degree": config.SPLAT_SH_DEGREE,
            "recommended_camera_distance": max(
                bbox_max[i] - bbox_min[i] for i in range(3)
            ) * 2.0,
            "motion_frame_rate": config.MOTION_FRAME_RATE,
            "motion_frame_bytes": config.MOTION_FRAME_BYTES,
        }

    def validate_for_web(self, splat_path: str) -> dict:
        """
        Validate a splat file for browser delivery.

        Returns dict with validation results and recommendations.
        """
        issues = []
        recommendations = []

        source = Path(splat_path)
        if not source.exists():
            return {"valid": False, "issues": ["File not found"]}

        file_size_mb = os.path.getsize(splat_path) / (1024 * 1024)

        # Size check
        if file_size_mb > config.SPLAT_MAX_FILE_SIZE_MB:
            issues.append(
                f"File size ({file_size_mb:.1f}MB) exceeds limit "
                f"({config.SPLAT_MAX_FILE_SIZE_MB}MB)"
            )
            recommendations.append("Prune low-opacity Gaussians or reduce max_gaussians")

        # Read and validate
        try:
            gaussians = self._read_ply(source)
            num = len(gaussians["positions"])

            if num > 500_000:
                recommendations.append(
                    f"High Gaussian count ({num:,}). "
                    f"Consider pruning for faster mobile rendering."
                )

            # Check for NaN/Inf
            for key, arr in gaussians.items():
                if isinstance(arr, np.ndarray) and arr.dtype in (np.float32, np.float64):
                    if np.any(np.isnan(arr)) or np.any(np.isinf(arr)):
                        issues.append(f"NaN/Inf values in {key}")

        except Exception as e:
            issues.append(f"Failed to read PLY: {e}")

        return {
            "valid": len(issues) == 0,
            "file_size_mb": round(file_size_mb, 2),
            "num_gaussians": num if "num" in dir() else 0,
            "issues": issues,
            "recommendations": recommendations,
        }

    # ─── Internal: PLY Read/Write ───────────────────────────────────────────

    def _read_ply(self, path: Path) -> dict:
        """Read a 3DGS PLY file into component arrays."""
        with open(path, "rb") as f:
            # Parse header
            header_lines = []
            while True:
                line = f.readline().decode("ascii").strip()
                header_lines.append(line)
                if line == "end_header":
                    break

            # Extract vertex count
            num_vertices = 0
            properties = []
            for line in header_lines:
                if line.startswith("element vertex"):
                    num_vertices = int(line.split()[-1])
                elif line.startswith("property"):
                    parts = line.split()
                    properties.append((parts[2], parts[1]))  # (name, type)

            if num_vertices == 0:
                return {
                    "positions": np.zeros((0, 3), dtype=np.float32),
                    "normals": np.zeros((0, 3), dtype=np.float32),
                    "colors_sh": np.zeros((0, 3), dtype=np.float32),
                    "opacities": np.zeros(0, dtype=np.float32),
                    "scales": np.zeros((0, 3), dtype=np.float32),
                    "rotations": np.zeros((0, 4), dtype=np.float32),
                }

            # Read binary data
            bytes_per_vertex = len(properties) * 4  # Assume all float32
            data = f.read(num_vertices * bytes_per_vertex)

        # Parse into arrays
        all_data = np.frombuffer(data, dtype=np.float32).reshape(num_vertices, -1)

        # Standard 3DGS layout: x,y,z, nx,ny,nz, f_dc_0..2, opacity, scale_0..2, rot_0..3
        result = {
            "positions": all_data[:, 0:3].copy(),
            "normals": all_data[:, 3:6].copy(),
            "colors_sh": all_data[:, 6:9].copy(),
            "opacities": all_data[:, 9].copy(),
            "scales": all_data[:, 10:13].copy(),
            "rotations": all_data[:, 13:17].copy(),
        }

        return result

    def _write_ply(self, path: str, gaussians: dict):
        """Write Gaussians to standard PLY format."""
        num = len(gaussians["positions"])

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

            # Concatenate all properties and write as single block
            data = np.column_stack([
                gaussians["positions"],
                gaussians["normals"],
                gaussians["colors_sh"],
                gaussians["opacities"].reshape(-1, 1),
                gaussians["scales"],
                gaussians["rotations"],
            ]).astype(np.float32)

            f.write(data.tobytes())

    def _write_splat(self, path: str, gaussians: dict):
        """
        Write in compressed .splat format for web delivery.

        Format per Gaussian (26 bytes):
          Position: 3 × float32 (12 bytes)
          Color: 4 × uint8 — RGBA (4 bytes)
          Scale: 3 × float16 (6 bytes)
          Rotation: 4 × uint8 — quantized quaternion (4 bytes)
        """
        num = len(gaussians["positions"])

        with open(path, "wb") as f:
            for i in range(num):
                # Position (3 × float32 = 12 bytes)
                f.write(gaussians["positions"][i].astype(np.float32).tobytes())

                # Color: SH DC to RGB, then to uint8 RGBA
                sh_dc = gaussians["colors_sh"][i]
                rgb = np.clip((sh_dc * 0.2822 + 0.5) * 255, 0, 255).astype(np.uint8)
                opacity_sigmoid = 1.0 / (1.0 + np.exp(-gaussians["opacities"][i]))
                alpha = np.uint8(np.clip(opacity_sigmoid * 255, 0, 255))
                f.write(rgb.tobytes())
                f.write(alpha.tobytes())

                # Scale (3 × float16 = 6 bytes)
                f.write(gaussians["scales"][i].astype(np.float16).tobytes())

                # Rotation quaternion quantized to uint8 (4 bytes)
                rot = gaussians["rotations"][i]
                rot_norm = rot / (np.linalg.norm(rot) + 1e-8)
                rot_uint8 = np.clip((rot_norm + 1.0) * 127.5, 0, 255).astype(np.uint8)
                f.write(rot_uint8.tobytes())

    def _write_compressed_ply(self, path: str, gaussians: dict):
        """Write gzipped PLY for faster download."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ply", delete=False) as tmp:
            tmp_path = tmp.name

        self._write_ply(tmp_path, gaussians)

        with open(tmp_path, "rb") as f_in:
            with gzip.open(path, "wb", compresslevel=6) as f_out:
                f_out.write(f_in.read())

        os.unlink(tmp_path)

    def _prune_by_opacity(self, gaussians: dict, threshold: float) -> dict:
        """Remove Gaussians with opacity below threshold."""
        # Convert from logit space to probability
        opacities_prob = 1.0 / (1.0 + np.exp(-gaussians["opacities"]))
        mask = opacities_prob >= threshold

        return {
            key: arr[mask] if isinstance(arr, np.ndarray) else arr
            for key, arr in gaussians.items()
        }

    def _prune_to_count(self, gaussians: dict, max_count: int) -> dict:
        """Keep only the top max_count Gaussians by opacity."""
        opacities = gaussians["opacities"]
        if len(opacities) <= max_count:
            return gaussians

        # Sort by opacity (descending) and keep top N
        top_indices = np.argsort(opacities)[-max_count:]

        return {
            key: arr[top_indices] if isinstance(arr, np.ndarray) else arr
            for key, arr in gaussians.items()
        }
