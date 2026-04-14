"""
LLM Generation Adapter — Connects Content Engine to the Brain for script generation.

The orchestrator's Creator role needs an LLM to generate scripts.
This adapter provides a clean interface that routes to the brain's
LLM client (via API call or direct import).

Two modes:
  1. API mode: Call brain's HTTP API at BRAIN_URL/v1/generate (default)
  2. Direct mode: Import brain.llm_client directly (same process)

The adapter handles:
  - Prompt construction with brand voice + platform rules + learned rules
  - Cortex routing hint (Marketing = Claude for reasoning)
  - Response parsing
  - Fallback to template if LLM unavailable

This module is NOT part of brain/ — it's the content engine's
interface TO the brain. No brain/ files modified.

Required env vars:
  BRAIN_URL — Brain API URL (default: http://127.0.0.1:8100)
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

BRAIN_URL = os.getenv("BRAIN_URL", "http://127.0.0.1:8100")


async def generate_script(
    topic: str,
    platform: str,
    funnel_stage: str,
    influencer_id: str,
    brand_voice: Optional[dict] = None,
    learned_rules: Optional[str] = None,
    hook_angle: Optional[str] = None,
    cta: Optional[str] = None,
    max_length: int = 280,
) -> Optional[str]:
    """Generate a content script using the brain's LLM.

    This is what the orchestrator's Creator role calls.
    Returns the generated script text, or None if generation fails.
    """
    prompt = _build_prompt(
        topic=topic,
        platform=platform,
        funnel_stage=funnel_stage,
        brand_voice=brand_voice,
        learned_rules=learned_rules,
        hook_angle=hook_angle,
        cta=cta,
        max_length=max_length,
    )

    system = _build_system_prompt(influencer_id, brand_voice)

    # Try API mode first (brain running as separate service)
    result = await _call_brain_api(prompt, system)
    if result:
        return result

    # Fallback: try direct LiteLLM call
    result = await _call_litellm_direct(prompt, system)
    if result:
        return result

    logger.warning(f"[LLM_ADAPTER] Generation failed for {topic} on {platform} — no LLM available")
    return None


async def evaluate_script(
    script: str,
    platform: str,
    funnel_stage: str,
) -> Optional[dict]:
    """Evaluate a script using LLM (for QA Gate V2).

    Returns: {"score": float, "verdict": str, "notes": str}
    """
    prompt = f"""Evaluate this {platform} post for quality.

POST:
{script}

FUNNEL STAGE: {funnel_stage.upper()}

Score on these criteria (YES/NO each):
1. Hook compelling? (stops the scroll in first line)
2. Delivers value? (teaches, inspires, or entertains)
3. CTA present and appropriate for funnel stage?
4. Brand voice consistent? (not generic, has personality)
5. Platform-appropriate length and format?
6. Not clickbait? (payoff matches promise)

Return JSON: {{"score": 0-100, "verdict": "excellent|publishable|rework|reject", "notes": "what to fix"}}
Return ONLY the JSON. No explanation."""

    result = await _call_brain_api(prompt, "You are a content quality evaluator. Be strict.")
    if not result:
        return None

    try:
        import json
        # Try to parse JSON from response
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        return json.loads(result)
    except Exception:
        return None


# ============================================
# Prompt Construction
# ============================================

def _build_prompt(
    topic: str,
    platform: str,
    funnel_stage: str,
    brand_voice: Optional[dict] = None,
    learned_rules: Optional[str] = None,
    hook_angle: Optional[str] = None,
    cta: Optional[str] = None,
    max_length: int = 280,
) -> str:
    """Build the content generation prompt."""
    platform_specs = {
        "twitter": {"max_length": 280, "format": "Single tweet or short thread. Punchy. Hot takes work."},
        "linkedin": {"max_length": 3000, "format": "Professional insight. Use line breaks. Hook in first 2 lines (before 'see more')."},
        "instagram": {"max_length": 2200, "format": "Caption for reel or carousel. Conversational. Emoji OK. Hashtags at end."},
        "tiktok": {"max_length": 2000, "format": "Caption for short video. Casual. Trend-aware. Hook immediately."},
        "youtube": {"max_length": 5000, "format": "Video description. SEO keywords. Timestamps. Links."},
        "facebook": {"max_length": 5000, "format": "Feed post. Conversational. Can be longer. Question hooks work."},
    }
    spec = platform_specs.get(platform, {"max_length": max_length, "format": "Social media post."})

    parts = [
        f"Write a {platform} post about: {topic}",
        "",
        f"PLATFORM: {platform}",
        f"FORMAT: {spec['format']}",
        f"MAX LENGTH: {spec['max_length']} characters",
        f"FUNNEL STAGE: {funnel_stage.upper()}",
    ]

    if funnel_stage == "tof":
        parts.append("GOAL: Attract and educate. NO selling. Pure value.")
    elif funnel_stage == "mof":
        parts.append("GOAL: Build trust. Show proof. Soft CTA.")
    elif funnel_stage == "bof":
        parts.append("GOAL: Convert. Direct CTA. Remove objections.")

    if hook_angle:
        parts.append(f"HOOK ANGLE: {hook_angle}")

    if cta:
        parts.append(f"CTA (include at end): {cta}")

    parts.append("")
    parts.append("STRUCTURE: Follow Lamar retention structure:")
    parts.append("  Hook (first line — stop the scroll)")
    parts.append("  Lead (keep them reading)")
    parts.append("  Meat (deliver the value)")
    parts.append("  Payoff (deliver on the hook's promise)")

    if brand_voice:
        tone = brand_voice.get("tone", "")
        avoid = brand_voice.get("avoid", [])
        if tone:
            parts.append(f"\nTONE: {tone}")
        if avoid:
            parts.append(f"AVOID: {', '.join(avoid)}")

    if learned_rules:
        parts.append(f"\nLEARNED RULES (from past performance):\n{learned_rules[:500]}")

    parts.append("\nReturn ONLY the post text. No explanations, no labels, no quotes around it.")

    return "\n".join(parts)


def _build_system_prompt(influencer_id: str, brand_voice: Optional[dict] = None) -> str:
    """Build the system prompt for the LLM."""
    base = "You are a professional content creator for social media."

    voice_desc = ""
    if brand_voice:
        tone = brand_voice.get("tone", "")
        personality = brand_voice.get("personality", "")
        if tone:
            voice_desc += f" Your tone is {tone}."
        if personality:
            voice_desc += f" Your personality is {personality}."

    return f"{base}{voice_desc} Write content that stops the scroll, delivers real value, and drives action. Never be generic. Never be boring. Every post must earn the next second of attention."


# ============================================
# LLM Calling — Two Modes
# ============================================

async def _call_brain_api(prompt: str, system: str) -> Optional[str]:
    """Call the brain's HTTP API for LLM generation."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{BRAIN_URL}/v1/generate",
                json={
                    "prompt": prompt,
                    "system": system,
                    "max_tokens": 1000,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("text") or data.get("content") or data.get("response")
            else:
                logger.debug(f"[LLM_ADAPTER] Brain API returned {resp.status_code}")
                return None
    except Exception as e:
        logger.debug(f"[LLM_ADAPTER] Brain API call failed: {e}")
        return None


async def _call_litellm_direct(prompt: str, system: str) -> Optional[str]:
    """Direct LiteLLM call as fallback (if brain not running as service)."""
    try:
        import litellm

        model = os.getenv("LITELLM_MODEL", "anthropic/claude-sonnet-4-20250514")
        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.8,
        )
        return response.choices[0].message.content
    except ImportError:
        logger.debug("[LLM_ADAPTER] litellm not available")
        return None
    except Exception as e:
        logger.debug(f"[LLM_ADAPTER] LiteLLM direct call failed: {e}")
        return None