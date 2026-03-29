"""
AIOSCP decorators — syntactic sugar for building operators.

Usage:
    from aioscp import Operator, capability, on_message, on_task, on_heal

    class MyOperator(Operator):
        @capability(cost_estimate="$0.02", avg_latency_ms=5000)
        async def my_skill(self, query: str) -> str:
            return "result"

        @on_message(type="request")
        async def handle_request(self, msg):
            await msg.reply("got it")

        @on_task()
        async def handle_task(self, task):
            ...

        @on_heal()
        async def handle_heal(self, reason, suggestion):
            ...
"""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, Optional

from aioscp.types import Capability, CapabilityMeta, MessageType


def capability(
    cost_estimate: Optional[str] = None,
    avg_latency_ms: Optional[int] = None,
    confidence: float = 0.8,
    requires_approval: bool = False,
    idempotent: bool = True,
    side_effects: Optional[list[str]] = None,
    input_schema: Optional[dict] = None,
    output_schema: Optional[dict] = None,
) -> Callable:
    """
    Decorator that marks a method as an AIOSCP capability.

    The method's name becomes the capability ID.
    The method's docstring becomes the description.
    """
    def decorator(func: Callable) -> Callable:
        # Build schema from type hints if not provided
        hints = func.__annotations__ if hasattr(func, "__annotations__") else {}

        _input_schema = input_schema or _schema_from_hints(hints, exclude=["return", "self"])
        _output_schema = output_schema or _schema_from_return_hint(hints.get("return"))

        cap = Capability(
            id=func.__name__,
            name=func.__name__.replace("_", " ").title(),
            description=(func.__doc__ or "").strip(),
            input_schema=_input_schema,
            output_schema=_output_schema,
            metadata=CapabilityMeta(
                cost_estimate=cost_estimate,
                avg_latency_ms=avg_latency_ms,
                confidence=confidence,
                requires_approval=requires_approval,
                idempotent=idempotent,
                side_effects=side_effects or [],
            ),
            handler=func,
        )

        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            return await func(self, *args, **kwargs)

        wrapper._aioscp_capability = cap
        return wrapper

    return decorator


def on_message(type: Optional[str] = None, from_id: Optional[str] = None) -> Callable:
    """
    Decorator that registers a method as a message handler.

    @on_message(type="request")
    async def handle_request(self, msg: Message):
        ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            return await func(self, *args, **kwargs)

        wrapper._aioscp_message_handler = {
            "type": type,
            "from_id": from_id,
        }
        return wrapper

    return decorator


def on_task() -> Callable:
    """
    Decorator that registers a method as the primary task handler.

    @on_task()
    async def handle_task(self, task: Task):
        ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            return await func(self, *args, **kwargs)

        wrapper._aioscp_task_handler = True
        return wrapper

    return decorator


def on_heal() -> Callable:
    """
    Decorator that registers a method as the self-healing handler.

    @on_heal()
    async def handle_heal(self, reason: str, suggestion: str | None):
        ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            return await func(self, *args, **kwargs)

        wrapper._aioscp_heal_handler = True
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _schema_from_hints(hints: dict, exclude: list[str] | None = None) -> dict:
    """Build a JSON Schema-like dict from function type hints."""
    exclude = exclude or []
    properties = {}
    required = []

    for name, hint in hints.items():
        if name in exclude:
            continue
        json_type = _TYPE_MAP.get(hint, "string")
        properties[name] = {"type": json_type}
        required.append(name)

    if not properties:
        return {}

    return {"type": "object", "properties": properties, "required": required}


def _schema_from_return_hint(hint: Any) -> dict:
    """Build output schema from return type hint."""
    if hint is None:
        return {}
    json_type = _TYPE_MAP.get(hint, "string")
    return {"type": json_type}
