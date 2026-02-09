# ============================================
# CHAMP V3 — Healing Loop
# Brick 6: Real-time detection of friction
# patterns — wrong mode, looping, tool failure,
# user frustration. Pure Python, no LLM call.
# ============================================

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

from brain.models import OutputMode

logger = logging.getLogger(__name__)


@dataclass
class HealingResult:
    """Result of a healing detection pass."""
    issues: list[dict] = field(default_factory=list)
    mode_override: Optional[OutputMode] = None
    warning_text: str = ""


# ---- Pattern definitions ----

# User wants code/spec but mode detected as VIBE
SPEC_SIGNALS = [
    re.compile(r"\bgive me the code\b", re.IGNORECASE),
    re.compile(r"\bwrite me a? ?(?:script|function|class|program)\b", re.IGNORECASE),
    re.compile(r"\bcode (?:for|to)\b", re.IGNORECASE),
    re.compile(r"\bgenerate (?:a |the )?(?:script|code|file)\b", re.IGNORECASE),
    re.compile(r"\bcopy.?paste ready\b", re.IGNORECASE),
]

# User wants casual/explanation but mode detected as SPEC
VIBE_SIGNALS = [
    re.compile(r"\bexplain\b", re.IGNORECASE),
    re.compile(r"\bwhat do you think\b", re.IGNORECASE),
    re.compile(r"\btell me about\b", re.IGNORECASE),
    re.compile(r"\bhow does .+ work\b", re.IGNORECASE),
    re.compile(r"\bwhy (?:did|does|is|would)\b", re.IGNORECASE),
]

# Tool failure signals from user
TOOL_FAILURE_SIGNALS = [
    re.compile(r"\bit didn'?t work\b", re.IGNORECASE),
    re.compile(r"\bthat'?s wrong\b", re.IGNORECASE),
    re.compile(r"\btry again\b", re.IGNORECASE),
    re.compile(r"\bthat broke\b", re.IGNORECASE),
    re.compile(r"\bgot an error\b", re.IGNORECASE),
    re.compile(r"\bnot working\b", re.IGNORECASE),
]

# User friction / frustration signals
USER_FRICTION_SIGNALS = [
    re.compile(r"\byou'?re spinning\b", re.IGNORECASE),
    re.compile(r"\bstop\b", re.IGNORECASE),
    re.compile(r"\bthat'?s not what I (?:asked|meant|said)\b", re.IGNORECASE),
    re.compile(r"\bcome on\b", re.IGNORECASE),
    re.compile(r"\byou already said that\b", re.IGNORECASE),
    re.compile(r"\byou'?re repeating\b", re.IGNORECASE),
    re.compile(r"\bforget it\b", re.IGNORECASE),
]

# Looping similarity threshold
LOOPING_THRESHOLD = 0.80


class HealingLoop:
    """
    Real-time friction detection.

    Runs on every request (no LLM call — pure regex/string matching).
    Detects wrong mode, looping, tool failures, and user frustration.
    Returns a HealingResult with optional mode override and warning text.
    """

    def detect(
        self,
        user_message: str,
        mode: OutputMode,
        recent_messages: list[dict],
    ) -> HealingResult:
        """
        Run all detectors and return aggregated result.

        Args:
            user_message: The current user message text
            mode: The mode detected by ModeDetector
            recent_messages: Last N messages from conversation
        """
        issues = []

        # 1. Wrong mode detection
        wrong_mode = self._detect_wrong_mode(user_message, mode)
        if wrong_mode:
            issues.append(wrong_mode)

        # 2. Looping detection
        looping = self._detect_looping(recent_messages)
        if looping:
            issues.append(looping)

        # 3. Tool failure detection
        tool_fail = self._detect_tool_failure(user_message)
        if tool_fail:
            issues.append(tool_fail)

        # 4. User friction detection
        friction = self._detect_user_friction(user_message)
        if friction:
            issues.append(friction)

        # Build result
        mode_override = None
        for issue in issues:
            if issue["type"] == "wrong_mode" and issue.get("suggested_mode"):
                mode_override = issue["suggested_mode"]
                break

        warning_text = self._build_warning(issues) if issues else ""

        if issues:
            logger.info(
                f"[HEALING] {len(issues)} issues detected: "
                f"{[i['type'] for i in issues]}"
            )

        return HealingResult(
            issues=issues,
            mode_override=mode_override,
            warning_text=warning_text,
        )

    def _detect_wrong_mode(
        self, user_message: str, mode: OutputMode
    ) -> Optional[dict]:
        """Check if the detected mode mismatches user intent."""
        # User wants code but mode is VIBE
        if mode == OutputMode.VIBE:
            for pattern in SPEC_SIGNALS:
                if pattern.search(user_message):
                    return {
                        "type": "wrong_mode",
                        "severity": "medium",
                        "context": f"User wants code/spec but mode={mode.value}",
                        "rule": "Switch to SPEC mode for code requests",
                        "suggested_mode": OutputMode.SPEC,
                    }

        # User wants explanation but mode is SPEC
        if mode == OutputMode.SPEC:
            for pattern in VIBE_SIGNALS:
                if pattern.search(user_message):
                    return {
                        "type": "wrong_mode",
                        "severity": "medium",
                        "context": f"User wants explanation but mode={mode.value}",
                        "rule": "Switch to VIBE mode for explanations",
                        "suggested_mode": OutputMode.VIBE,
                    }

        return None

    def _detect_looping(self, recent_messages: list[dict]) -> Optional[dict]:
        """Check if the last 2 assistant responses are too similar."""
        assistant_msgs = [
            m["content"]
            for m in recent_messages
            if m.get("role") == "assistant" and m.get("content")
        ]

        if len(assistant_msgs) < 2:
            return None

        last_two = assistant_msgs[-2:]
        similarity = SequenceMatcher(
            None, last_two[0], last_two[1]
        ).ratio()

        if similarity >= LOOPING_THRESHOLD:
            return {
                "type": "looping",
                "severity": "high",
                "context": f"Last 2 responses {similarity:.0%} similar",
                "rule": "Break the loop — try a different approach or acknowledge the repetition",
            }

        return None

    def _detect_tool_failure(self, user_message: str) -> Optional[dict]:
        """Check if user is reporting a tool failure."""
        for pattern in TOOL_FAILURE_SIGNALS:
            if pattern.search(user_message):
                return {
                    "type": "tool_failure",
                    "severity": "medium",
                    "context": f"User reported failure: '{user_message[:80]}'",
                    "rule": "Acknowledge the error, try a different approach",
                }
        return None

    def _detect_user_friction(self, user_message: str) -> Optional[dict]:
        """Check if user is expressing frustration."""
        for pattern in USER_FRICTION_SIGNALS:
            if pattern.search(user_message):
                return {
                    "type": "user_friction",
                    "severity": "high",
                    "context": f"User friction detected: '{user_message[:80]}'",
                    "rule": "Pause, acknowledge, and reset approach",
                }
        return None

    def _build_warning(self, issues: list[dict]) -> str:
        """Format issues into a warning string for system prompt injection."""
        lines = ["[HEALING WARNING]"]
        for issue in issues:
            severity = issue["severity"].upper()
            lines.append(
                f"- [{severity}] {issue['type']}: {issue['rule']}"
            )
        return "\n".join(lines)
