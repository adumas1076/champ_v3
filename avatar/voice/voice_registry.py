"""
CHAMP Avatar — Voice Registry

Stores and manages voice profiles per operator.

Each operator's voice profile lives alongside their avatar data:
    models/avatars/{operator_id}/voice/
        reference.wav     — extracted from 2-min video
        centroid.npy      — enrollment centroid (50-clip average embedding)
        config.json       — engine preference, language, emotion mode
        samples/          — reference audio clips for ICL enrollment

A voice profile is created automatically when an operator uploads their
2-min reference video — the audio track becomes the voice source.
"""

import json
import logging
import os
import shutil
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from .. import config

logger = logging.getLogger("champ.avatar.voice.registry")


@dataclass
class VoiceProfile:
    """Voice identity for an operator."""
    operator_id: str
    mode: str                         # "clone", "design", "emotion"
    engine: str                       # "qwen3", "orpheus", "auto"
    language: str                     # ISO 639-1 code ("en", "zh", "es", etc.)
    reference_audio: Optional[str]    # Path to reference WAV (clone mode)
    centroid_path: Optional[str]      # Path to enrollment centroid .npy
    design_prompt: Optional[str]      # Text description (design mode)
    sample_count: int                 # Number of reference clips
    created_at: str
    # Quality metrics from enrollment
    speaker_similarity: float = 0.0   # SECS score from WavLM (0-1)
    word_error_rate: float = 0.0      # WER from Whisper verification
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class VoiceRegistry:
    """
    Manages voice profiles on disk per operator.

    Usage:
        registry = VoiceRegistry()

        # Create from video (clone mode)
        profile = registry.create_from_video("recording.mp4", "anthony")

        # Create from description (design mode)
        profile = registry.create_designed("anthony", "warm male, 35, slight accent")

        # Load for inference
        profile = registry.get_profile("anthony")
    """

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else config.AVATARS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_profile(self, operator_id: str) -> Optional[VoiceProfile]:
        """Load voice profile for an operator."""
        config_path = self._config_path(operator_id)
        if not config_path.exists():
            return None

        try:
            with open(config_path) as f:
                data = json.load(f)
            return VoiceProfile.from_dict(data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to load voice profile for '{operator_id}': {e}")
            return None

    def create_from_video(
        self,
        video_path: str,
        operator_id: str,
        language: str = "en",
        engine: str = "auto",
    ) -> VoiceProfile:
        """
        Create a voice profile by extracting audio from a reference video.

        This is the standard flow — the same 2-min video used for avatar creation
        provides the voice reference. One upload, two outputs.
        """
        from .voice_cloner import VoiceCloner

        voice_dir = self._voice_dir(operator_id)
        voice_dir.mkdir(parents=True, exist_ok=True)

        cloner = VoiceCloner()
        clone_result = cloner.extract_and_enroll(
            video_path=video_path,
            output_dir=str(voice_dir),
        )

        profile = VoiceProfile(
            operator_id=operator_id,
            mode="clone",
            engine=engine,
            language=language,
            reference_audio=clone_result["reference_path"],
            centroid_path=clone_result.get("centroid_path"),
            design_prompt=None,
            sample_count=clone_result["sample_count"],
            created_at=datetime.now().isoformat(),
            speaker_similarity=clone_result.get("speaker_similarity", 0.0),
        )

        self._save_profile(profile)
        logger.info(
            f"Voice profile created for '{operator_id}' from video: "
            f"{clone_result['sample_count']} samples, "
            f"SECS={profile.speaker_similarity:.3f}"
        )
        return profile

    def create_from_audio(
        self,
        audio_path: str,
        operator_id: str,
        language: str = "en",
        engine: str = "auto",
    ) -> VoiceProfile:
        """Create a voice profile from a direct audio reference."""
        voice_dir = self._voice_dir(operator_id)
        voice_dir.mkdir(parents=True, exist_ok=True)

        # Copy reference audio
        ref_dest = voice_dir / "reference.wav"
        shutil.copy2(audio_path, ref_dest)

        profile = VoiceProfile(
            operator_id=operator_id,
            mode="clone",
            engine=engine,
            language=language,
            reference_audio=str(ref_dest),
            centroid_path=None,
            design_prompt=None,
            sample_count=1,
            created_at=datetime.now().isoformat(),
        )

        self._save_profile(profile)
        logger.info(f"Voice profile created for '{operator_id}' from audio")
        return profile

    def create_designed(
        self,
        operator_id: str,
        design_prompt: str,
        language: str = "en",
    ) -> VoiceProfile:
        """
        Create a designed voice from text description.
        No real person — AI generates a voice matching the description.

        Example prompts:
          "warm female voice, 30s, slight southern accent, professional"
          "deep male voice, authoritative, news anchor style"
          "young energetic voice, friendly, casual tone"
        """
        voice_dir = self._voice_dir(operator_id)
        voice_dir.mkdir(parents=True, exist_ok=True)

        profile = VoiceProfile(
            operator_id=operator_id,
            mode="design",
            engine="qwen3",  # Only Qwen3-TTS supports VoiceDesign
            language=language,
            reference_audio=None,
            centroid_path=None,
            design_prompt=design_prompt,
            sample_count=0,
            created_at=datetime.now().isoformat(),
        )

        self._save_profile(profile)
        logger.info(f"Designed voice profile created for '{operator_id}': {design_prompt[:50]}")
        return profile

    def set_emotion_mode(self, operator_id: str, enabled: bool = True) -> Optional[VoiceProfile]:
        """Enable/disable Orpheus emotion mode for an operator."""
        profile = self.get_profile(operator_id)
        if profile is None:
            return None

        if enabled and profile.language == "en":
            profile.engine = "orpheus"
            profile.mode = "emotion"
        else:
            profile.engine = "qwen3"
            if profile.reference_audio:
                profile.mode = "clone"
            elif profile.design_prompt:
                profile.mode = "design"

        self._save_profile(profile)
        logger.info(f"Voice emotion mode for '{operator_id}': {'enabled' if enabled else 'disabled'}")
        return profile

    def list_profiles(self) -> list[VoiceProfile]:
        """List all voice profiles."""
        profiles = []
        for entry in sorted(self.base_dir.iterdir()):
            if entry.is_dir():
                profile = self.get_profile(entry.name)
                if profile:
                    profiles.append(profile)
        return profiles

    def delete_profile(self, operator_id: str) -> bool:
        """Delete an operator's voice profile."""
        voice_dir = self._voice_dir(operator_id)
        if voice_dir.exists():
            shutil.rmtree(voice_dir)
            logger.info(f"Voice profile deleted for '{operator_id}'")
            return True
        return False

    def get_reference_audio(self, operator_id: str) -> Optional[str]:
        """Get the best available reference audio for an operator."""
        profile = self.get_profile(operator_id)
        if profile is None:
            return None
        return profile.reference_audio

    # ── Internal ─────────────────────────────────────────────────────────

    def _voice_dir(self, operator_id: str) -> Path:
        return self.base_dir / operator_id / "voice"

    def _config_path(self, operator_id: str) -> Path:
        return self._voice_dir(operator_id) / "config.json"

    def _save_profile(self, profile: VoiceProfile):
        config_path = self._config_path(profile.operator_id)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(profile.to_dict(), f, indent=2)
