# ============================================
# CHAMP V3 — Cortex Router
# Per-turn smart model selection.
#
# Inspired by:
#   Hermes-Agent: smart_model_routing.py (complexity signals)
#   Nemoclaw: single endpoint routing (everything via LiteLLM)
#   Claude Code: tiered fallback (quota → downgrade)
#
# The Brain calls select_model() before every LLM request.
# Returns a model_name that maps to litellm_config.yaml.
# ============================================

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================
# Model Registry — matches litellm_config.yaml
# ============================================

MODELS = {
    "claude-sonnet":        {"cost_tier": 3, "role": "reasoning",  "strengths": ["coding", "analysis", "sales", "strategy"]},
    "claude-haiku":         {"cost_tier": 1, "role": "qa",         "strengths": ["eval", "structured", "fast"]},
    "gpt-4o":               {"cost_tier": 2, "role": "action",     "strengths": ["tools", "function_calling", "json", "creative"]},
    "gemini-flash":         {"cost_tier": 0, "role": "vision",     "strengths": ["images", "screenshots", "multimodal"]},
    "gemini-flash-volume":  {"cost_tier": 0, "role": "volume",     "strengths": ["drafts", "summaries", "bulk"]},
    "grok-mini":            {"cost_tier": 0, "role": "voice",      "strengths": ["conversation", "casual", "scripts"]},
    "llama-groq":           {"cost_tier": 0, "role": "hooks",      "strengths": ["variants", "ab_test", "brainstorm"]},
}

DEFAULT_MODEL = "claude-sonnet"

# ============================================
# Complexity Detection (Hermes pattern)
# ============================================

# Keywords that signal complex reasoning — route to expensive models
COMPLEX_KEYWORDS = re.compile(
    r"\b(debug|implement|refactor|architect|design|analyze|compare|evaluate|"
    r"security|migration|deploy|optimize|strategy|plan|review|audit|"
    r"write code|build|fix bug|root cause|traceback|error|exception)\b",
    re.IGNORECASE,
)

# Keywords that signal simple tasks — route to cheap models
SIMPLE_KEYWORDS = re.compile(
    r"\b(summarize|reformat|translate|list|define|what is|explain simply|"
    r"rephrase|shorten|expand|rewrite|TL;DR|tldr)\b",
    re.IGNORECASE,
)


@dataclass
class RouteDecision:
    """Result of a routing decision."""
    model: str
    reason: str
    cost_tier: int  # 0=free/cheap, 1=low, 2=mid, 3=high


def select_model(
    task_type: Optional[str] = None,
    funnel_stage: Optional[str] = None,
    message: Optional[str] = None,
    has_images: bool = False,
    operator_name: str = "champ",
    current_model: Optional[str] = None,
) -> RouteDecision:
    """
    Select the best model for this request.

    Priority order:
    1. Explicit task_type override (caller knows what they want)
    2. Image detection → vision model
    3. Funnel stage routing (content engine)
    4. Message complexity analysis (Hermes pattern)
    5. Default to current_model or claude-sonnet

    Args:
        task_type: Explicit routing hint (voice_script, eval, hook_gen, research, tool_call, content_tofu, content_mofu, content_bofu)
        funnel_stage: Marketing funnel position (tof, mof, bof)
        message: The user message text (for complexity analysis)
        has_images: Whether the request contains images
        operator_name: Which operator is making the request
        current_model: The model already set on the request (respect if explicitly chosen)

    Returns:
        RouteDecision with model name, reason, and cost tier
    """

    # ---- Rule 0: If caller explicitly set a model that exists, respect it ----
    if current_model and current_model in MODELS:
        return RouteDecision(
            model=current_model,
            reason=f"explicit model: {current_model}",
            cost_tier=MODELS[current_model]["cost_tier"],
        )

    # ---- Rule 1: Explicit task_type overrides everything ----
    if task_type:
        decision = _route_by_task_type(task_type)
        if decision:
            return decision

    # ---- Rule 2: Images → vision model ----
    if has_images:
        return RouteDecision(
            model="gemini-flash",
            reason="image detected → vision cortex",
            cost_tier=0,
        )

    # ---- Rule 3: Funnel stage routing (content engine) ----
    if funnel_stage:
        decision = _route_by_funnel(funnel_stage)
        if decision:
            return decision

    # ---- Rule 4: Message complexity analysis (Hermes pattern) ----
    if message:
        decision = _route_by_complexity(message)
        if decision:
            return decision

    # ---- Rule 5: Default ----
    return RouteDecision(
        model=DEFAULT_MODEL,
        reason="default → reasoning cortex",
        cost_tier=3,
    )


def _route_by_task_type(task_type: str) -> Optional[RouteDecision]:
    """Route based on explicit task type hint."""
    routes = {
        # Voice
        "voice_script":     ("grok-mini",           "voice script → voice cortex"),
        "conversation":     ("grok-mini",           "conversation → voice cortex"),
        # Content generation
        "content_tofu":     ("gemini-flash-volume", "TOFU content → volume cortex (cheap)"),
        "content_mofu":     ("claude-haiku",        "MOFU content → QA cortex (mid)"),
        "content_bofu":     ("claude-sonnet",       "BOFU content → reasoning cortex (quality)"),
        # Evaluation
        "eval":             ("claude-haiku",        "eval scoring → QA cortex"),
        "qa":               ("claude-haiku",        "QA gate → QA cortex"),
        # Generation at scale
        "hook_gen":         ("llama-groq",          "hook A/B gen → hook cortex (fast+cheap)"),
        "brainstorm":       ("llama-groq",          "brainstorm → hook cortex (variant generation)"),
        # Research & reasoning
        "research":         ("claude-sonnet",       "research → reasoning cortex"),
        "coding":           ("claude-sonnet",       "coding → reasoning cortex"),
        "architecture":     ("claude-sonnet",       "architecture → reasoning cortex"),
        # Tool execution
        "tool_call":        ("gpt-4o",              "tool execution → action cortex"),
        "function_calling": ("gpt-4o",              "function calling → action cortex"),
        "json_output":      ("gpt-4o",              "structured JSON → action cortex"),
        # Vision
        "vision":           ("gemini-flash",        "vision task → vision cortex"),
        "screenshot":       ("gemini-flash",        "screenshot analysis → vision cortex"),
        # Bulk/cheap
        "summary":          ("gemini-flash-volume", "summary → volume cortex"),
        "reformat":         ("gemini-flash-volume", "reformat → volume cortex"),
    }

    if task_type in routes:
        model, reason = routes[task_type]
        return RouteDecision(
            model=model,
            reason=reason,
            cost_tier=MODELS[model]["cost_tier"],
        )
    return None


def _route_by_funnel(funnel_stage: str) -> Optional[RouteDecision]:
    """Route content generation by marketing funnel stage."""
    stage = funnel_stage.lower().strip()

    if stage in ("tof", "tofu", "top"):
        return RouteDecision(
            model="gemini-flash-volume",
            reason="TOFU funnel → volume cortex (60% of content, keep cheap)",
            cost_tier=0,
        )
    elif stage in ("mof", "mofu", "middle"):
        return RouteDecision(
            model="claude-haiku",
            reason="MOFU funnel → QA cortex (better persuasion, mid cost)",
            cost_tier=1,
        )
    elif stage in ("bof", "bofu", "bottom"):
        return RouteDecision(
            model="claude-sonnet",
            reason="BOFU funnel → reasoning cortex (best brand voice, worth the cost)",
            cost_tier=3,
        )
    return None


def _route_by_complexity(message: str) -> Optional[RouteDecision]:
    """
    Analyze message text for complexity signals.
    Hermes pattern: cheap model for simple, expensive for complex.
    """
    msg_len = len(message)
    word_count = len(message.split())
    has_code = "```" in message or "def " in message or "class " in message
    has_complex = bool(COMPLEX_KEYWORDS.search(message))
    has_simple = bool(SIMPLE_KEYWORDS.search(message))
    has_newlines = message.count("\n") > 3

    # Short + simple + no code = cheap model
    if msg_len < 200 and word_count < 30 and not has_code and not has_complex and not has_newlines:
        if has_simple:
            return RouteDecision(
                model="gemini-flash-volume",
                reason="simple short message → volume cortex",
                cost_tier=0,
            )
        # Short but not explicitly simple — use default voice/conversation model
        return RouteDecision(
            model="grok-mini",
            reason="short casual message → voice cortex",
            cost_tier=0,
        )

    # Complex signals = reasoning model
    if has_complex or has_code or (word_count > 200):
        return RouteDecision(
            model="claude-sonnet",
            reason=f"complex message (code={has_code}, keywords={has_complex}, words={word_count}) → reasoning cortex",
            cost_tier=3,
        )

    # Medium complexity — mid-tier
    if word_count > 50 or has_newlines:
        return RouteDecision(
            model="claude-haiku",
            reason="medium complexity → QA cortex (cost-effective)",
            cost_tier=1,
        )

    return None


# ============================================
# Cost Estimation (for logging / budget checks)
# ============================================

# Approximate costs per 1M tokens (input)
COST_PER_M_INPUT = {
    "claude-sonnet":        3.00,
    "claude-haiku":         1.00,
    "gpt-4o":               2.50,
    "gemini-flash":         0.10,
    "gemini-flash-volume":  0.075,
    "grok-mini":            0.30,
    "llama-groq":           0.05,
}

COST_PER_M_OUTPUT = {
    "claude-sonnet":        15.00,
    "claude-haiku":         5.00,
    "gpt-4o":               10.00,
    "gemini-flash":         0.40,
    "gemini-flash-volume":  0.30,
    "grok-mini":            0.50,
    "llama-groq":           0.08,
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a request."""
    in_rate = COST_PER_M_INPUT.get(model, 3.00)
    out_rate = COST_PER_M_OUTPUT.get(model, 15.00)
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000
