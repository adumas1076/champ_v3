# ============================================
# CHAMP V3 — Mode Detector
# Analyzes user input BEFORE the LLM call
# to detect Vibe / Build / Spec mode.
# ============================================
# Priority:
#   1. Explicit cues override everything
#   2. Inference from request shape
#   3. Default to Vibe when uncertain
# ============================================

import re
import logging

from brain.models import OutputMode

logger = logging.getLogger(__name__)


# -----------------------------------------------------------
# Trigger patterns — extracted from persona V1.6.1 Mode Selector
# Check order: SPEC > BUILD > VIBE (strongest signal first)
# -----------------------------------------------------------

SPEC_TRIGGERS = [
    r"\bcopy/?paste\b",
    r"\bfinal\b",
    r"\blocked\b",
    r"\bprompt\b",
    r"\bscript\b",
    r"\bsop\b",
    r"\bspec\b",
    r"\bjson\b",
    r"\btemplate\b",
    r"\bship it\b",
    r"\bgive me the code\b",
    r"\bjust the code\b",
    r"\bi need exact\b",
    r"\bspecific\b",
    r"\bexact\b",
    r"\bdeliverable\b",
]

BUILD_TRIGGERS = [
    r"\blet'?s build\b",
    r"\bstep by step\b",
    r"\bwalk me through\b",
    r"\bone at a time\b",
    r"\bhow do we\b",
    r"\bhow would we\b",
    r"\bbreak it down\b",
    r"\bbreak this down\b",
    r"\bwalk through\b",
    r"\bhelp me build\b",
    r"\bcreate\b",
    r"\blet'?s make\b",
]

VIBE_TRIGGERS = [
    r"\bquick\b",
    r"\breal quick\b",
    r"\bthoughts\??",
    r"\bwhat you think\??",
    r"\bwhat do you think\??",
    r"\byes or no\b",
    r"\byeah or nah\b",
]

# Inference patterns — no explicit cue, infer from request shape
BUILD_INFERENCE = [
    r"\bhow (do|can|should|would) (I|we)\b",
    r"\barchitect",
    r"\bdebug",
    r"\bplan\b",
    r"\bstrateg",
    r"\bdiagram\b",
    r"\bworkflow\b",
]

SPEC_INFERENCE = [
    r"\bwrite\b.{0,30}\b(code|function|class|script|prompt|email|doc|SOP)\b",
    r"\bgenerate\b",
    r"\bcreate\b.{0,30}\b(file|document|template|page|component)\b",
]


class ModeDetector:
    """
    Detects output mode from user input.
    Runs BEFORE the LLM call to adjust the system prompt.

    Priority:
    1. Explicit cues (highest) — direct phrases from persona spec
    2. Inference — request shape implies a mode
    3. Default — Vibe Mode (short, keep momentum)
    """

    def detect(self, user_message: str) -> OutputMode:
        """Analyze user input and return the detected mode."""
        text = user_message.lower().strip()

        if not text:
            return OutputMode.VIBE

        # Priority 1: Explicit cues (SPEC > BUILD > VIBE)
        if self._matches_any(text, SPEC_TRIGGERS):
            logger.info(f"Mode: SPEC (explicit) | '{text[:60]}'")
            return OutputMode.SPEC

        if self._matches_any(text, BUILD_TRIGGERS):
            logger.info(f"Mode: BUILD (explicit) | '{text[:60]}'")
            return OutputMode.BUILD

        if self._matches_any(text, VIBE_TRIGGERS):
            logger.info(f"Mode: VIBE (explicit) | '{text[:60]}'")
            return OutputMode.VIBE

        # Priority 2: Inference from request shape
        if self._matches_any(text, SPEC_INFERENCE):
            logger.info(f"Mode: SPEC (inferred) | '{text[:60]}'")
            return OutputMode.SPEC

        if self._matches_any(text, BUILD_INFERENCE):
            logger.info(f"Mode: BUILD (inferred) | '{text[:60]}'")
            return OutputMode.BUILD

        # Priority 3: Default to Vibe
        logger.info(f"Mode: VIBE (default) | '{text[:60]}'")
        return OutputMode.VIBE

    def _matches_any(self, text: str, patterns: list[str]) -> bool:
        """Check if text matches any pattern in the list."""
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)
