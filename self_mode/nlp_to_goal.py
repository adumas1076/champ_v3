# ============================================
# CHAMP V3 -- NLP to Goal Card Generator
# Brick 8.5: Converts natural language requests
# into structured Goal Cards for Self Mode.
# ============================================

import logging
import os

import requests

from brain.config import Settings

logger = logging.getLogger(__name__)

NLP_TO_GOAL_PROMPT = """\
You are Champ's Goal Card generator. Convert the user's natural language request into a \
structured CHAMP Goal Card.

Rules:
- Fill ALL 9 fields with sensible defaults based on the request
- Set approval to "None. Auto-execute." for safe, local-only tasks
- Set approval to "Human approval required." if the task involves payments, emails, deploys, \
or external writes
- Set risk_level to "low" for local scripts, "medium" for API calls, "high" for deploys
- Set priority to "P1" unless the user says it's not urgent
- Be specific in success_checks -- include testable criteria
- Stack should match what's needed (Python 3, specific libraries, etc.)
- Platform is Windows -- use "python" not "python3"
- Keep constraints practical: local-only, no paid APIs, reasonable time limits
- Context/assets should include any URLs, data, or inputs mentioned by the user

User request: {task}

{context_section}

Return ONLY the Goal Card in this exact format (no extra text before or after):

GOAL CARD v1.0
(goal_id: GC-AUTO-{short_id} | project_id: champ_v3 | priority: P1 | risk_level: low)

1) OBJECTIVE
- [fill in]

2) PROBLEM
- [fill in]

3) SOLUTION
- [fill in]

4) STACK
- [fill in]

5) CONSTRAINTS
- [fill in]

6) APPROVAL
- [fill in]

7) DELIVERABLES
- [fill in]

8) CONTEXT / ASSETS
- [fill in]

9) SUCCESS CHECKS
- [fill in]"""


def generate_goal_card(
    task_text: str,
    settings: Settings,
    context: str = "",
) -> str:
    """
    Convert natural language task into a Goal Card string.

    Args:
        task_text: Natural language request (e.g. "build me a weather script")
        settings: Brain settings for LLM access
        context: Optional memory context to include

    Returns:
        Complete Goal Card text ready for GoalCardParser.parse()
    """
    import uuid
    short_id = uuid.uuid4().hex[:6].upper()

    context_section = ""
    if context:
        context_section = f"User context from memory:\n{context}"

    prompt = NLP_TO_GOAL_PROMPT.format(
        task=task_text,
        short_id=short_id,
        context_section=context_section,
    )

    # Try LiteLLM first, fallback to direct Anthropic
    content = _llm_call(prompt, settings)

    # Validate it looks like a Goal Card
    if "GOAL CARD" not in content or "1) OBJECTIVE" not in content:
        logger.warning(
            "[NLP_TO_GOAL] LLM response doesn't look like a Goal Card, "
            "wrapping in template"
        )
        # Fallback: build a minimal Goal Card from the task text
        content = _fallback_goal_card(task_text, short_id)

    return content


def _llm_call(prompt: str, settings: Settings) -> str:
    """Make an LLM call -- LiteLLM first, direct Anthropic fallback."""
    # Try LiteLLM
    try:
        response = requests.post(
            f"{settings.litellm_base_url}/chat/completions",
            json={
                "model": settings.default_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"[NLP_TO_GOAL] LiteLLM failed ({e}), trying Anthropic...")

    # Fallback: direct Anthropic API
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        raise RuntimeError(
            "LiteLLM unavailable and no ANTHROPIC_API_KEY set"
        )

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        json={
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        },
        headers={
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    return "".join(
        b["text"] for b in data.get("content", []) if b.get("type") == "text"
    )


def _fallback_goal_card(task_text: str, short_id: str) -> str:
    """Build a minimal Goal Card when the LLM response is unusable."""
    return (
        f"GOAL CARD v1.0\n"
        f"(goal_id: GC-AUTO-{short_id} | project_id: champ_v3 | "
        f"priority: P1 | risk_level: low)\n\n"
        f"1) OBJECTIVE\n- {task_text}\n\n"
        f"2) PROBLEM\n- User needs this task completed.\n\n"
        f"3) SOLUTION\n- Python script to accomplish the objective.\n\n"
        f"4) STACK\n- Python 3\n\n"
        f"5) CONSTRAINTS\n- Must run locally. No paid APIs. Under 30 minutes.\n\n"
        f"6) APPROVAL\n- None. Auto-execute.\n\n"
        f"7) DELIVERABLES\n- Script file + output\n\n"
        f"8) CONTEXT / ASSETS\n- None specified\n\n"
        f"9) SUCCESS CHECKS\n- Script runs without errors\n- Output is produced\n"
    )
