"""
CHAMP Avatar — Voice Designer

Creates AI-designed voices from text descriptions.
No real person needed — the AI generates a voice matching your description.

Uses Qwen3-TTS VoiceDesign model:
  Input:  "warm female voice, 30s, professional, slight accent"
  Output: Voice configuration for TTS inference

Examples:
  "deep male voice, authoritative, news anchor style"
  "young energetic voice, friendly, casual tone"
  "calm soothing voice, meditation guide, slow pace"
"""

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from .. import config

logger = logging.getLogger("champ.avatar.voice.designer")


@dataclass
class DesignedVoice:
    """A voice designed from a text description."""
    name: str
    description: str
    language: str
    # Qwen3-TTS VoiceDesign parameters
    speaker_embedding: Optional[str]  # Path to generated embedding
    design_config: dict               # Model-specific parameters

    def to_dict(self) -> dict:
        return asdict(self)


# Pre-built voice templates for common operator roles
VOICE_TEMPLATES = {
    "professional_male": {
        "description": "Clear, confident male voice, 35-45 years old, "
                      "professional tone, neutral accent, medium pace",
        "language": "en",
    },
    "professional_female": {
        "description": "Warm, articulate female voice, 30-40 years old, "
                      "professional tone, neutral accent, medium pace",
        "language": "en",
    },
    "friendly_assistant": {
        "description": "Friendly, approachable voice, 25-35 years old, "
                      "casual but professional, slightly upbeat",
        "language": "en",
    },
    "calm_advisor": {
        "description": "Calm, measured voice, 40-50 years old, "
                      "thoughtful pace, reassuring tone, clear enunciation",
        "language": "en",
    },
    "energetic_coach": {
        "description": "Energetic, motivating voice, 30-40 years old, "
                      "dynamic pace, enthusiastic, clear projection",
        "language": "en",
    },
    "tech_expert": {
        "description": "Clear, precise voice, 30-45 years old, "
                      "technical but accessible, steady pace, confident",
        "language": "en",
    },
}


class VoiceDesigner:
    """
    Creates AI-designed voices from text descriptions.

    Usage:
        designer = VoiceDesigner()

        # From custom description
        voice = designer.design(
            name="sales_rep",
            description="warm female, 30s, professional, slight accent",
        )

        # From template
        voice = designer.from_template("professional_female")

        # List templates
        templates = designer.list_templates()
    """

    def __init__(self):
        self._qwen_available = self._check_qwen()

    def _check_qwen(self) -> bool:
        """Check if Qwen3-TTS VoiceDesign is available."""
        try:
            import importlib
            importlib.import_module("qwen_tts")
            return True
        except ImportError:
            return False

    def design(
        self,
        name: str,
        description: str,
        language: str = "en",
        output_dir: Optional[str] = None,
    ) -> DesignedVoice:
        """
        Design a voice from a text description.

        Args:
            name: Voice name identifier
            description: Natural language description of desired voice
            language: Target language
            output_dir: Where to save the voice config

        Returns:
            DesignedVoice with design parameters
        """
        if self._qwen_available:
            try:
                return self._design_qwen(name, description, language, output_dir)
            except Exception as e:
                logger.warning(f"Qwen3 VoiceDesign failed ({e}), using placeholder")

        return self._design_placeholder(name, description, language, output_dir)

    def _design_qwen(
        self, name: str, description: str, language: str, output_dir: Optional[str]
    ) -> DesignedVoice:
        """Design voice using Qwen3-TTS VoiceDesign model."""
        from qwen_tts import QwenTTS

        model = QwenTTS.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign")

        # Generate voice from description
        result = model.design_voice(description)

        embedding_path = None
        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            embedding_path = str(out / f"{name}_embedding.npy")
            import numpy as np
            np.save(embedding_path, result["embedding"])

        voice = DesignedVoice(
            name=name,
            description=description,
            language=language,
            speaker_embedding=embedding_path,
            design_config={
                "model": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
                "voice_id": result.get("voice_id", name),
            },
        )

        logger.info(f"Designed voice '{name}' via Qwen3-TTS: {description[:50]}")
        return voice

    def _design_placeholder(
        self, name: str, description: str, language: str, output_dir: Optional[str]
    ) -> DesignedVoice:
        """Placeholder voice design for testing without Qwen3-TTS."""
        voice = DesignedVoice(
            name=name,
            description=description,
            language=language,
            speaker_embedding=None,
            design_config={
                "model": "placeholder",
                "description_hash": hash(description) % 10000,
            },
        )

        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            config_path = out / f"{name}_design.json"
            with open(config_path, "w") as f:
                json.dump(voice.to_dict(), f, indent=2)

        logger.info(f"Placeholder voice designed: '{name}'")
        return voice

    def from_template(
        self,
        template_name: str,
        custom_name: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> DesignedVoice:
        """Create a voice from a pre-built template."""
        if template_name not in VOICE_TEMPLATES:
            available = ", ".join(VOICE_TEMPLATES.keys())
            raise ValueError(
                f"Unknown template '{template_name}'. Available: {available}"
            )

        template = VOICE_TEMPLATES[template_name]
        return self.design(
            name=custom_name or template_name,
            description=template["description"],
            language=template.get("language", "en"),
            output_dir=output_dir,
        )

    def list_templates(self) -> dict:
        """List available voice templates."""
        return {
            name: tmpl["description"]
            for name, tmpl in VOICE_TEMPLATES.items()
        }

    @property
    def available(self) -> bool:
        """True if Qwen3-TTS VoiceDesign is available."""
        return self._qwen_available
