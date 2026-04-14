# ============================================
# Cocreatiq V1 — Operator Hook System
# Lifecycle events for operators
# Pattern: Claude Code event hooks + LiveKit session events
# ============================================

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class HookEvent:
    """A lifecycle event fired by the OS."""
    event_type: str
    operator_name: str
    session_id: str
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)


# All supported hook events
HOOK_EVENTS = [
    "session_start",      # Operator session begins
    "session_end",        # Operator session ends
    "user_message",       # User said something
    "agent_message",      # Operator responded
    "tool_call_start",    # Tool is about to execute
    "tool_call_end",      # Tool finished executing
    "tool_call_error",    # Tool failed
    "error",              # Any error in the session
    "state_change",       # Operator state changed (listening, thinking, speaking)
    "memory_loaded",      # Memory was injected at session start
    "transcript_saved",   # Transcript persisted to Supabase
    "evaluation_done",    # Session evaluation completed
]


class HookRegistry:
    """
    Registry for operator lifecycle hooks.

    Operators register callbacks for events they care about.
    The OS fires events at the right time.
    Hooks are non-blocking — failures don't crash the session.
    """

    def __init__(self):
        self._hooks: dict[str, list[Callable]] = {event: [] for event in HOOK_EVENTS}
        self._operator_hooks: dict[str, dict[str, list[Callable]]] = {}

    def on(self, event_type: str, callback: Callable, operator_name: Optional[str] = None) -> None:
        """Register a hook callback."""
        if event_type not in HOOK_EVENTS:
            logger.warning(f"Unknown hook event: {event_type}")
            return

        if operator_name:
            # Operator-specific hook
            if operator_name not in self._operator_hooks:
                self._operator_hooks[operator_name] = {e: [] for e in HOOK_EVENTS}
            self._operator_hooks[operator_name][event_type].append(callback)
        else:
            # Global hook (fires for all operators)
            self._hooks[event_type].append(callback)

        logger.debug(f"Hook registered: {event_type} {'(' + operator_name + ')' if operator_name else '(global)'}")

    def fire(self, event: HookEvent) -> None:
        """Fire a hook event. Non-blocking — failures are logged, not raised."""
        # Global hooks
        for callback in self._hooks.get(event.event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Global hook failed ({event.event_type}): {e}")

        # Operator-specific hooks
        op_hooks = self._operator_hooks.get(event.operator_name, {})
        for callback in op_hooks.get(event.event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Operator hook failed ({event.operator_name}/{event.event_type}): {e}")

    def clear(self, operator_name: Optional[str] = None) -> None:
        """Clear hooks. If operator_name given, only clear that operator's hooks."""
        if operator_name:
            self._operator_hooks.pop(operator_name, None)
        else:
            self._hooks = {event: [] for event in HOOK_EVENTS}
            self._operator_hooks = {}


# Global hook registry — singleton
hooks = HookRegistry()


# ---- Convenience functions ----

def on_session_start(callback: Callable, operator_name: Optional[str] = None):
    hooks.on("session_start", callback, operator_name)

def on_session_end(callback: Callable, operator_name: Optional[str] = None):
    hooks.on("session_end", callback, operator_name)

def on_user_message(callback: Callable, operator_name: Optional[str] = None):
    hooks.on("user_message", callback, operator_name)

def on_agent_message(callback: Callable, operator_name: Optional[str] = None):
    hooks.on("agent_message", callback, operator_name)

def on_tool_call(callback: Callable, operator_name: Optional[str] = None):
    hooks.on("tool_call_start", callback, operator_name)

def on_error(callback: Callable, operator_name: Optional[str] = None):
    hooks.on("error", callback, operator_name)

def fire_event(event_type: str, operator_name: str, session_id: str, data: dict = None):
    """Fire a hook event with minimal boilerplate."""
    hooks.fire(HookEvent(
        event_type=event_type,
        operator_name=operator_name,
        session_id=session_id,
        data=data or {},
    ))