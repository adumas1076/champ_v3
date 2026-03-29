"""
AIOSCP Host — the OS-side runtime that manages operators.

This is what CHAMP (or any AI OS) embeds to become AIOSCP-compatible.

    from aioscp import Host

    host = Host()
    host.register_operator("./operators/genesis/")
    host.spawn("genesis-v2", task_id="task-001")
    await host.run()
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from aioscp.types import (
    TrustLevel,
    TaskStatus,
    HealthState,
    Capability,
    Task,
    OperatorManifest,
)

logger = logging.getLogger("aioscp.host")


@dataclass
class OperatorInstance:
    """A running instance of an operator."""
    instance_id: str
    operator_id: str
    manifest: OperatorManifest
    process: Optional[asyncio.subprocess.Process] = None
    status: HealthState = HealthState.IDLE
    current_task_id: Optional[str] = None
    health_failures: int = 0


class Host:
    """
    AIOSCP Host runtime.

    Manages operator registration, spawning, health checks,
    message routing, task management, and context storage.
    """

    def __init__(
        self,
        health_interval_s: float = 30.0,
        max_health_failures: int = 3,
    ):
        # Registry
        self._operators: dict[str, OperatorManifest] = {}  # operator_id → manifest
        self._capabilities: dict[str, tuple[str, Capability]] = {}  # cap_id → (operator_id, capability)
        self._instances: dict[str, OperatorInstance] = {}  # instance_id → instance

        # Tasks
        self._tasks: dict[str, Task] = {}

        # Context stores
        self._context: dict[str, dict[str, Any]] = {
            "global": {},
            "conversation": {},
        }  # scope → key → value
        self._operator_context: dict[str, dict[str, Any]] = {}  # operator_id → key → value
        self._task_context: dict[str, dict[str, Any]] = {}  # task_id → key → value

        # Message subscriptions
        self._subscriptions: dict[str, list[str]] = {}  # channel → [instance_ids]

        # Config
        self._health_interval = health_interval_s
        self._max_health_failures = max_health_failures

    # ------------------------------------------------------------------
    # Operator Management
    # ------------------------------------------------------------------

    def register(self, manifest: OperatorManifest) -> bool:
        """Register an operator from its manifest."""
        if manifest.id in self._operators:
            logger.warning(f"Operator {manifest.id} already registered, updating")

        self._operators[manifest.id] = manifest

        # Register capabilities
        for cap in manifest.capabilities:
            full_id = f"{manifest.id}.{cap.id}"
            self._capabilities[full_id] = (manifest.id, cap)

        logger.info(f"Registered operator: {manifest.name} ({manifest.id}) "
                     f"with {len(manifest.capabilities)} capabilities")
        return True

    async def spawn(
        self,
        operator_id: str,
        task_id: Optional[str] = None,
        config_overrides: Optional[dict] = None,
    ) -> str:
        """Spawn a new instance of a registered operator."""
        manifest = self._operators.get(operator_id)
        if not manifest:
            raise ValueError(f"Operator {operator_id} not registered")

        instance_id = f"inst-{uuid.uuid4().hex[:8]}"
        instance = OperatorInstance(
            instance_id=instance_id,
            operator_id=operator_id,
            manifest=manifest,
            status=HealthState.ACTIVE,
            current_task_id=task_id,
        )
        self._instances[instance_id] = instance

        logger.info(f"Spawned {manifest.name} as {instance_id}")

        # Send spawn message to operator
        await self._send_to_instance(instance_id, "operator.spawn", {
            "operator_id": operator_id,
            "instance_id": instance_id,
            "task_id": task_id,
            "config_overrides": config_overrides or {},
        })

        return instance_id

    async def kill(self, instance_id: str, reason: str = "host_requested") -> bool:
        """Kill an operator instance."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        await self._send_to_instance(instance_id, "operator.kill", {
            "instance_id": instance_id,
            "reason": reason,
        })

        if instance.process:
            instance.process.terminate()

        del self._instances[instance_id]
        logger.info(f"Killed {instance_id}: {reason}")
        return True

    # ------------------------------------------------------------------
    # Health Monitoring
    # ------------------------------------------------------------------

    async def _health_loop(self):
        """Periodic health check for all running instances."""
        while True:
            await asyncio.sleep(self._health_interval)

            for instance_id, instance in list(self._instances.items()):
                try:
                    result = await asyncio.wait_for(
                        self._send_to_instance(instance_id, "operator.health", {
                            "instance_id": instance_id,
                        }),
                        timeout=10.0,
                    )

                    if result and result.get("status") in ("active", "idle"):
                        instance.health_failures = 0
                        instance.status = HealthState(result["status"])
                    else:
                        instance.health_failures += 1

                except (asyncio.TimeoutError, Exception):
                    instance.health_failures += 1

                # Trigger healing if too many failures
                if instance.health_failures >= self._max_health_failures:
                    await self._heal_instance(instance_id)

    async def _heal_instance(self, instance_id: str):
        """Attempt to heal a failing operator instance."""
        instance = self._instances.get(instance_id)
        if not instance:
            return

        logger.warning(f"Healing {instance_id} ({instance.health_failures} failures)")

        try:
            result = await asyncio.wait_for(
                self._send_to_instance(instance_id, "operator.heal", {
                    "instance_id": instance_id,
                    "reason": "health_timeout",
                }),
                timeout=15.0,
            )

            if result and result.get("recovered"):
                instance.health_failures = 0
                logger.info(f"Healed {instance_id}: {result.get('action_taken')}")
                return

        except Exception:
            pass

        # Healing failed — kill and respawn
        logger.error(f"Healing failed for {instance_id}. Killing and respawning.")
        task_id = instance.current_task_id
        operator_id = instance.operator_id
        await self.kill(instance_id, reason="heal_failed")
        await self.spawn(operator_id, task_id=task_id)

    # ------------------------------------------------------------------
    # Task Management
    # ------------------------------------------------------------------

    async def create_task(
        self,
        description: str,
        assigned_to: str,
        created_by: str = "host",
        priority: str = "normal",
        max_cost: Optional[str] = None,
        deliverable_type: str = "none",
        deadline: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> Task:
        """Create and assign a task."""
        task = Task(
            description=description,
            created_by=created_by,
            assigned_to=assigned_to,
            priority=priority,
            max_cost=max_cost,
            deadline=deadline,
            deliverable={"type": deliverable_type},
            context=context or {},
            status=TaskStatus.CREATED,
        )
        self._tasks[task.id] = task
        self._task_context[task.id] = {}

        # Spawn operator for task if not already running
        running_instances = [
            inst for inst in self._instances.values()
            if inst.operator_id == assigned_to and inst.status == HealthState.IDLE
        ]

        if running_instances:
            instance = running_instances[0]
            instance.current_task_id = task.id
        else:
            await self.spawn(assigned_to, task_id=task.id)

        task.status = TaskStatus.RUNNING
        return task

    # ------------------------------------------------------------------
    # Message Routing
    # ------------------------------------------------------------------

    async def route_message(self, from_id: str, to_id: str, msg: dict):
        """Route a message from one operator to another."""
        # Find target instance
        target = None
        for inst in self._instances.values():
            if inst.operator_id == to_id or inst.instance_id == to_id:
                target = inst
                break

        if not target:
            logger.warning(f"Message target {to_id} not found")
            return

        await self._send_to_instance(target.instance_id, "message.send", msg)

    async def broadcast(self, from_id: str, channel: str, msg: dict):
        """Broadcast a message to all operators or a channel."""
        if channel == "all":
            targets = list(self._instances.keys())
        else:
            targets = self._subscriptions.get(channel, [])

        for instance_id in targets:
            if instance_id != from_id:  # Don't echo back
                await self._send_to_instance(instance_id, "message.send", msg)

    # ------------------------------------------------------------------
    # Context Management
    # ------------------------------------------------------------------

    async def context_read(
        self,
        scope: str,
        key: Optional[str] = None,
        query: Optional[str] = None,
        task_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> Any:
        """Read from a context scope."""
        store = self._get_context_store(scope, task_id, operator_id)

        if key:
            return store.get(key)

        if query:
            # Semantic search placeholder — in production, use vector DB
            results = []
            for k, v in store.items():
                if query.lower() in str(v).lower() or query.lower() in k.lower():
                    results.append({"key": k, "value": v})
            return results

        return store

    async def context_write(
        self,
        scope: str,
        key: str,
        value: Any,
        task_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> None:
        """Write to a context scope."""
        if scope == "global":
            raise PermissionError("Operators cannot write to global scope")

        store = self._get_context_store(scope, task_id, operator_id)
        store[key] = value

    def _get_context_store(
        self,
        scope: str,
        task_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> dict:
        if scope == "task":
            if not task_id:
                raise ValueError("task_id required for task scope")
            return self._task_context.setdefault(task_id, {})
        elif scope == "operator":
            if not operator_id:
                raise ValueError("operator_id required for operator scope")
            return self._operator_context.setdefault(operator_id, {})
        elif scope in ("conversation", "global"):
            return self._context.setdefault(scope, {})
        else:
            raise ValueError(f"Unknown scope: {scope}")

    # ------------------------------------------------------------------
    # Transport helpers
    # ------------------------------------------------------------------

    async def _send_to_instance(self, instance_id: str, method: str, params: dict) -> Any:
        """Send a JSON-RPC message to an operator instance."""
        instance = self._instances.get(instance_id)
        if not instance or not instance.process:
            # In-process operators: direct call
            # This is a placeholder — real implementation depends on transport
            logger.debug(f"→ {instance_id}: {method}")
            return None

        msg = json.dumps({
            "jsonrpc": "2.0",
            "aioscp": "1.0",
            "method": method,
            "params": params,
            "id": f"host-{uuid.uuid4().hex[:8]}",
        })

        instance.process.stdin.write((msg + "\n").encode())
        await instance.process.stdin.drain()

        # Read response
        line = await instance.process.stdout.readline()
        if line:
            data = json.loads(line.decode())
            return data.get("result")

        return None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Start the host runtime (health monitoring, etc.)."""
        logger.info("AIOSCP Host starting")
        await self._health_loop()
