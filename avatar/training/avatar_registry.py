"""
CHAMP Avatar Training — Avatar Registry

Manages stored avatar reference data:
  - Create new avatar from video or image
  - List available avatars
  - Load avatar reference path for FlashHead
  - Store metadata (name, source, frame count, creation date)

Each avatar is stored as:
    models/avatars/{avatar_id}/
        metadata.json       — name, source video, frame count, created date
        frames/             — extracted keyframes (PNGs)
        reference.png       — single best reference frame (fallback)
"""

import json
import logging
import os
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .. import config

logger = logging.getLogger("champ.avatar.training.registry")


@dataclass
class AvatarMetadata:
    avatar_id: str
    name: str
    source_type: str              # "video" or "image"
    source_path: Optional[str]    # Original file path
    frame_count: int              # Number of keyframes extracted
    created_at: str               # ISO timestamp
    reference_image: str          # Path to best single reference frame
    frames_dir: Optional[str]     # Path to keyframes directory (None if single image)
    # Phase 7: Gaussian Splat fields
    splat_path: Optional[str] = None         # Path to .ply splat file
    splat_preview_path: Optional[str] = None # Path to instant preview .ply
    splat_status: str = "none"               # "none", "preview", "training", "ready"
    num_gaussians: int = 0                   # Total Gaussians in splat model
    synthetic_views_dir: Optional[str] = None  # Virtual Capture Studio output


class AvatarRegistry:
    """Manages avatar reference data on disk."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else config.AVATARS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def list_avatars(self) -> list[AvatarMetadata]:
        """List all registered avatars."""
        avatars = []
        for entry in sorted(self.base_dir.iterdir()):
            if entry.is_dir():
                meta = self._load_metadata(entry.name)
                if meta:
                    avatars.append(meta)
        return avatars

    def get_avatar(self, avatar_id: str) -> Optional[AvatarMetadata]:
        """Get metadata for a specific avatar."""
        return self._load_metadata(avatar_id)

    def get_reference_path(self, avatar_id: str) -> str:
        """
        Get the reference path for FlashHead.
        Returns frames directory if multi-reference, single image otherwise.
        FlashHead's get_base_data() accepts both file and directory.
        """
        meta = self._load_metadata(avatar_id)
        if meta is None:
            raise ValueError(f"Avatar not found: {avatar_id}")

        # Prefer multi-reference frames directory
        if meta.frames_dir and os.path.isdir(meta.frames_dir):
            frame_files = [f for f in os.listdir(meta.frames_dir) if f.endswith(".png")]
            if len(frame_files) > 0:
                return meta.frames_dir

        # Fallback to single reference image
        return meta.reference_image

    def create_from_video(
        self,
        video_path: str,
        avatar_id: str,
        name: str = "",
        **extract_kwargs,
    ) -> AvatarMetadata:
        """
        Create a new avatar from a 2-minute reference video.
        Extracts keyframes and registers the avatar.
        """
        from .extract_keyframes import extract_keyframes

        avatar_dir = self.base_dir / avatar_id
        frames_dir = avatar_dir / "frames"

        if avatar_dir.exists():
            logger.warning(f"Avatar '{avatar_id}' already exists, overwriting")
            shutil.rmtree(avatar_dir)

        frames_dir.mkdir(parents=True, exist_ok=True)

        # Extract keyframes
        logger.info(f"Extracting keyframes for avatar '{avatar_id}'...")
        frame_paths = extract_keyframes(
            video_path=video_path,
            output_dir=str(frames_dir),
            **extract_kwargs,
        )

        # Pick best frame as single reference (first = highest quality from front cluster)
        reference_image = frame_paths[0] if frame_paths else video_path

        # Save metadata
        meta = AvatarMetadata(
            avatar_id=avatar_id,
            name=name or avatar_id,
            source_type="video",
            source_path=os.path.abspath(video_path),
            frame_count=len(frame_paths),
            created_at=datetime.now().isoformat(),
            reference_image=str(reference_image),
            frames_dir=str(frames_dir),
        )
        self._save_metadata(meta)

        logger.info(
            f"Avatar '{avatar_id}' created: "
            f"{len(frame_paths)} keyframes from {video_path}"
        )
        return meta

    def create_from_image(
        self,
        image_path: str,
        avatar_id: str,
        name: str = "",
    ) -> AvatarMetadata:
        """
        Create a new avatar from a single reference image.
        No keyframe extraction — just copies the image.
        """
        avatar_dir = self.base_dir / avatar_id
        avatar_dir.mkdir(parents=True, exist_ok=True)

        # Copy image to avatar directory
        dest = avatar_dir / "reference.png"
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        img = img.resize((config.VIDEO_WIDTH, config.VIDEO_HEIGHT), Image.LANCZOS)
        img.save(str(dest))

        meta = AvatarMetadata(
            avatar_id=avatar_id,
            name=name or avatar_id,
            source_type="image",
            source_path=os.path.abspath(image_path),
            frame_count=1,
            created_at=datetime.now().isoformat(),
            reference_image=str(dest),
            frames_dir=None,
        )
        self._save_metadata(meta)

        logger.info(f"Avatar '{avatar_id}' created from image: {image_path}")
        return meta

    def update_splat_status(
        self,
        avatar_id: str,
        status: str,
        splat_path: Optional[str] = None,
        preview_path: Optional[str] = None,
        num_gaussians: int = 0,
        synthetic_views_dir: Optional[str] = None,
    ) -> Optional[AvatarMetadata]:
        """
        Update the Gaussian Splat status for an avatar.

        Status progression: none → preview → training → ready
        """
        meta = self._load_metadata(avatar_id)
        if meta is None:
            logger.warning(f"Avatar '{avatar_id}' not found for splat update")
            return None

        meta.splat_status = status
        if splat_path:
            meta.splat_path = splat_path
        if preview_path:
            meta.splat_preview_path = preview_path
        if num_gaussians:
            meta.num_gaussians = num_gaussians
        if synthetic_views_dir:
            meta.synthetic_views_dir = synthetic_views_dir

        self._save_metadata(meta)
        logger.info(f"Avatar '{avatar_id}' splat status → {status}")
        return meta

    def get_splat_path(self, avatar_id: str) -> Optional[str]:
        """
        Get the best available splat path for an avatar.
        Returns production splat if ready, preview if training, None if unavailable.
        """
        meta = self._load_metadata(avatar_id)
        if meta is None:
            return None

        if meta.splat_status == "ready" and meta.splat_path:
            return meta.splat_path
        elif meta.splat_status in ("preview", "training") and meta.splat_preview_path:
            return meta.splat_preview_path
        return None

    def delete_avatar(self, avatar_id: str) -> bool:
        """Delete an avatar and all its data."""
        avatar_dir = self.base_dir / avatar_id
        if avatar_dir.exists():
            shutil.rmtree(avatar_dir)
            logger.info(f"Avatar '{avatar_id}' deleted")
            return True
        return False

    # ── Internal ─────────────────────────────────────────────────────────

    def _metadata_path(self, avatar_id: str) -> Path:
        return self.base_dir / avatar_id / "metadata.json"

    def _save_metadata(self, meta: AvatarMetadata):
        path = self._metadata_path(meta.avatar_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(meta), f, indent=2)

    def _load_metadata(self, avatar_id: str) -> Optional[AvatarMetadata]:
        path = self._metadata_path(avatar_id)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return AvatarMetadata(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to load metadata for '{avatar_id}': {e}")
            return None
