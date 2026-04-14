"""
AIOSCP core types — data classes for the six primitives.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import IntEnum, Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TrustLevel(IntEnum):
    """How much system access an operator is granted."""
    SANDBOXED = 0  # Own task context only, no network, no filesystem
    LOCAL = 1      # Task + conversation context, read-only files
    NETWORK = 2    # + network, file write, browser
    SYSTEM = 3     # + desktop control, process management, global context write


class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    INFORM = "inform"
    ERROR = "error"
    ALERT = "alert"
    HANDOFF = "handoff"                      # Transfer task ownership to another operator
    ESCALATION = "escalation"                # Escalate to human or higher-trust operator
    APPROVAL_REQUEST = "approval_request"    # Need human/operator approval before proceeding
    APPROVAL_RESPONSE = "approval_response"  # Approve/deny with optional feedback


class ContextScope(str, Enum):
    TASK = "task"
    CONVERSATION = "conversation"
    OPERATOR = "operator"
    GLOBAL = "global"


class HealthState(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    STUCK = "stuck"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Persona
# ---------------------------------------------------------------------------

@dataclass
class Persona:
    role: str
    voice: Optional[str] = None
    backstory: Optional[str] = None
    avatar: Optional[str] = None


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------

@dataclass
class CapabilityMeta:
    cost_estimate: Optional[str] = None
    avg_latency_ms: Optional[int] = None
    confidence: float = 0.8
    requires_approval: bool = False
    idempotent: bool = True
    side_effects: list[str] = field(default_factory=list)
    # Safety flags — fail-closed defaults (from Claude Code patterns)
    concurrency_safe: bool = False    # Can run in parallel with other capabilities?
    destructive: bool = False         # Deletes, overwrites, or sends externally?
    read_only: bool = False           # Pure observation, no state change?


@dataclass
class Capability:
    id: str
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    metadata: CapabilityMeta = field(default_factory=CapabilityMeta)
    handler: Any = None  # Set by @capability decorator


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@dataclass
class Deliverable:
    type: str = "none"  # markdown, json, file, none
    destination: Optional[str] = None


@dataclass
class Verification:
    self_checked: bool = False
    method: Optional[str] = None  # output_validation, test_run, human_review


@dataclass
class Task:
    id: str = field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    description: str = ""
    created_by: str = ""
    assigned_to: str = ""
    parent_task_id: Optional[str] = None
    priority: str = "normal"
    deadline: Optional[str] = None
    max_cost: Optional[str] = None
    deliverable: Deliverable = field(default_factory=Deliverable)
    on_complete: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.CREATED
    progress: float = 0.0
    cost_so_far: str = "$0.00"
    tokens_used: int = 0
    # Dependency graph — which tasks block/are blocked by this one
    blocks: list[str] = field(default_factory=list)        # Task IDs this task blocks
    blocked_by: list[str] = field(default_factory=list)    # Task IDs blocking this task
    requires_verification: bool = False                     # Must pass QA before marking complete


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

@dataclass
class Message:
    id: str = field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:8]}")
    from_id: str = ""
    to_id: str = ""
    type: MessageType = MessageType.INFORM
    correlation_id: Optional[str] = None
    body: Any = None
    expires_ms: Optional[int] = None
    resume_on_delivery: bool = False  # If recipient is stopped, restart it to deliver


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class Context:
    scope: ContextScope = ContextScope.TASK
    key: str = ""
    value: Any = None
    task_id: Optional[str] = None
    visible_to: list[str] = field(default_factory=list)
    ttl_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@dataclass
class HealthStatus:
    status: HealthState = HealthState.IDLE
    progress: float = 0.0
    tokens_used: int = 0
    cost_so_far: str = "$0.00"
    current_action: str = ""


# ---------------------------------------------------------------------------
# Operator Manifest (parsed from YAML)
# ---------------------------------------------------------------------------

@dataclass
class OperatorManifest:
    id: str = ""
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    license: str = "MIT"
    persona: Persona = field(default_factory=Persona)
    capabilities: list[Capability] = field(default_factory=list)
    trust_level: TrustLevel = TrustLevel.LOCAL
    model_preference: str = "auto"
    max_tokens_per_task: int = 100000
