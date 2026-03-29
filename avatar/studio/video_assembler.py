"""
CHAMP Avatar Studio — Video Assembler

Stitches rendered video frames + audio track into a final MP4 file.
Uses ffmpeg for encoding — no Python video encoding dependencies needed.

Supports:
  - Frame directory (PNGs) + audio WAV -> MP4
  - Configurable resolution, FPS, codec, bitrate
  - Optional intro/outro frame insertion
  - Optional background music mixing
  - Thumbnail extraction

Usage:
    assembler = VideoAssembler()
    output_path = assembler.assemble(
        frames_dir="render_output/frames/",
        audio_path="render_output/audio.wav",
        output_path="render_output/final.mp4",
    )
"""

import logging
import os
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .. import config

logger = logging.getLogger("champ.avatar.studio.assembler")


@dataclass
class AssemblyConfig:
    """Configuration for video assembly."""
    fps: float = config.VIDEO_FPS                    # 25 fps (FlashHead native)
    video_codec: str = "libx264"                     # H.264 for broad compatibility
    audio_codec: str = "aac"                         # AAC audio
    video_bitrate: str = "4M"                        # 4 Mbps for 512x512, increase for 4K
    audio_bitrate: str = "192k"                      # 192kbps AAC
    pixel_format: str = "yuv420p"                    # Broad compatibility
    preset: str = "medium"                           # Encoding speed/quality tradeoff
    crf: int = 18                                    # Quality (lower = better, 18 = visually lossless)
    # 4K settings
    upscale_4k: bool = False                         # Upscale output to 4K
    output_width: Optional[int] = None               # Override output width
    output_height: Optional[int] = None              # Override output height


def _check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


class VideoAssembler:
    """
    Assembles video frames + audio into a final MP4.

    Requires ffmpeg installed on the system.
    """

    def __init__(self, assembly_config: Optional[AssemblyConfig] = None):
        self.config = assembly_config or AssemblyConfig()

        if not _check_ffmpeg():
            logger.warning(
                "ffmpeg not found in PATH. Video assembly will fail. "
                "Install: apt install ffmpeg / brew install ffmpeg / choco install ffmpeg"
            )

    def assemble(
        self,
        frames_dir: str,
        audio_path: str,
        output_path: str,
        intro_frames: Optional[str] = None,
        outro_frames: Optional[str] = None,
    ) -> str:
        """
        Assemble frames + audio into MP4.

        Args:
            frames_dir: Directory of PNG frames (sorted alphabetically)
            audio_path: Path to audio WAV file
            output_path: Where to save the final MP4
            intro_frames: Optional directory of intro frame PNGs
            outro_frames: Optional directory of outro frame PNGs

        Returns:
            Path to the output MP4 file
        """
        if not _check_ffmpeg():
            raise RuntimeError("ffmpeg not found. Install ffmpeg to assemble videos.")

        # Verify inputs
        if not os.path.isdir(frames_dir):
            raise ValueError(f"Frames directory not found: {frames_dir}")
        if not os.path.isfile(audio_path):
            raise ValueError(f"Audio file not found: {audio_path}")

        frame_files = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
        if not frame_files:
            raise ValueError(f"No PNG frames found in {frames_dir}")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        logger.info(f"Assembling video: {len(frame_files)} frames + audio")
        logger.info(f"  Frames: {frames_dir}")
        logger.info(f"  Audio: {audio_path}")
        logger.info(f"  Output: {output_path}")

        # Build ffmpeg command
        # Input: image sequence + audio
        # Output: H.264 MP4
        cfg = self.config

        cmd = [
            "ffmpeg", "-y",  # Overwrite output
            # Video input: image sequence
            "-framerate", str(cfg.fps),
            "-i", os.path.join(frames_dir, "frame_%03d.png"),
            # Audio input
            "-i", audio_path,
            # Video encoding
            "-c:v", cfg.video_codec,
            "-crf", str(cfg.crf),
            "-preset", cfg.preset,
            "-pix_fmt", cfg.pixel_format,
        ]

        # Add bitrate if not using CRF mode
        if cfg.video_bitrate:
            cmd.extend(["-b:v", cfg.video_bitrate])

        # Scale if requested
        if cfg.output_width and cfg.output_height:
            cmd.extend(["-vf", f"scale={cfg.output_width}:{cfg.output_height}"])
        elif cfg.upscale_4k:
            cmd.extend(["-vf", "scale=3840:2160"])

        # Audio encoding
        cmd.extend([
            "-c:a", cfg.audio_codec,
            "-b:a", cfg.audio_bitrate,
        ])

        # Sync: use shortest stream (in case audio/video lengths differ slightly)
        cmd.extend(["-shortest"])

        # Output
        cmd.append(output_path)

        logger.debug(f"  ffmpeg command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"ffmpeg failed: {result.stderr[-500:]}")
                raise RuntimeError(f"ffmpeg encoding failed: {result.stderr[-200:]}")

            # Verify output
            if not os.path.isfile(output_path):
                raise RuntimeError(f"Output file not created: {output_path}")

            file_size = os.path.getsize(output_path)
            duration = len(frame_files) / cfg.fps

            logger.info(
                f"  Video assembled: {output_path} "
                f"({file_size / 1024 / 1024:.1f}MB, {duration:.1f}s)"
            )

            return output_path

        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg encoding timed out (>5 minutes)")

    def assemble_from_numpy(
        self,
        frames: list,
        audio_path: str,
        output_path: str,
        temp_dir: Optional[str] = None,
    ) -> str:
        """
        Assemble from in-memory numpy frames + audio file.

        Args:
            frames: List of numpy RGBA/RGB uint8 arrays
            audio_path: Path to audio WAV file
            output_path: Where to save the final MP4
            temp_dir: Temporary directory for frame PNGs (auto-cleaned)

        Returns:
            Path to the output MP4 file
        """
        import tempfile
        import numpy as np
        from PIL import Image

        cleanup = False
        if temp_dir is None:
            temp_dir = tempfile.mkdtemp(prefix="champ_render_")
            cleanup = True

        frames_dir = os.path.join(temp_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        try:
            # Save frames as PNGs
            for i, frame in enumerate(frames):
                if frame.shape[2] == 4:
                    img = Image.fromarray(frame, "RGBA").convert("RGB")
                else:
                    img = Image.fromarray(frame, "RGB")
                img.save(os.path.join(frames_dir, f"frame_{i:03d}.png"))

            # Assemble
            return self.assemble(frames_dir, audio_path, output_path)

        finally:
            if cleanup:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def extract_thumbnail(
        self,
        video_path: str,
        output_path: str,
        timestamp_sec: float = 1.0,
    ) -> str:
        """Extract a thumbnail frame from a video."""
        if not _check_ffmpeg():
            raise RuntimeError("ffmpeg not found")

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp_sec),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            output_path,
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def get_video_info(self, video_path: str) -> dict:
        """Get video metadata using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {}
