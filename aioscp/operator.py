"""
AIOSCP Operator base class.

Subclass this to build an operator:

    from aioscp import Operator, capability, on_message

    class Genesis(Operator):
        name = "Genesis"
        persona = {"role": "Research Analyst", "voice": "nova"}
        trust_level = 2

        @capability(cost_estimate="$0.02-0.15")
        async def web_research(self, query: str) -> str:
            '''Deep research on any topic with sourced citations'''
            ...
            return report

        @on_message(type="request")
        async def handle_request(self, msg):
            ...

    # Run with stdio transport (default)
    if __name__ == "__main__":
        Genesis.run()
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from typing import Any, Optional, Type

from aioscp.types import (
    TrustLevel,
    TaskStatus,
    MessageType,
    ContextScope,
    HealthState,
    HealthStatus,
    Capability,
    Task,
    Message,
    Persona,
)

logger = logging.getLogger("aioscp.operator")


class OperatorContext:
    """Interface for operators to interact with the host's context system."""

    def __init__(self, operator: "Operator"):
        self._operator = operator

    async def read(
        self,
        scope: str = "task",
        key: Optional[str] = None,
        query: Optional[str] = None,
        task_id: Optional[str] = None,
        top_k: int = 5,
    ) -> Any:
        return await self._operator._send_request("context.read", {
            "scope": scope,
            "key": key,
            "query": query,
            "task_id": task_id or self._operator._current_task_id,
            "top_k": top_k,
        })

    async def write(
        self,
        key: str,
        value: Any,
        scope: str = "task",
        task_id: Optional[str] = None,
        visible_to: Optional[list[str]] = None,
        ttl_ms: Optional[int] = None,
    ) -> None:
        await self._operator._send_request("context.write", {
            "scope": scope,
            "key": key,
            "value": value,
            "task_id": task_id or self._operator._current_task_id,
            "visible_to": visible_to or [],
            "ttl_ms": ttl_ms,
        })

    async def search(
        self,
        query: str,
        scopes: Optional[list[str]] = None,
        top_k: int = 5,
        min_relevance: float = 0.0,
    ) -> list[dict]:
        return await self._operator._send_request("context.search", {
            "query": query,
            "scopes": scopes or ["task", "conversation"],
            "top_k": top_k,
            "min_relevance": min_relevance,
        })

    async def delete(
        self,
        key: str,
        scope: str = "task",
        task_id: Optional[str] = None,
    ) -> None:
        await self._operator._send_request("context.delete", {
            "scope": scope,
            "key": key,
            "task_id": task_id or self._operator._current_task_id,
        })


class OperatorMessaging:
    """Interface for operators to send messages."""

    def __init__(self, operator: "Operator"):
        self._operator = operator

    async def send(
        self,
        to: str,
        body: Any,
        type: str = "request",
        correlation_id: Optional[str] = None,
        expires_ms: Optional[int] = None,
    ) -> Optional[dict]:
        return await self._operator._send_request("message.send", {
            "from": self._operator._instance_id,
            "to": to,
            "type": type,
            "correlation_id": correlation_id,
            "body": body,
            "expires_ms": expires_ms,
        })

    async def broadcast(
        self,
        body: Any,
        channel: str = "all",
        type: str = "inform",
        priority: str = "normal",
    ) -> None:
        await self._operator._send_notification("message.broadcast", {
            "from": self._operator._instance_id,
            "channel": channel,
            "type": type,
            "body": body,
            "priority": priority,
        })


class OperatorTasking:
    """Interface for operators to manage tasks."""

    def __init__(self, operator: "Operator"):
        self._operator = operator

    async def delegate(
        self,
        description: str,
        assigned_to: str = "auto",
        priority: str = "normal",
        max_cost: Optional[str] = None,
        deliverable_type: str = "none",
        context: Optional[dict] = None,
    ) -> dict:
        return await self._operator._send_request("task.delegate", {
            "parent_task_id": self._operator._current_task_id,
            "sub_task": {
                "description": description,
                "assigned_to": assigned_to,
                "priority": priority,
                "max_cost": max_cost,
                "deliverable": {"type": deliverable_type},
                "context": context or {},
            },
        })

    async def progress(
        self,
        progress: float,
        status: str = "",
        checkpoint: Optional[dict] = None,
    ) -> None:
        await self._operator._send_notification("task.progress", {
            "task_id": self._operator._current_task_id,
            "progress": progress,
            "status": status,
            "tokens_used": self._operator._tokens_used,
            "cost_so_far": self._operator._cost_so_far,
            "checkpoint": checkpoint or {},
        })

    async def complete(
        self,
        deliverable: Any = None,
        summary: str = "",
        confidence: float = 0.8,
        self_checked: bool = False,
        verification_method: Optional[str] = None,
    ) -> None:
        await self._operator._send_request("task.complete", {
            "task_id": self._operator._current_task_id,
            "status": "success",
            "deliverable": deliverable,
            "summary": summary,
            "total_cost": self._operator._cost_so_far,
            "total_tokens": self._operator._tokens_used,
            "confidence": confidence,
            "verification": {
                "self_checked": self_checked,
                "method": verification_method,
            },
        })


class Operator:
    """
    Base class for all AIOSCP operators.

    Subclass this and define:
    - Class attributes: name, persona, trust_level
    - Methods decorated with @capability, @on_message, @on_task, @on_heal
    """

    # --- Override these in subclass ---
    name: str = "Unnamed Operator"
    version: str = "1.0.0"
    description: str = ""
    persona: dict | Persona = Persona(role="General Assistant")
    trust_level: int | TrustLevel = TrustLevel.LOCAL
    model_preference: str = "auto"
    max_tokens_per_task: int = 100000

    def __init__(self):
        self._operator_id = self.__class__.__name__.lower().replace(" ", "-")
        self._instance_id: str = ""
        self._current_task_id: Optional[str] = None
        self._tokens_used: int = 0
        self._cost_so_far: str = "$0.00"
        self._transport: Any = None
        self._health = HealthStatus()
        self._running = False

        # Collect decorated methods
        self._capabilities: dict[str, Capability] = {}
        self._message_handlers: list[tuple[dict, Any]] = []
        self._task_handler: Optional[Any] = None
        self._heal_handler: Optional[Any] = None

        self._discover_handlers()

        # Expose sub-interfaces
        self.context = OperatorContext(self)
        self.messages = OperatorMessaging(self)
        self.tasks = OperatorTasking(self)

    def _discover_handlers(self):
        """Scan class for decorated methods and register them."""
        for attr_name in dir(self):
            try:
                attr = getattr(self, attr_name)
            except Exception:
                continue

            if hasattr(attr, "_aioscp_capability"):
                cap: Capability = attr._aioscp_capability
                cap.handler = attr
                self._capabilities[cap.id] = cap

            if hasattr(attr, "_aioscp_message_handler"):
                self._message_handlers.append((attr._aioscp_message_handler, attr))

            if hasattr(attr, "_aioscp_task_handler"):
                self._task_handler = attr

            if hasattr(attr, "_aioscp_heal_handler"):
                self._heal_handler = attr

    # ------------------------------------------------------------------
    # Protocol: incoming message dispatch
    # ------------------------------------------------------------------

    async def _handle_rpc(self, method: str, params: dict) -> Any:
        """Route an incoming JSON-RPC method to the appropriate handler."""

        if method == "operator.spawn":
            return await self._on_spawn(params)

        elif method == "operator.health":
            return await self._on_health(params)

        elif method == "operator.pause":
            return await self._on_pause(params)

        elif method == "operator.resume":
            return await self._on_resume(params)

        elif method == "operator.heal":
            return await self._on_heal(params)

        elif method == "operator.kill":
            return await self._on_kill(params)

        elif method == "capability.invoke":
            return await self._on_capability_invoke(params)

        elif method == "message.send":
            return await self._on_message(params)

        else:
            raise ValueError(f"Unknown method: {method}")

    async def _on_spawn(self, params: dict) -> dict:
        self._instance_id = params.get("instance_id", f"inst-{uuid.uuid4().hex[:8]}")
        self._current_task_id = params.get("task_id")
        self._running = True
        self._health.status = HealthState.ACTIVE
        logger.info(f"Operator {self.name} spawned as {self._instance_id}")

        # Run task handler if there's a task and a handler
        if self._current_task_id and self._task_handler:
            asyncio.create_task(self._run_task_handler())

        return {"status": "running", "instance_id": self._instance_id}

    async def _run_task_handler(self):
        """Run the @on_task handler in the background."""
        try:
            task_info = await self._send_request("task.list", {
                "filter": {"task_id": self._current_task_id}
            })
            await self._task_handler(task_info)
        except Exception as e:
            logger.error(f"Task handler error: {e}")
            self._health.status = HealthState.ERROR

    async def _on_health(self, params: dict) -> dict:
        return {
            "status": self._health.status.value,
            "progress": self._health.progress,
            "tokens_used": self._tokens_used,
            "cost_so_far": self._cost_so_far,
            "current_action": self._health.current_action,
        }

    async def _on_pause(self, params: dict) -> dict:
        self._running = False
        self._health.status = HealthState.IDLE
        # Serialize state to context
        state = await self.on_pause()
        if state:
            await self.context.write("_operator_state", state, scope="operator")
        return {"paused": True}

    async def _on_resume(self, params: dict) -> dict:
        self._running = True
        self._health.status = HealthState.ACTIVE
        # Restore state from context
        state = await self.context.read(scope="operator", key="_operator_state")
        await self.on_resume(state)
        return {"resumed": True}

    async def _on_heal(self, params: dict) -> dict:
        reason = params.get("reason", "unknown")
        suggestion = params.get("suggestion")
        logger.warning(f"Heal requested: {reason}")

        if self._heal_handler:
            try:
                result = await self._heal_handler(reason, suggestion)
                return {"recovered": True, "action_taken": str(result)}
            except Exception as e:
                return {"recovered": False, "error": str(e)}

        # Default: reset state and signal recovery
        self._health.status = HealthState.ACTIVE
        return {"recovered": True, "action_taken": "reset to active state"}

    async def _on_kill(self, params: dict) -> dict:
        self._running = False
        await self.on_shutdown()
        return {"killed": True}

    async def _on_capability_invoke(self, params: dict) -> dict:
        cap_id = params.get("capability_id", "")
        cap = self._capabilities.get(cap_id)

        if not cap:
            raise ValueError(f"Unknown capability: {cap_id}")

        input_data = params.get("input", {})
        self._health.current_action = f"Running {cap.name}"

        result = await cap.handler(**input_data) if isinstance(input_data, dict) else await cap.handler(input_data)

        self._health.current_action = ""
        return {
            "output": result,
            "cost": self._cost_so_far,
            "tokens_used": self._tokens_used,
            "confidence": cap.metadata.confidence,
        }

    async def _on_message(self, params: dict) -> None:
        msg = Message(
            from_id=params.get("from", ""),
            to_id=params.get("to", ""),
            type=MessageType(params.get("type", "inform")),
            correlation_id=params.get("correlation_id"),
            body=params.get("body"),
        )

        for filter_spec, handler in self._message_handlers:
            if filter_spec.get("type") and filter_spec["type"] != msg.type.value:
                continue
            if filter_spec.get("from_id") and filter_spec["from_id"] != msg.from_id:
                continue
            await handler(msg)

    # ------------------------------------------------------------------
    # Lifecycle hooks (override in subclass)
    # ------------------------------------------------------------------

    async def on_pause(self) -> Optional[dict]:
        """Called before pausing. Return state dict to serialize."""
        return None

    async def on_resume(self, state: Any) -> None:
        """Called after resuming. Receives previously serialized state."""
        pass

    async def on_shutdown(self) -> None:
        """Called before the operator is killed. Clean up resources."""
        pass

    # ------------------------------------------------------------------
    # Transport layer
    # ------------------------------------------------------------------

    async def _send_request(self, method: str, params: dict) -> Any:
        """Send a JSON-RPC request to the host and return the result."""
        msg_id = f"req-{uuid.uuid4().hex[:8]}"
        request = {
            "jsonrpc": "2.0",
            "aioscp": "1.0",
            "method": method,
            "params": params,
            "id": msg_id,
        }

        if self._transport:
            return await self._transport.send_request(request)

        logger.warning(f"No transport connected. Request dropped: {method}")
        return None

    async def _send_notification(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification to the host (no response expected)."""
        notification = {
            "jsonrpc": "2.0",
            "aioscp": "1.0",
            "method": method,
            "params": params,
        }

        if self._transport:
            await self._transport.send_notification(notification)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def get_registration(self) -> dict:
        """Generate the operator.register params for this operator."""
        persona = self.persona if isinstance(self.persona, dict) else {
            "role": self.persona.role,
            "voice": self.persona.voice,
            "backstory": self.persona.backstory,
            "avatar": self.persona.avatar,
        }

        return {
            "id": self._operator_id,
            "name": self.name,
            "version": self.version,
            "persona": persona,
            "capabilities": list(self._capabilities.keys()),
            "requires": {
                "trust_level": int(self.trust_level),
                "model": self.model_preference,
                "max_tokens_per_task": self.max_tokens_per_task,
            },
        }

    def get_capability_declarations(self) -> list[dict]:
        """Generate capability.declare params for all capabilities."""
        declarations = []
        for cap in self._capabilities.values():
            declarations.append({
                "id": cap.id,
                "name": cap.name,
                "description": cap.description,
                "input_schema": cap.input_schema,
                "output_schema": cap.output_schema,
                "metadata": {
                    "cost_estimate": cap.metadata.cost_estimate,
                    "avg_latency_ms": cap.metadata.avg_latency_ms,
                    "confidence": cap.metadata.confidence,
                    "requires_approval": cap.metadata.requires_approval,
                    "idempotent": cap.metadata.idempotent,
                    "side_effects": cap.metadata.side_effects,
                },
            })
        return declarations

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    @classmethod
    def run(cls, transport: str = "stdio", **kwargs):
        """
        Start the operator with the specified transport.

        Usage:
            if __name__ == "__main__":
                MyOperator.run()               # stdio (default)
                MyOperator.run("websocket", port=8765)
                MyOperator.run("http", port=8080)
        """
        from aioscp.transport import StdioTransport, WebSocketTransport, HTTPTransport

        operator = cls()

        transport_map = {
            "stdio": StdioTransport,
            "websocket": WebSocketTransport,
            "http": HTTPTransport,
        }

        transport_cls = transport_map.get(transport, StdioTransport)
        operator._transport = transport_cls(operator, **kwargs)

        logger.info(f"Starting {cls.name} on {transport} transport")
        asyncio.run(operator._transport.start())
