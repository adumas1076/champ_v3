# ============================================
# CHAMP V3 — Operator Registry (AIOSCP Host)
# The OS uses this to look up and spin up operators.
# Register by class (code) or by config (YAML).
#
# This IS the AIOSCP Host — it manages operator
# lifecycle, capabilities, manifests, and A2A.
#
# A2A (Agent-to-Agent) levels:
#   1. Swap     — one replaces another, context passes
#   2. Delegate — hand task to another, get results back
#   3. Collaborate — multiple active, messaging each other
# ============================================

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Type, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from livekit.agents.llm import ChatContext

from operators.base import BaseOperator, CONFIGS_DIR
from operators.aioscp_bridge import (
    generate_manifest,
    get_os_capabilities,
    get_capability,
    estimate_cost,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------
# A2A Data Models
# -----------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class A2AMessage:
    """A message between operators, routed through the OS."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_operator: str = ""
    to_operator: str = ""           # empty = broadcast
    channel: str = "default"
    body: Any = None
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)


@dataclass
class A2ATask:
    """A delegated task from one operator to another."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_operator: str = ""
    to_operator: str = ""
    description: str = ""
    context: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0


class OperatorRegistry:
    """
    Registry of all operators available on this OS instance.
    Also serves as the AIOSCP Host — manages manifests,
    capabilities, and operator lifecycle.

    Two ways to register an operator:
    1. By class:  registry.register("champ", ChampOperator)
    2. By config: registry.register_config("billy")  → loads billy.yaml

    The OS calls registry.spawn("champ") to create an instance.
    AIOSCP clients call registry.get_manifest("champ") to discover capabilities.
    """

    def __init__(self):
        self._classes: dict[str, Type[BaseOperator]] = {}
        self._configs: set[str] = set()
        self._manifests: dict[str, object] = {}  # name -> OperatorManifest
        # A2A state
        self._instances: dict[str, BaseOperator] = {}   # active operator instances
        self._tasks: dict[str, A2ATask] = {}             # task_id -> A2ATask
        self._subscriptions: dict[str, list[Callable]] = {}  # channel -> [callbacks]
        self._message_queue: asyncio.Queue = asyncio.Queue()

    def register(self, name: str, operator_class: Type[BaseOperator]) -> None:
        """Register an operator class by name."""
        key = name.lower()
        self._classes[key] = operator_class

        # Auto-generate AIOSCP manifest
        config_path = CONFIGS_DIR / f"{key}.yaml"
        self._manifests[key] = generate_manifest(
            key,
            config_path=config_path if config_path.exists() else None,
        )

        logger.info(f"[REGISTRY] Registered operator class: {name}")

    def register_config(self, name: str) -> None:
        """Register an operator by config file name (loads from configs/{name}.yaml)."""
        key = name.lower()
        self._configs.add(key)

        # Auto-generate AIOSCP manifest from config
        config_path = CONFIGS_DIR / f"{key}.yaml"
        self._manifests[key] = generate_manifest(
            key,
            config_path=config_path if config_path.exists() else None,
        )

        logger.info(f"[REGISTRY] Registered operator config: {name}")

    def spawn(
        self, name: str, chat_ctx: ChatContext = None
    ) -> BaseOperator:
        """
        Spin up an operator instance by name.

        Checks classes first (code-defined operators like Champ),
        then falls back to config-driven operators (YAML-defined).
        """
        key = name.lower()

        # Code-defined operator (has its own class)
        if key in self._classes:
            logger.info(f"[OS] Spawning operator '{key}' from class")
            return self._classes[key](chat_ctx=chat_ctx)

        # Config-defined operator (loaded from YAML)
        if key in self._configs:
            logger.info(f"[OS] Spawning operator '{key}' from config")
            return BaseOperator.from_config(key, chat_ctx=chat_ctx)

        available = sorted(set(self._classes.keys()) | self._configs)
        raise KeyError(
            f"Unknown operator '{name}'. "
            f"Available: {', '.join(available) or 'none'}"
        )

    def list_operators(self) -> list[str]:
        """List all registered operator names."""
        return sorted(set(self._classes.keys()) | self._configs)

    # ---- AIOSCP Host Methods ----

    def get_manifest(self, name: str) -> Optional[object]:
        """Get the AIOSCP manifest for a registered operator."""
        return self._manifests.get(name.lower())

    def get_all_manifests(self) -> dict[str, object]:
        """Get all AIOSCP manifests. Used by marketplace / discovery."""
        return dict(self._manifests)

    def get_capabilities(self, name: str) -> list:
        """Get AIOSCP capabilities for a specific operator."""
        manifest = self._manifests.get(name.lower())
        if manifest:
            return manifest.capabilities
        return []

    def estimate_task_cost(self, capability_ids: list[str]) -> str:
        """
        Estimate total cost for a set of capabilities.
        Used for cost estimation before task execution.

        Returns a cost range string like "$0.02-0.25".
        """
        min_total = 0.0
        max_total = 0.0

        for cap_id in capability_ids:
            cap = get_capability(cap_id)
            if cap and cap.metadata.cost_estimate:
                cost_str = cap.metadata.cost_estimate.replace("$", "")
                if "-" in cost_str:
                    parts = cost_str.split("-")
                    min_total += float(parts[0])
                    max_total += float(parts[1])
                else:
                    val = float(cost_str)
                    min_total += val
                    max_total += val

        if min_total == max_total:
            return f"${min_total:.2f}"
        return f"${min_total:.2f}-{max_total:.2f}"


    # ---- A2A: Level 1 — Swap ----

    def swap(
        self, current: str, target: str, chat_ctx: ChatContext = None
    ) -> BaseOperator:
        """
        Swap one operator for another. The current operator goes dormant,
        the target operator takes over with the chat context passed through.

        This is the multiagent_vid pattern — one at a time, baton pass.
        """
        current_key = current.lower()
        target_key = target.lower()

        # Deactivate current
        if current_key in self._instances:
            logger.info(f"[A2A:SWAP] {current_key} going dormant")
            del self._instances[current_key]

        # Spawn and activate target
        new_op = self.spawn(target_key, chat_ctx=chat_ctx)
        self._instances[target_key] = new_op
        logger.info(f"[A2A:SWAP] {current_key} -> {target_key}")
        return new_op

    # ---- A2A: Level 2 — Delegate ----

    async def delegate(
        self,
        from_operator: str,
        to_operator: str,
        description: str,
        context: dict = None,
        timeout: float = 120.0,
    ) -> A2ATask:
        """
        Delegate a task from one operator to another.
        The source operator continues running. The target
        operator is spawned (if not active), receives the task,
        processes it, and returns results.

        The OS handles everything: spawning, routing, tracking, timeout.
        The operator just calls: self.delegate("genesis", "research pricing")
        """
        task = A2ATask(
            from_operator=from_operator.lower(),
            to_operator=to_operator.lower(),
            description=description,
            context=context or {},
            status=TaskStatus.PENDING,
        )
        self._tasks[task.id] = task

        logger.info(
            f"[A2A:DELEGATE] {task.from_operator} -> {task.to_operator}: "
            f"'{description[:60]}' (task={task.id[:8]})"
        )

        # Spawn the target operator if not already active
        target_key = to_operator.lower()
        if target_key not in self._instances:
            self._instances[target_key] = self.spawn(target_key)

        target_op = self._instances[target_key]

        # Execute the task asynchronously with timeout
        task.status = TaskStatus.RUNNING
        try:
            result = await asyncio.wait_for(
                self._execute_delegated_task(target_op, task),
                timeout=timeout,
            )
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            logger.info(
                f"[A2A:DELEGATE] Task {task.id[:8]} completed "
                f"({task.completed_at - task.created_at:.1f}s)"
            )
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.error = f"Task timed out after {timeout}s"
            logger.error(f"[A2A:DELEGATE] Task {task.id[:8]} timed out")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"[A2A:DELEGATE] Task {task.id[:8]} failed: {e}")

        return task

    async def _execute_delegated_task(
        self, operator: BaseOperator, task: A2ATask
    ) -> Any:
        """
        Execute a delegated task on the target operator.
        Override this in subclasses for custom execution logic.
        Default: pass the task description through the Brain pipeline.
        """
        # The operator processes the task via its handle_task method
        if hasattr(operator, 'handle_task'):
            return await operator.handle_task(task.description, task.context)

        # Fallback: return the task description as-is (operator doesn't implement handle_task yet)
        logger.warning(
            f"[A2A:DELEGATE] {task.to_operator} has no handle_task method, "
            f"returning description as result"
        )
        return {"status": "received", "description": task.description}

    def get_task(self, task_id: str) -> Optional[A2ATask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_tasks_for(self, operator: str) -> list[A2ATask]:
        """Get all tasks delegated to or from an operator."""
        key = operator.lower()
        return [
            t for t in self._tasks.values()
            if t.from_operator == key or t.to_operator == key
        ]

    # ---- A2A: Level 3 — Collaborate (Message Bus) ----

    def subscribe(self, channel: str, callback: Callable) -> None:
        """
        Subscribe to a message channel. When a message is sent to this
        channel, all subscribers' callbacks are invoked.

        Operators call: self.subscribe("research", self.on_research_result)
        """
        if channel not in self._subscriptions:
            self._subscriptions[channel] = []
        self._subscriptions[channel].append(callback)
        logger.info(f"[A2A:MSG] Subscribed to channel '{channel}'")

    def unsubscribe(self, channel: str, callback: Callable) -> None:
        """Unsubscribe from a message channel."""
        if channel in self._subscriptions:
            self._subscriptions[channel] = [
                cb for cb in self._subscriptions[channel] if cb != callback
            ]

    async def message(
        self,
        from_operator: str,
        to_operator: str = "",
        body: Any = None,
        channel: str = "default",
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> A2AMessage:
        """
        Send a message from one operator to another (direct) or
        to all subscribers on a channel (broadcast).

        Direct:    registry.message("champ", to_operator="genesis", body="need pricing")
        Broadcast: registry.message("champ", channel="research", body=data)
        """
        msg = A2AMessage(
            from_operator=from_operator.lower(),
            to_operator=to_operator.lower() if to_operator else "",
            channel=channel,
            body=body,
            priority=priority,
        )

        if to_operator:
            # Direct message — deliver to specific operator
            target_key = to_operator.lower()
            if target_key in self._instances:
                target = self._instances[target_key]
                if hasattr(target, 'on_message'):
                    await target.on_message(msg)
            logger.info(
                f"[A2A:MSG] {msg.from_operator} -> {msg.to_operator}: "
                f"{str(body)[:60]}"
            )
        else:
            # Broadcast — deliver to all channel subscribers
            callbacks = self._subscriptions.get(channel, [])
            for cb in callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(msg)
                    else:
                        cb(msg)
                except Exception as e:
                    logger.error(f"[A2A:MSG] Subscriber error on '{channel}': {e}")

            logger.info(
                f"[A2A:MSG] {msg.from_operator} broadcast on '{channel}' "
                f"to {len(callbacks)} subscribers"
            )

        return msg

    def get_active_operators(self) -> list[str]:
        """List all currently active (running) operator instances."""
        return list(self._instances.keys())


# ---- Global registry instance ----
# Import and use this from anywhere in the OS.
registry = OperatorRegistry()