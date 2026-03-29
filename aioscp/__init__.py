"""
AIOSCP — AI Operating System Communication Protocol
Python SDK v1.0

Build AI operators that run on any AIOSCP-compatible host.
"""

from aioscp.operator import Operator
from aioscp.decorators import capability, on_message, on_task, on_heal
from aioscp.types import (
    TrustLevel,
    TaskStatus,
    MessageType,
    ContextScope,
    Capability as CapabilityDef,
    Task,
    Message,
    Context,
    HealthStatus,
    OperatorManifest,
)
from aioscp.host import Host
from aioscp.transport import StdioTransport, WebSocketTransport, HTTPTransport

__version__ = "1.0.0"
__protocol_version__ = "1.0"

__all__ = [
    "Operator",
    "Host",
    "capability",
    "on_message",
    "on_task",
    "on_heal",
    "TrustLevel",
    "TaskStatus",
    "MessageType",
    "ContextScope",
    "CapabilityDef",
    "Task",
    "Message",
    "Context",
    "HealthStatus",
    "OperatorManifest",
    "StdioTransport",
    "WebSocketTransport",
    "HTTPTransport",
]
