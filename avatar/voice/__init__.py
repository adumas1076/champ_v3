"""
CHAMP Avatar — Voice Engine (Phase 7 Voice)

Dual-engine voice system for Live Creatiq Operators:

  voice_engine.py     — Dual-engine router (Qwen3-TTS + Orpheus)
  voice_cloner.py     — Extract audio from 2-min video → voice profile
  voice_designer.py   — Text description → designed voice (no real person)
  voice_registry.py   — Store/load voice profiles per operator

Three voice modes:
  CLONE   — Real person's voice from 2-min video audio (Qwen3-TTS ICL)
  DESIGN  — AI-designed voice from text description (Qwen3-TTS VoiceDesign)
  EMOTION — Emotional English voice with laughs/sighs (Orpheus TTS)

Architecture:
  2-min video → extract audio → voice_cloner → voice profile
  Text → voice_engine.route() → Qwen3 or Orpheus → WAV → LiveKit/render

Both engines: Apache 2.0, pip-installable, HuggingFace weights.
"""

from .voice_engine import VoiceEngine, VoiceEngineConfig, VoiceMode
from .voice_cloner import VoiceCloner
from .voice_designer import VoiceDesigner, DesignedVoice
from .voice_registry import VoiceRegistry, VoiceProfile

__all__ = [
    "VoiceEngine",
    "VoiceEngineConfig",
    "VoiceMode",
    "VoiceCloner",
    "VoiceDesigner",
    "DesignedVoice",
    "VoiceProfile",
    "VoiceRegistry",
]
