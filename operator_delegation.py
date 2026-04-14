# ============================================
# Cocreatiq V1 — Agent Delegation
# Seamless handoff between operators with context
# Pattern: MultiAgent vid + AIOSCP A2A
# ============================================

import logging
from dataclasses import dataclass, field
from typing import Optional, Any
from uuid import uuid4
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class DelegationRequest:
    """A request to hand off to another operator."""
    id: str = field(default_factory=lambda: str(uuid4()))
    from_operator: str = ""
    to_operator: str = ""
    reason: str = ""
    context_summary: str = ""
    user_message: str = ""  # What the user said that triggered the handoff
    preserve_memory: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DelegationResult:
    """Result of a delegation attempt."""
    success: bool
    request: DelegationRequest
    new_operator: Optional[Any] = None
    transition_message: str = ""
    error: str = ""


class DelegationManager:
    """
    Manages operator-to-operator handoffs.

    Flow:
    1. Current operator decides to delegate
    2. DelegationManager builds context summary
    3. New operator is spawned with context
    4. Transition message is spoken to user
    5. Old operator is cleaned up
    """

    def __init__(self, registry=None):
        self._registry = registry
        self._history: list[DelegationRequest] = []

    def set_registry(self, registry):
        """Set the operator registry (avoids circular import)."""
        self._registry = registry

    def build_transition_message(self, request: DelegationRequest) -> str:
        """Build a natural transition message for the user."""
        messages = {
            "billing": f"Copy champ, let me connect you with billing. They'll have your account pulled up.",
            "sales": f"Alright, connecting you with sales. They'll take it from here.",
            "support": f"Got it, let me get support on the line. They'll help you out.",
            "assistant": f"Let me hand this to your assistant. They'll get it scheduled.",
            "operations": f"Routing to operations. They'll handle the backend.",
            "retention": f"Let me connect you with the retention team.",
            "content": f"Passing this to content. They'll get it created.",
            "growth": f"Connecting you with growth. They'll run the numbers.",
        }

        return messages.get(
            request.to_operator,
            f"Let me connect you with {request.to_operator}. One moment."
        )

    def build_context_for_new_operator(self, request: DelegationRequest, transcript_text: str = "") -> str:
        """Build context summary for the incoming operator."""
        context = f"HANDOFF CONTEXT:\n"
        context += f"Transferred from: {request.from_operator}\n"
        context += f"Reason: {request.reason}\n"

        if request.user_message:
            context += f"User's last request: {request.user_message}\n"

        if request.context_summary:
            context += f"Summary: {request.context_summary}\n"

        if transcript_text:
            # Get last 5 exchanges for context
            lines = transcript_text.strip().split("\n")
            last_lines = lines[-10:] if len(lines) >= 10 else lines
            context += f"Recent conversation:\n" + "\n".join(last_lines)

        return context

    async def delegate(
        self,
        from_operator: str,
        to_operator: str,
        reason: str,
        user_message: str = "",
        context_summary: str = "",
        transcript_text: str = "",
        session_id: str = "",
        memory_text: str = "",
    ) -> DelegationResult:
        """
        Execute a delegation from one operator to another.
        """
        request = DelegationRequest(
            from_operator=from_operator,
            to_operator=to_operator,
            reason=reason,
            user_message=user_message,
            context_summary=context_summary,
        )

        self._history.append(request)

        if not self._registry:
            return DelegationResult(
                success=False,
                request=request,
                error="No registry available",
            )

        try:
            # Build context for new operator
            handoff_context = self.build_context_for_new_operator(request, transcript_text)

            # Spawn new operator with context
            new_operator = self._registry.spawn_with_context(
                name=to_operator,
                session_id=session_id,
                memory_text=memory_text + "\n\n" + handoff_context,
            )

            # Build transition message
            transition_msg = self.build_transition_message(request)

            logger.info(
                f"[DELEGATION] {from_operator} → {to_operator}: {reason}"
            )

            return DelegationResult(
                success=True,
                request=request,
                new_operator=new_operator,
                transition_message=transition_msg,
            )

        except Exception as e:
            logger.error(f"[DELEGATION] Failed: {e}")
            return DelegationResult(
                success=False,
                request=request,
                error=str(e),
            )

    def get_history(self) -> list[dict]:
        """Return delegation history."""
        return [
            {
                "id": r.id,
                "from": r.from_operator,
                "to": r.to_operator,
                "reason": r.reason,
                "timestamp": r.created_at.isoformat(),
            }
            for r in self._history
        ]


# Global delegation manager — singleton
delegation = DelegationManager()