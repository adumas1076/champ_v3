"""
CHAMP Avatar — Motion Smoothing & Transition Blending
Eliminates jitter, handles state crossfades, adds anticipatory motion.
"""

import numpy as np
from . import config
from .states import AvatarState, AvatarStateMachine


class MotionSmoother:
    """
    Applies EMA smoothing to motion vectors with state-aware alpha.

    - SPEAKING: alpha=0.7 (responsive to audio)
    - LISTENING: alpha=0.3 (smooth, relaxed movement)
    - IDLE: alpha=0.2 (very smooth, minimal drift)
    """

    def __init__(self):
        self._prev_motion: np.ndarray | None = None

    def smooth(self, motion: np.ndarray, state: AvatarState) -> np.ndarray:
        """
        Apply EMA smoothing to a motion vector.

        Args:
            motion: raw motion vector (55,)
            state: current avatar state (determines alpha)

        Returns:
            Smoothed motion vector (55,)
        """
        alpha = {
            AvatarState.SPEAKING: config.SMOOTHING_ALPHA_SPEAKING,
            AvatarState.LISTENING: config.SMOOTHING_ALPHA_LISTENING,
            AvatarState.IDLE: config.SMOOTHING_ALPHA_IDLE,
        }.get(state, config.SMOOTHING_ALPHA_IDLE)

        if self._prev_motion is None:
            self._prev_motion = motion.copy()
            return motion

        smoothed = alpha * motion + (1.0 - alpha) * self._prev_motion
        self._prev_motion = smoothed.copy()
        return smoothed

    def reset(self) -> None:
        """Reset smoothing state (on hard state change)."""
        self._prev_motion = None


class TransitionBlender:
    """
    Blends motion vectors during state transitions.

    When transitioning from SPEAKING → IDLE, the motion gradually
    fades from the last speaking motion to idle motion over the
    transition duration.
    """

    def __init__(self):
        self._last_speaking_motion: np.ndarray | None = None

    def blend(
        self,
        current_motion: np.ndarray,
        state_machine: AvatarStateMachine,
    ) -> np.ndarray:
        """
        Blend motion during state transitions.

        Args:
            current_motion: motion from current state's generator
            state_machine: the state machine (provides blend_factor)

        Returns:
            Blended motion vector (55,)
        """
        transition = state_machine.transition
        if transition is None:
            # No active transition — just track if we're speaking
            if state_machine.state == AvatarState.SPEAKING:
                self._last_speaking_motion = current_motion.copy()
            return current_motion

        # Active transition — blend between old and new
        t = transition.progress
        # Use smooth step for natural easing (cubic Hermite)
        t = t * t * (3.0 - 2.0 * t)

        if transition.from_state == AvatarState.SPEAKING and self._last_speaking_motion is not None:
            # Blend from last speaking frame to current (idle/listening)
            blended = (1.0 - t) * self._last_speaking_motion + t * current_motion
        else:
            # Generic blend — just ease in the new motion
            blended = current_motion * t
            if self._last_speaking_motion is not None:
                blended += self._last_speaking_motion * (1.0 - t)
            # Else we don't have old motion, just fade in

        # Track speaking motion
        if state_machine.state == AvatarState.SPEAKING:
            self._last_speaking_motion = current_motion.copy()

        return blended


class AnticipatoryMotion:
    """
    Adds pre-opening mouth movement before speech audio arrives.

    When transitioning to SPEAKING, the jaw begins opening slightly
    ~50ms before the first audio sample. This mimics natural human
    behavior where the mouth opens before sound comes out.
    """

    def apply(
        self,
        motion: np.ndarray,
        state_machine: AvatarStateMachine,
    ) -> np.ndarray:
        """
        Add anticipatory motion if transitioning to SPEAKING.

        Args:
            motion: current motion vector (55,)
            state_machine: state machine for transition info

        Returns:
            Modified motion vector with anticipatory opening
        """
        transition = state_machine.transition
        if transition is None:
            return motion

        if transition.to_state != AvatarState.SPEAKING:
            return motion

        # Early phase of transition to speaking — open jaw slightly
        t = transition.progress
        if t < 0.5:
            # Ramp up jaw opening in first half of transition
            anticipate = t / 0.5  # 0 → 1 over first 50% of transition
            motion = motion.copy()
            motion[config.IDX_JAW_OPEN] = max(
                motion[config.IDX_JAW_OPEN],
                anticipate * 0.15,  # Subtle pre-opening
            )

        return motion