# ============================================
# Cocreatiq V1 — Operator Context Isolation
# Each operator session gets its own isolated context
# No shared state, no collisions between operators
# Pattern: Python contextvars (equivalent to Claude Code's AsyncLocalStorage)
# ============================================

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OperatorContext:
    """Isolated context for a single operator session."""
    operator_name: str
    session_id: str
    user_id: str = "00000000-0000-0000-0000-000000000001"
    memory_text: str = ""
    model_used: str = "gpt-4o"
    channel: str = "voice"
    metadata: dict = field(default_factory=dict)


# Context variable — isolated per async task (one per LiveKit room)
_current_context: ContextVar[Optional[OperatorContext]] = ContextVar(
    "operator_context", default=None
)


def set_operator_context(ctx: OperatorContext) -> None:
    """Set the current operator context for this async task."""
    _current_context.set(ctx)
    logger.info(f"Context set: operator={ctx.operator_name}, session={ctx.session_id}")


def get_operator_context() -> Optional[OperatorContext]:
    """Get the current operator context. Returns None if not set."""
    return _current_context.get()


def clear_operator_context() -> None:
    """Clear the current operator context."""
    _current_context.set(None)