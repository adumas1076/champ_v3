# ============================================
# CHAMP V3 — AIOSCP Bridge
# Connects the V3 operator system to the
# AIOSCP protocol. The OS IS the Host.
#
# This bridge:
# 1. Translates OS tools → AIOSCP Capabilities
# 2. Generates AIOSCP OperatorManifest from configs
# 3. Makes the OperatorRegistry an AIOSCP Host
# 4. Enables cost estimation per capability
#
# Architecture:
#   The AIOSCP layer wraps the OS (outside).
#   Operators don't know they're speaking AIOSCP.
#   The OS handles protocol compliance.
# ============================================

import logging
import yaml
from pathlib import Path
from typing import Optional

# Import from the AIOSCP SDK (lives at aioscp/sdk/python/)
import sys
_aioscp_sdk_path = str(Path(__file__).resolve().parent.parent.parent / "aioscp" / "sdk" / "python")
if _aioscp_sdk_path not in sys.path:
    sys.path.insert(0, _aioscp_sdk_path)

from aioscp.types import (
    TrustLevel,
    Capability,
    CapabilityMeta,
    OperatorManifest,
    Persona,
    HealthState,
    HealthStatus,
    Task,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# ---- AIOSCP Capability definitions for OS tools ----
# Each OS tool gets a structured AIOSCP capability with
# cost estimates, latency, confidence, and side effects.
# This is what other operators and the marketplace see.

OS_CAPABILITIES = [
    # === INPUT (Eyes) ===
    Capability(
        id="analyze_screen",
        name="Analyze Screen",
        description="Take a screenshot and analyze it with a vision model. "
                    "Understands UI, text, code, errors — anything visible.",
        input_schema={
            "question": {"type": "string", "description": "What to analyze"},
            "url": {"type": "string", "description": "Optional URL to screenshot first"},
            "model": {"type": "string", "enum": ["gemini-flash", "gpt-4o", "claude-sonnet"]},
        },
        output_schema={"analysis": {"type": "string"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.005-0.05",
            avg_latency_ms=3000,
            confidence=0.85,
            requires_approval=False,
            idempotent=True,
            side_effects=[],
        ),
    ),
    Capability(
        id="read_screen",
        name="Read Screen",
        description="Read UI elements visible on screen or in a specific window.",
        input_schema={"window_title": {"type": "string"}},
        output_schema={"elements": {"type": "array"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.00",
            avg_latency_ms=500,
            confidence=0.90,
            side_effects=[],
        ),
    ),

    # === THINK (Brain) ===
    Capability(
        id="ask_brain",
        name="Ask Brain",
        description="Deep thinking via the Brain API. Uses Claude Sonnet with "
                    "full persona, memory context, and mode detection.",
        input_schema={"question": {"type": "string"}},
        output_schema={"answer": {"type": "string"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.01-0.10",
            avg_latency_ms=5000,
            confidence=0.90,
            side_effects=[],
        ),
    ),

    # === ACT (Hands — Browser) ===
    Capability(
        id="browse_url",
        name="Browse URL",
        description="Navigate to a URL in the user's real browser. "
                    "Undetectable — uses cookies, sessions, everything.",
        input_schema={"url": {"type": "string"}},
        output_schema={"title": {"type": "string"}, "text": {"type": "string"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.00",
            avg_latency_ms=3000,
            confidence=0.95,
            side_effects=["browser_navigation"],
        ),
    ),
    Capability(
        id="google_search",
        name="Google Search",
        description="Search Google using the user's real browser with personalized results.",
        input_schema={"query": {"type": "string"}},
        output_schema={"results": {"type": "array"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.00",
            avg_latency_ms=4000,
            confidence=0.95,
            side_effects=["browser_navigation"],
        ),
    ),
    Capability(
        id="fill_web_form",
        name="Fill Web Form",
        description="Fill form fields on a webpage with human-like typing.",
        input_schema={
            "url": {"type": "string"},
            "fields": {"type": "array", "items": {"type": "object"}},
        },
        output_schema={"fields_filled": {"type": "integer"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.00",
            avg_latency_ms=5000,
            confidence=0.85,
            requires_approval=True,
            side_effects=["form_submission", "browser_navigation"],
        ),
    ),
    Capability(
        id="take_screenshot",
        name="Take Screenshot",
        description="Capture a screenshot of the screen or a webpage.",
        input_schema={"url": {"type": "string"}},
        output_schema={"path": {"type": "string"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.00",
            avg_latency_ms=2000,
            confidence=0.95,
            side_effects=["file_write"],
        ),
    ),

    # === ACT (Hands — Desktop) ===
    Capability(
        id="control_desktop",
        name="Control Desktop",
        description="Control any desktop app — open, click, type, press keys, scroll.",
        input_schema={"instruction": {"type": "string"}},
        output_schema={"result": {"type": "object"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.00",
            avg_latency_ms=1000,
            confidence=0.80,
            side_effects=["desktop_interaction", "app_launch", "keystroke"],
        ),
    ),

    # === ACT (Hands — Code) ===
    Capability(
        id="run_code",
        name="Run Code",
        description="Execute Python or JavaScript code and return output.",
        input_schema={
            "code": {"type": "string"},
            "language": {"type": "string", "enum": ["python", "javascript"]},
        },
        output_schema={"output": {"type": "string"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.00",
            avg_latency_ms=2000,
            confidence=0.90,
            side_effects=["code_execution"],
        ),
    ),
    Capability(
        id="create_file",
        name="Create File",
        description="Create a file with given content and save it.",
        input_schema={
            "filename": {"type": "string"},
            "content": {"type": "string"},
        },
        output_schema={"path": {"type": "string"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.00",
            avg_latency_ms=100,
            confidence=0.99,
            side_effects=["file_write"],
        ),
    ),

    # === THINK (Cost Estimation) ===
    Capability(
        id="estimate_task",
        name="Estimate Task Cost",
        description="Estimate cost and time for a task BEFORE executing it. "
                    "Analyzes which capabilities would be needed and returns a breakdown.",
        input_schema={"task": {"type": "string", "description": "Task description to estimate"}},
        output_schema={
            "estimated_cost": {"type": "string"},
            "estimated_time": {"type": "string"},
            "capabilities_needed": {"type": "integer"},
        },
        metadata=CapabilityMeta(
            cost_estimate="$0.00",
            avg_latency_ms=50,
            confidence=0.75,
            side_effects=[],
        ),
    ),

    # === ACT (Hands — Self Mode) ===
    Capability(
        id="go_do",
        name="Autonomous Task",
        description="Hand off a multi-step task to Self Mode for autonomous execution. "
                    "Plans, builds, tests, and delivers results without supervision.",
        input_schema={"task": {"type": "string"}},
        output_schema={"run_id": {"type": "string"}},
        metadata=CapabilityMeta(
            cost_estimate="$0.10-2.00",
            avg_latency_ms=300000,
            confidence=0.70,
            requires_approval=True,
            idempotent=False,
            side_effects=["code_execution", "file_write", "browser_navigation"],
        ),
    ),
]

# Build lookup: capability_id → Capability
_CAPABILITY_MAP = {cap.id: cap for cap in OS_CAPABILITIES}


def get_os_capabilities() -> list[Capability]:
    """Return all OS-level AIOSCP capabilities."""
    return list(OS_CAPABILITIES)


def get_capability(capability_id: str) -> Optional[Capability]:
    """Look up a single capability by ID."""
    return _CAPABILITY_MAP.get(capability_id)


def estimate_cost(capability_id: str) -> Optional[str]:
    """Get the cost estimate for a capability."""
    cap = _CAPABILITY_MAP.get(capability_id)
    return cap.metadata.cost_estimate if cap else None


# ---- Manifest generation ----

def generate_manifest(
    operator_name: str,
    config_path: Optional[Path] = None,
    extra_capabilities: Optional[list[Capability]] = None,
) -> OperatorManifest:
    """
    Generate an AIOSCP OperatorManifest from an operator config.

    This is what the protocol sees — a structured description of
    who this operator is and what it can do.
    """
    config = {}
    if config_path and config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # Build persona from config
    voice_config = config.get("voice", {})
    persona = Persona(
        role=config.get("description", f"{operator_name} operator"),
        voice=voice_config.get("voice"),
        backstory=None,
        avatar=None,
    )

    # Determine capabilities: OS capabilities + any extras
    # If tool_permissions is set, filter OS capabilities to match
    perms = config.get("tool_permissions")
    if perms:
        perm_set = set(perms)
        capabilities = [c for c in OS_CAPABILITIES if c.id in perm_set]
    else:
        capabilities = list(OS_CAPABILITIES)

    if extra_capabilities:
        capabilities.extend(extra_capabilities)

    # Determine trust level from config
    trust = TrustLevel.SYSTEM  # Default for CHAMP operators (full access)
    if perms:
        # Restricted operators get lower trust
        has_desktop = any(c.id in ("control_desktop", "run_code") for c in capabilities)
        has_network = any(c.id in ("browse_url", "google_search") for c in capabilities)
        if has_desktop:
            trust = TrustLevel.SYSTEM
        elif has_network:
            trust = TrustLevel.NETWORK
        else:
            trust = TrustLevel.LOCAL

    manifest = OperatorManifest(
        id=operator_name.lower(),
        name=config.get("display_name", operator_name),
        version="1.0.0",
        description=config.get("description", ""),
        author=config.get("owner", "champ-os"),
        persona=persona,
        capabilities=capabilities,
        trust_level=trust,
        model_preference=config.get("model_preference", "auto"),
    )

    logger.info(
        f"[AIOSCP] Generated manifest for '{operator_name}': "
        f"{len(capabilities)} capabilities, trust={trust.name}"
    )

    return manifest


def generate_health(
    status: str = "idle",
    progress: float = 0.0,
    current_action: str = "",
    tokens_used: int = 0,
    cost_so_far: str = "$0.00",
) -> HealthStatus:
    """Generate an AIOSCP HealthStatus for an operator."""
    state_map = {
        "idle": HealthState.IDLE,
        "active": HealthState.ACTIVE,
        "stuck": HealthState.STUCK,
        "error": HealthState.ERROR,
    }
    return HealthStatus(
        status=state_map.get(status, HealthState.IDLE),
        progress=progress,
        tokens_used=tokens_used,
        cost_so_far=cost_so_far,
        current_action=current_action,
    )