# ============================================
# Conversation Matrix — Backchannel Manager
# Handles "mhm", "yeah", "right" injection while
# the user is speaking. Makes the AI feel PRESENT.
#
# Harvested patterns from:
# - LiveKit 1.5 Adaptive Interruption Handling
# - NVIDIA PersonaPlex-7B backchannel research
# - Linguistics research on backchannel timing
# ============================================

import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BackchannelClip:
    """A pre-recorded backchannel audio clip."""
    name: str
    file_path: str
    energy: str          # neutral | engaged | surprised | agreeing | amused
    duration_ms: int     # clip duration in milliseconds
    category: str        # acknowledgment | engagement | agreement | humor


@dataclass
class BackchannelEvent:
    """A backchannel to inject at a specific moment."""
    clip: BackchannelClip
    trigger_reason: str  # why this backchannel was triggered
    timestamp: float     # when to play (relative to user speech start)


# ---- Default Clip Library ----
# These can be pre-recorded or sourced from royalty-free packs.
# Path is relative to project root — actual .wav files needed.

DEFAULT_CLIPS = [
    # Acknowledgment — "I'm listening"
    BackchannelClip("mhm", "static/backchannels/mhm.wav", "neutral", 400, "acknowledgment"),
    BackchannelClip("yeah", "static/backchannels/yeah.wav", "neutral", 350, "acknowledgment"),
    BackchannelClip("right", "static/backchannels/right.wav", "engaged", 300, "acknowledgment"),
    BackchannelClip("uh_huh", "static/backchannels/uh_huh.wav", "neutral", 450, "acknowledgment"),

    # Engagement — "that's interesting"
    BackchannelClip("oh_really", "static/backchannels/oh_really.wav", "surprised", 600, "engagement"),
    BackchannelClip("wow", "static/backchannels/wow.wav", "surprised", 350, "engagement"),
    BackchannelClip("hmm", "static/backchannels/hmm.wav", "engaged", 500, "engagement"),

    # Agreement — "I'm with you"
    BackchannelClip("facts", "static/backchannels/facts.wav", "agreeing", 400, "agreement"),
    BackchannelClip("for_real", "static/backchannels/for_real.wav", "agreeing", 500, "agreement"),

    # Humor — "that was funny"
    BackchannelClip("haha", "static/backchannels/haha.wav", "amused", 600, "humor"),
]


# ---- Timing Rules ----
# Based on linguistics research (MDPI Languages 2025)

BACKCHANNEL_RULES = {
    # Trigger: when to consider injecting a backchannel
    "trigger_pause_ms": 200,        # user pauses for 200ms+ at phrase boundary
    "trigger_falling_pitch": True,   # combined with falling pitch = phrase end

    # Cooldown: don't backchannel too frequently
    "cooldown_ms": 5000,             # minimum 5 seconds between backchannels
    "max_per_turn": 3,               # maximum 3 per user speaking turn

    # Variety: don't repeat the same clip
    "no_repeat_last_n": 3,           # don't use same clip within last 3

    # Energy matching: select clip energy based on detected user emotion
    "energy_matching": True,
}


class BackchannelManager:
    """
    Manages backchannel injection during user speech.

    In voice mode, while the user is talking, this system
    decides when and what to inject as listening signals.

    Integration:
    - Receives VAD events from LiveKit (pause detected)
    - Selects appropriate clip based on timing + energy
    - Returns audio to play through LiveKit track
    - Respects cooldown and variety rules

    NOTE: This system works with LiveKit 1.5+ Adaptive
    Interruption Handling. Without it, backchannels would
    be treated as barge-in and kill the user's speech.
    """

    def __init__(
        self,
        clips: list[BackchannelClip] = None,
        base_path: str = "",
    ):
        self.clips = clips or DEFAULT_CLIPS
        self.base_path = base_path

        # State tracking
        self._last_backchannel_time: float = 0
        self._backchannels_this_turn: int = 0
        self._recent_clips: list[str] = []
        self._turn_active: bool = False

    def start_user_turn(self) -> None:
        """Called when user starts speaking. Resets turn counters."""
        self._backchannels_this_turn = 0
        self._turn_active = True
        logger.debug("[BACKCHANNEL] User turn started")

    def end_user_turn(self) -> None:
        """Called when user stops speaking."""
        self._turn_active = False
        logger.debug(
            f"[BACKCHANNEL] User turn ended | "
            f"backchannels_injected={self._backchannels_this_turn}"
        )

    def should_backchannel(
        self,
        pause_ms: int,
        user_emotion: str = "neutral",
    ) -> Optional[BackchannelEvent]:
        """
        Decide whether to inject a backchannel at this moment.

        Called when VAD detects a pause during user speech.

        Args:
            pause_ms: Duration of the detected pause in milliseconds
            user_emotion: Current detected user emotion

        Returns:
            BackchannelEvent if we should play one, None if not
        """
        if not self._turn_active:
            return None

        # Check: pause long enough?
        if pause_ms < BACKCHANNEL_RULES["trigger_pause_ms"]:
            return None

        # Check: cooldown elapsed?
        now = time.time()
        elapsed_ms = (now - self._last_backchannel_time) * 1000
        if elapsed_ms < BACKCHANNEL_RULES["cooldown_ms"]:
            return None

        # Check: max per turn?
        if self._backchannels_this_turn >= BACKCHANNEL_RULES["max_per_turn"]:
            return None

        # Select clip
        clip = self._select_clip(user_emotion)
        if not clip:
            return None

        # Record state
        self._last_backchannel_time = now
        self._backchannels_this_turn += 1
        self._recent_clips.append(clip.name)
        if len(self._recent_clips) > BACKCHANNEL_RULES["no_repeat_last_n"]:
            self._recent_clips.pop(0)

        event = BackchannelEvent(
            clip=clip,
            trigger_reason=f"pause={pause_ms}ms, emotion={user_emotion}",
            timestamp=now,
        )

        logger.debug(
            f"[BACKCHANNEL] Injecting: {clip.name} ({clip.energy}) | "
            f"reason={event.trigger_reason}"
        )

        return event

    def _select_clip(self, user_emotion: str) -> Optional[BackchannelClip]:
        """
        Select the best backchannel clip based on context.

        Priority:
        1. Match energy to user emotion
        2. Don't repeat recent clips
        3. Random selection within matching candidates
        """
        # Map user emotion to preferred clip energy
        energy_map = {
            "excited": ["agreeing", "engaged", "amused"],
            "frustrated": ["neutral", "engaged"],
            "casual": ["neutral", "agreeing"],
            "serious": ["neutral", "engaged"],
            "curious": ["engaged", "surprised"],
            "confident": ["agreeing", "engaged"],
            "defeated": ["neutral"],
            "grateful": ["agreeing", "neutral"],
            "neutral": ["neutral", "engaged"],
        }

        preferred_energies = energy_map.get(user_emotion, ["neutral"])

        # Filter: match energy + not recently used
        candidates = [
            clip for clip in self.clips
            if clip.energy in preferred_energies
            and clip.name not in self._recent_clips
        ]

        # Fallback: any clip not recently used
        if not candidates:
            candidates = [
                clip for clip in self.clips
                if clip.name not in self._recent_clips
            ]

        # Final fallback: any clip
        if not candidates:
            candidates = self.clips

        return random.choice(candidates) if candidates else None

    def get_clip_path(self, clip: BackchannelClip) -> str:
        """Get full file path for a backchannel clip."""
        if self.base_path:
            return str(Path(self.base_path) / clip.file_path)
        return clip.file_path

    def get_available_clips(self) -> list[dict]:
        """List all available backchannel clips with their properties."""
        return [
            {
                "name": c.name,
                "energy": c.energy,
                "category": c.category,
                "duration_ms": c.duration_ms,
                "file": c.file_path,
            }
            for c in self.clips
        ]

    def has_audio_files(self) -> bool:
        """Check if backchannel audio files actually exist on disk."""
        for clip in self.clips:
            path = Path(self.get_clip_path(clip))
            if path.exists():
                return True
        return False
