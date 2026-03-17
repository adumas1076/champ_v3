"""
CHAMP Avatar — Idle & Listening Animation Generator
Procedural animations for when the avatar is NOT speaking.
No ML needed — just math (Perlin noise, sine waves, randomized triggers).

Generates motion vectors (52 blendshapes + 3 head pose) per frame.
"""

import math
import time
import random
import numpy as np
from . import config


def _perlin_1d(t: float, seed: float = 0.0) -> float:
    """Simple 1D Perlin-like smooth noise using sine harmonics."""
    return (
        math.sin(t * 0.7 + seed) * 0.5
        + math.sin(t * 1.3 + seed * 2.1) * 0.3
        + math.sin(t * 2.9 + seed * 0.7) * 0.2
    )


class IdleAnimator:
    """
    Generates procedural motion for IDLE and LISTENING states.

    IDLE: breathing, occasional blinks, subtle head sway
    LISTENING: all of IDLE + nods, brow raises, more frequent blinks
    """

    def __init__(self, seed: int | None = None):
        rng = random.Random(seed)
        self._seed_x = rng.random() * 100
        self._seed_y = rng.random() * 100
        self._seed_z = rng.random() * 100
        self._rng = rng

        # Blink state — uses provided t, not wall clock
        self._next_blink_time = rng.uniform(
            config.BLINK_INTERVAL_MIN, config.BLINK_INTERVAL_MAX
        )
        self._blink_start: float | None = None

        # Nod state (listening only)
        self._nod_start: float | None = None
        self._nod_direction: float = 1.0  # positive = down nod

        # Brow raise state (listening only)
        self._brow_raise_start: float | None = None

    def generate(self, state: str, t: float | None = None) -> np.ndarray:
        """
        Generate a motion vector for the current frame.

        Args:
            state: "idle" or "listening"
            t: animation time in seconds. Uses time.monotonic() if None.

        Returns:
            np.ndarray of shape (55,) — 52 blendshapes + 3 head pose
        """
        if t is None:
            t = time.monotonic()
        # Initialize next_blink_time relative to first call's t
        if not hasattr(self, '_time_initialized'):
            self._next_blink_time += t
            self._time_initialized = True

        motion = np.zeros(config.MOTION_DIM, dtype=np.float32)

        # ─── Breathing (always active) ────────────────────────────
        breath = math.sin(t * config.BREATHING_RATE * 2 * math.pi)
        breath_val = breath * config.BREATHING_AMPLITUDE
        # Slight jaw movement with breathing
        motion[config.IDX_JAW_OPEN] = max(0, breath_val * 0.3)
        # Head pitch follows breathing slightly
        motion[config.IDX_HEAD_PITCH] = breath_val * 0.5

        # ─── Head sway (Perlin noise) ────────────────────────────
        sway_t = t * config.HEAD_SWAY_SPEED
        amp = config.HEAD_SWAY_AMPLITUDE
        if state == "listening":
            amp *= 2.0  # More head movement when listening

        motion[config.IDX_HEAD_PITCH] += _perlin_1d(sway_t, self._seed_x) * amp * 0.7
        motion[config.IDX_HEAD_YAW] += _perlin_1d(sway_t, self._seed_y) * amp
        motion[config.IDX_HEAD_ROLL] += _perlin_1d(sway_t, self._seed_z) * amp * 0.3

        # ─── Blinking ────────────────────────────────────────────
        self._update_blink(t, state, motion)

        # ─── Listening-specific animations ────────────────────────
        if state == "listening":
            self._update_nod(t, motion)
            self._update_brow_raise(t, motion)
            # Slight smile when listening (engagement)
            smile_val = 0.1 + _perlin_1d(t * 0.3, self._seed_x + 50) * 0.05
            motion[config.IDX_MOUTH_SMILE_LEFT] = smile_val
            motion[config.IDX_MOUTH_SMILE_RIGHT] = smile_val

        return motion

    def _update_blink(self, t: float, state: str, motion: np.ndarray) -> None:
        """Handle eye blinking."""
        # Check if it's time for a new blink
        if self._blink_start is None and t >= self._next_blink_time:
            self._blink_start = t
            # Schedule next blink
            interval = self._rng.uniform(config.BLINK_INTERVAL_MIN, config.BLINK_INTERVAL_MAX)
            if state == "listening":
                interval *= 0.7  # Blink more often when engaged
            self._next_blink_time = t + interval

        # Animate active blink
        if self._blink_start is not None:
            blink_progress = (t - self._blink_start) / config.BLINK_DURATION
            if blink_progress >= 1.0:
                self._blink_start = None
            else:
                # Smooth blink curve: quick close, slower open
                if blink_progress < 0.4:
                    # Closing (fast)
                    blink_val = blink_progress / 0.4
                else:
                    # Opening (slower)
                    blink_val = 1.0 - (blink_progress - 0.4) / 0.6
                motion[config.IDX_EYE_BLINK_LEFT] = blink_val
                motion[config.IDX_EYE_BLINK_RIGHT] = blink_val

    def _update_nod(self, t: float, motion: np.ndarray) -> None:
        """Handle listening nods."""
        # Check if we should start a nod
        if self._nod_start is None:
            if random.random() < config.LISTENING_NOD_PROBABILITY / config.VIDEO_FPS:
                self._nod_start = t
                self._nod_direction = random.choice([1.0, 1.0, 1.0, -0.5])  # Mostly down-nods

        # Animate active nod
        if self._nod_start is not None:
            nod_progress = (t - self._nod_start) / config.LISTENING_NOD_DURATION
            if nod_progress >= 1.0:
                self._nod_start = None
            else:
                # Smooth nod: sine curve
                nod_val = math.sin(nod_progress * math.pi) * 0.08 * self._nod_direction
                motion[config.IDX_HEAD_PITCH] += nod_val

    def _update_brow_raise(self, t: float, motion: np.ndarray) -> None:
        """Handle listening brow raises."""
        if self._brow_raise_start is None:
            if random.random() < config.LISTENING_BROW_RAISE_PROB / config.VIDEO_FPS:
                self._brow_raise_start = t

        if self._brow_raise_start is not None:
            brow_progress = (t - self._brow_raise_start) / 0.5  # 500ms
            if brow_progress >= 1.0:
                self._brow_raise_start = None
            else:
                brow_val = math.sin(brow_progress * math.pi) * 0.15
                motion[config.IDX_BROW_INNER_UP] = brow_val
                motion[config.IDX_BROW_OUTER_UP_LEFT] = brow_val * 0.5
                motion[config.IDX_BROW_OUTER_UP_RIGHT] = brow_val * 0.5