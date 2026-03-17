"""
CHAMP Avatar — Real-time animated digital human for voice calls.

Split pipeline architecture:
    Audio → wav2vec2 features → FlashHead motion → LivePortrait render → WebRTC

Modules:
    config     — All settings and constants
    states     — State machine (IDLE/LISTENING/SPEAKING)
    audio      — wav2vec2 feature extraction + resampling
    motion     — FlashHead audio-to-motion predictor
    idle       — Procedural animations (blinks, nods, breathing)
    smoothing  — EMA smoothing + transition blending + anticipatory motion
    renderer   — Orchestrates pipeline, implements LiveKit VideoGenerator
    controller — Bridges LiveKit room events → avatar states
"""

from .renderer import ChampAvatarRenderer
from .states import AvatarState, AvatarStateMachine
from .controller import AvatarStateController

__all__ = [
    "ChampAvatarRenderer",
    "AvatarState",
    "AvatarStateMachine",
    "AvatarStateController",
]