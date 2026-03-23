# ============================================
# CHAMP V3 — Loop Selector
# Analyzes user input BEFORE the LLM call
# to select the right execution loop.
#
# The OS governs the loop. The operator runs it.
#
# 8 Loops (from 0004_loop_taxonomy.md):
#   1. Direct    — INPUT → THINK → RESPOND
#   2. Action    — INPUT → THINK → ACT → RESPOND
#   3. Verify    — INPUT → THINK → ACT → VERIFY → RESPOND
#   4. Autonomous — INPUT → (THINK → ACT → VERIFY)ⁿ → RESPOND
#   5. Handoff   — INPUT → THINK → DELEGATE → WAIT → RESPOND
#   6. Healing   — ERROR → THINK → ACT → VERIFY → RETRY
#   7. Memory    — INTERACTION → THINK → STORE
#   8. Watch     — OBSERVE → THINK → ACT IF NEEDED
#
# Priority:
#   1. Explicit cues override everything
#   2. Inference from request complexity
#   3. Default to Direct when uncertain
# ============================================

import re
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class LoopType(str, Enum):
    DIRECT = "direct"           # Simple Q&A, no tools
    ACTION = "action"           # One tool call, then respond
    VERIFY = "verify"           # Tool call + check result
    AUTONOMOUS = "autonomous"   # Multi-step Self Mode
    HANDOFF = "handoff"         # Delegate to another operator
    HEALING = "healing"         # Self-correction (triggered internally)
    MEMORY = "memory"           # Store info (triggered internally)
    WATCH = "watch"             # Continuous monitoring (triggered internally)


# -----------------------------------------------------------
# Trigger patterns — detect loop type from user input
# Check order: AUTONOMOUS > HANDOFF > VERIFY > ACTION > DIRECT
# (most specific first, broadest last)
# -----------------------------------------------------------

# Autonomous: multi-step, build something, needs a plan
AUTONOMOUS_TRIGGERS = [
    r"\bbuild me\b",
    r"\bcreate (a|me|the)\b.{0,30}(script|tool|app|pipeline|scraper|bot|system)",
    r"\bmake (a|me|the)\b.{0,30}(script|tool|app|pipeline|scraper|bot|system)",
    r"\bwrite (a|me|the)\b.{0,30}(script|tool|app|pipeline|scraper|program)",
    r"\bautomate\b",
    r"\bbuild\b.{0,20}\bfrom scratch\b",
    r"\bset up\b.{0,20}\b(pipeline|system|workflow|integration)\b",
    r"\bgo do\b",
    r"\bself mode\b",
    r"\bautonomous",
]

# Handoff: route to another operator
HANDOFF_TRIGGERS = [
    r"\b(get|ask|call|connect|transfer|hand off|switch to)\b.{0,20}\b(billy|genesis|sadie|another|other)\b",
    r"\bdelegate\b",
    r"\bhand (this|it) off\b",
    r"\blet .{0,15} handle\b",
    r"\bswitch (to|me to)\b",
]

# Verify: do something and check the result
VERIFY_TRIGGERS = [
    r"\b(and|then) (check|verify|confirm|make sure|validate|test)\b",
    r"\b(screenshot|look at|analyze|read).{0,30}(and|then)\b",
    r"\bmake sure\b",
    r"\bverify\b",
    r"\bdouble check\b",
    r"\bconfirm\b.{0,20}\b(it|that|this)\b",
]

# Action: single tool call (browser, desktop, code, search, screenshot)
ACTION_TRIGGERS = [
    r"\b(open|launch|start|run|close|quit)\b.{0,20}\b(app|chrome|spotify|excel|code|terminal|browser)",
    r"\b(go to|visit|browse|navigate|check)\b.{0,20}\b(website|page|site|url|http)",
    r"\bgoogle\b",
    r"\bsearch (for|up)\b",
    r"\btake a screenshot\b",
    r"\bscreenshot\b",
    r"\b(open|click|type|press|scroll)\b",
    r"\bfill (out|in|the)\b.{0,20}form\b",
    r"\brun (this|the|my|some) code\b",
    r"\bcreate (a|the) file\b",
    r"\bsave (this|it|the file)\b",
    r"\bcontrol\b.{0,10}\bdesktop\b",
    r"\bweather\b",
]

# Direct: simple question, no tools needed
DIRECT_TRIGGERS = [
    r"\bwhat (is|are|was|were|does|do)\b",
    r"\bwho (is|are|was)\b",
    r"\bwhen (is|was|did|will)\b",
    r"\bwhere (is|are|was)\b",
    r"\bwhy (is|are|did|do|does|would)\b",
    r"\bhow (is|are|was|were)\b",
    r"\bexplain\b",
    r"\btell me about\b",
    r"\bdefine\b",
    r"\bmeaning of\b",
    r"^(yes|no|yeah|nah|yep|nope|ok|okay|sure|bet|cool|got it|copy)",
    r"\bthoughts\??$",
    r"\bwhat you think\??$",
]

# Inference: when no explicit trigger, infer from complexity
ACTION_INFERENCE = [
    r"\b(look at|see|read|show me)\b.{0,20}\b(screen|page|this|that)\b",
    r"\banalyze\b",
    r"\bdescribe\b.{0,20}\b(screen|page|image|what)\b",
]

AUTONOMOUS_INFERENCE = [
    r"\b(need|want) (a|the)\b.{0,30}\b(that|which|to)\b",
    r"\bmulti.?step\b",
    r"\bcomplex\b.{0,20}\b(task|project|build)\b",
]


# -----------------------------------------------------------
# Loop instructions — injected into the LLM context
# Tells the operator HOW to execute this loop pattern
# -----------------------------------------------------------

LOOP_INSTRUCTIONS = {
    LoopType.DIRECT: (
        "\n\n[LOOP: DIRECT] Answer directly. No tools needed. "
        "Keep it conversational."
    ),
    LoopType.ACTION: (
        "\n\n[LOOP: ACTION] Use the right tool, then respond with the result. "
        "One tool call, clear response."
    ),
    LoopType.VERIFY: (
        "\n\n[LOOP: VERIFY] Use the tool, then VERIFY the result before responding. "
        "If the result looks wrong, try again or flag it. "
        "Do not respond until you have confirmed the result is correct."
    ),
    LoopType.AUTONOMOUS: (
        "\n\n[LOOP: AUTONOMOUS] This is a multi-step task. "
        "Use estimate_task first to estimate cost. "
        "Then use go_do to hand it to Self Mode. "
        "Tell the user the estimate and that you are on it."
    ),
    LoopType.HANDOFF: (
        "\n\n[LOOP: HANDOFF] The user wants another operator. "
        "Acknowledge the request and initiate the handoff. "
        "Pass relevant context so the other operator does not start from zero."
    ),
    LoopType.HEALING: "",   # Triggered internally, not from user input
    LoopType.MEMORY: "",    # Triggered internally
    LoopType.WATCH: "",     # Triggered internally
}


class LoopSelector:
    """
    Selects the execution loop pattern from user input.
    Runs BEFORE the LLM call, alongside ModeDetector.

    ModeDetector = HOW to respond (Vibe/Build/Spec format)
    LoopSelector = WHAT pattern to follow (Direct/Action/Verify/Autonomous/Handoff)

    Priority:
    1. Explicit cues (highest) — direct phrases
    2. Inference — request complexity implies a loop
    3. Default — Direct Loop (just answer)
    """

    def select(self, user_message: str) -> LoopType:
        """Analyze user input and return the selected loop."""
        text = user_message.lower().strip()

        if not text:
            return LoopType.DIRECT

        # Priority 1: Explicit cues (most specific first)
        if self._matches_any(text, AUTONOMOUS_TRIGGERS):
            logger.info(f"Loop: AUTONOMOUS (explicit) | '{text[:60]}'")
            return LoopType.AUTONOMOUS

        if self._matches_any(text, HANDOFF_TRIGGERS):
            logger.info(f"Loop: HANDOFF (explicit) | '{text[:60]}'")
            return LoopType.HANDOFF

        if self._matches_any(text, VERIFY_TRIGGERS):
            logger.info(f"Loop: VERIFY (explicit) | '{text[:60]}'")
            return LoopType.VERIFY

        if self._matches_any(text, ACTION_TRIGGERS):
            logger.info(f"Loop: ACTION (explicit) | '{text[:60]}'")
            return LoopType.ACTION

        if self._matches_any(text, DIRECT_TRIGGERS):
            logger.info(f"Loop: DIRECT (explicit) | '{text[:60]}'")
            return LoopType.DIRECT

        # Priority 2: Inference
        if self._matches_any(text, AUTONOMOUS_INFERENCE):
            logger.info(f"Loop: AUTONOMOUS (inferred) | '{text[:60]}'")
            return LoopType.AUTONOMOUS

        if self._matches_any(text, ACTION_INFERENCE):
            logger.info(f"Loop: ACTION (inferred) | '{text[:60]}'")
            return LoopType.ACTION

        # Priority 3: Default to Direct
        logger.info(f"Loop: DIRECT (default) | '{text[:60]}'")
        return LoopType.DIRECT

    def get_instruction(self, loop_type: LoopType) -> str:
        """Get the loop instruction to inject into the LLM context."""
        return LOOP_INSTRUCTIONS.get(loop_type, "")

    def _matches_any(self, text: str, patterns: list[str]) -> bool:
        """Check if text matches any pattern in the list."""
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)