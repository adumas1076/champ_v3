"""
CHAMP Avatar — State Machine
Mirrors LiveAvatar's state model with clean transitions.

States:
  IDLE       → minimal movement (breathing, blinks)
  LISTENING  → active engagement (nods, brow raises, blinks)
  SPEAKING   → audio-driven lip sync + expressions + head motion

Transitions:
  IDLE → LISTENING       (user starts speaking / start_listening event)
  LISTENING → SPEAKING   (agent TTS audio arrives)
  SPEAKING → LISTENING   (interrupt)
  SPEAKING → IDLE        (agent finishes speaking, natural end)
  LISTENING → IDLE       (user stops speaking, 3s timeout)
"""

from enum import Enum
from dataclasses import dataclass, field
import time


class AvatarState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    SPEAKING = "speaking"


@dataclass
class StateTransition:
    """Represents a transition between states with timing for blending."""
    from_state: AvatarState
    to_state: AvatarState
    started_at: float = field(default_factory=time.monotonic)
    duration: float = 0.3  # seconds to blend

    @property
    def progress(self) -> float:
        """Returns 0.0 → 1.0 over the transition duration."""
        elapsed = time.monotonic() - self.started_at
        return min(1.0, elapsed / self.duration) if self.duration > 0 else 1.0

    @property
    def complete(self) -> bool:
        return self.progress >= 1.0


class AvatarStateMachine:
    """
    Manages avatar state with smooth transitions.
    Only one transition can be active at a time.
    """

    def __init__(self):
        self._state = AvatarState.IDLE
        self._transition: StateTransition | None = None
        self._last_state_change = time.monotonic()

    @property
    def state(self) -> AvatarState:
        return self._state

    @property
    def transition(self) -> StateTransition | None:
        """Active transition (None if settled)."""
        if self._transition and self._transition.complete:
            self._transition = None
        return self._transition

    @property
    def is_transitioning(self) -> bool:
        return self.transition is not None

    @property
    def blend_factor(self) -> float:
        """0.0 = fully in old state, 1.0 = fully in new state."""
        t = self.transition
        if t is None:
            return 1.0
        return t.progress

    @property
    def time_in_state(self) -> float:
        """Seconds since last state change."""
        return time.monotonic() - self._last_state_change

    def transition_to(self, new_state: AvatarState, duration: float = 0.3) -> bool:
        """
        Transition to a new state with blending.
        Returns True if transition started, False if already in that state.
        """
        # Clean up completed transitions before checking
        if self._transition and self._transition.complete:
            self._transition = None
        if new_state == self._state and self._transition is None:
            return False

        from_state = self._state
        self._state = new_state
        self._last_state_change = time.monotonic()
        self._transition = StateTransition(
            from_state=from_state,
            to_state=new_state,
            duration=duration,
        )
        return True

    def to_idle(self, duration: float = 0.3) -> bool:
        return self.transition_to(AvatarState.IDLE, duration)

    def to_listening(self, duration: float = 0.15) -> bool:
        return self.transition_to(AvatarState.LISTENING, duration)

    def to_speaking(self, duration: float = 0.05) -> bool:
        return self.transition_to(AvatarState.SPEAKING, duration)