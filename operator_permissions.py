# ============================================
# Cocreatiq V1 — Operator Permission System
# Each operator gets specific tool access
# Pattern: Claude Code discriminated unions + our operator pack
# ============================================

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# Default tool sets per operator type
TOOL_PRESETS = {
    "full_access": None,  # None = all tools (Champ, Operations)
    "champ": None,  # Champ = full access
    "sales": [
        "browse_url", "google_search", "get_web_content",
        "analyze_screen", "take_screenshot",
        "manage_tasks", "take_notes",
        "get_youtube_transcript", "get_web_content",
    ],
    "billing": [
        "browse_url", "google_search",
        "read_file", "create_file",
        "manage_tasks", "take_notes",
        "run_code",
    ],
    "support": [
        "browse_url", "google_search", "get_web_content",
        "analyze_screen", "take_screenshot", "read_screen",
        "read_file", "search_files", "list_directory",
        "manage_tasks", "take_notes",
    ],
    "assistant": [
        "browse_url", "google_search", "get_web_content",
        "manage_tasks", "take_notes",
        "get_weather", "clipboard",
        "get_youtube_transcript", "get_pdf_content",
    ],
    "operations": None,  # Full access
    "retention": [
        "browse_url", "google_search", "get_web_content",
        "manage_tasks", "take_notes",
        "analyze_screen",
    ],
    "content": [
        "browse_url", "google_search", "get_web_content",
        "get_youtube_transcript", "get_podcast_transcript", "get_pdf_content",
        "create_file", "read_file", "edit_file",
        "manage_tasks", "take_notes",
        "run_code",
    ],
    "growth": [
        "browse_url", "google_search", "get_web_content",
        "fill_web_form", "analyze_screen", "take_screenshot",
        "get_youtube_transcript", "get_web_content",
        "manage_tasks", "take_notes",
    ],
}

# Tools that are NEVER allowed for non-admin operators
DANGEROUS_TOOLS = [
    "run_shell",
    "git_command",
    "self_correct",
    "control_desktop",
]


@dataclass
class PermissionSet:
    """Permission configuration for an operator."""
    operator_name: str
    allowed_tools: Optional[list[str]] = None  # None = all
    disallowed_tools: list[str] = field(default_factory=list)
    max_turns: Optional[int] = None
    can_self_mode: bool = False
    can_escalate: bool = True


def get_permissions(operator_name: str, custom_allowed: Optional[list[str]] = None) -> PermissionSet:
    """Get permission set for an operator."""
    name = operator_name.lower()

    # Custom override from operator pack
    if custom_allowed is not None:
        return PermissionSet(
            operator_name=name,
            allowed_tools=custom_allowed,
            disallowed_tools=DANGEROUS_TOOLS if custom_allowed is not None else [],
            can_self_mode=(custom_allowed is None),
        )

    # Preset lookup
    preset = TOOL_PRESETS.get(name)

    # Full access operators
    if preset is None and name in TOOL_PRESETS:
        return PermissionSet(
            operator_name=name,
            allowed_tools=None,
            disallowed_tools=[],
            can_self_mode=True,
        )

    # Limited access operators
    if preset is not None:
        return PermissionSet(
            operator_name=name,
            allowed_tools=preset,
            disallowed_tools=DANGEROUS_TOOLS,
            can_self_mode=False,
        )

    # Unknown operator — safe defaults
    logger.warning(f"No permission preset for '{name}', using safe defaults")
    return PermissionSet(
        operator_name=name,
        allowed_tools=TOOL_PRESETS["assistant"],
        disallowed_tools=DANGEROUS_TOOLS,
        can_self_mode=False,
    )


def check_tool_permission(permissions: PermissionSet, tool_name: str) -> bool:
    """Check if a tool is allowed for this operator."""
    # Explicitly blocked
    if tool_name in permissions.disallowed_tools:
        return False

    # Full access
    if permissions.allowed_tools is None:
        return True

    # Allowlist check
    return tool_name in permissions.allowed_tools


def filter_tools(permissions: PermissionSet, available_tools: list) -> list:
    """Filter a tool list to only what this operator is allowed to use."""
    if permissions.allowed_tools is None and not permissions.disallowed_tools:
        return available_tools

    return [
        tool for tool in available_tools
        if check_tool_permission(permissions, getattr(tool, 'name', str(tool)))
    ]