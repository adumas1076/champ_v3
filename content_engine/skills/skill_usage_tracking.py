"""
Skill Usage Tracking — Count + recency ranking with 7-day half-life decay.

Harvested from: Claude Code source (skillUsageTracking.ts)
Pattern: Exponential decay — recent usage matters more than old usage.
Skills used today score higher than skills used last week.

Our addition: Connects to operator_skills Supabase table for persistence
and DDO effectiveness scoring.
"""

import logging
import math
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("cocreatiq.skills.tracking")


# In-memory cache of usage data (persisted to Supabase periodically)
_usage_cache: dict[str, "SkillUsage"] = {}

# Debounce: don't write to DB more than once per 60 seconds per skill
USAGE_DEBOUNCE_SEC = 60
_last_write: dict[str, float] = {}

# Half-life: usage from 7 days ago is worth half as much as today
HALF_LIFE_DAYS = 7

# Minimum recency factor — don't completely drop old but heavily used skills
MIN_RECENCY_FACTOR = 0.1


@dataclass
class SkillUsage:
    """Usage data for a single skill."""
    skill_name: str
    usage_count: int = 0
    last_used_at: float = 0.0    # Unix timestamp
    total_success: int = 0
    total_failure: int = 0
    effectiveness: float = 0.5   # 0.0-1.0


def record_skill_usage(
    skill_name: str,
    success: bool = True,
) -> None:
    """Record that a skill was used.

    Called after a skill completes execution. Updates count, timestamp,
    and success/failure tracking.

    Args:
        skill_name: Name of the skill that was executed
        success: Whether the skill completed successfully
    """
    now = time.time()

    # Debounce — don't spam the DB
    last = _last_write.get(skill_name, 0)
    if now - last < USAGE_DEBOUNCE_SEC:
        # Still update in-memory cache
        usage = _get_or_create(skill_name)
        usage.usage_count += 1
        usage.last_used_at = now
        if success:
            usage.total_success += 1
        else:
            usage.total_failure += 1
        return

    _last_write[skill_name] = now

    # Update in-memory
    usage = _get_or_create(skill_name)
    usage.usage_count += 1
    usage.last_used_at = now
    if success:
        usage.total_success += 1
    else:
        usage.total_failure += 1

    # Recalculate effectiveness
    total = usage.total_success + usage.total_failure
    if total > 0:
        usage.effectiveness = usage.total_success / total

    # TODO: Persist to Supabase operator_skills table
    # UPDATE operator_skills SET times_used = {count}, effectiveness = {eff}
    # WHERE name = {skill_name}
    logger.info(
        f"[SKILL TRACKING] {skill_name}: used={usage.usage_count}, "
        f"effectiveness={usage.effectiveness:.2f}"
    )


def get_skill_usage_score(skill_name: str) -> float:
    """Calculate a usage score based on frequency and recency.

    Higher scores = more frequently and recently used skills.
    Uses exponential decay with 7-day half-life.

    Harvested from Claude Code: skillUsageTracking.ts getSkillUsageScore()

    Returns:
        Float score. 0 = never used. Higher = more important.
    """
    usage = _usage_cache.get(skill_name)
    if not usage or usage.usage_count == 0:
        return 0.0

    # Days since last use
    days_since = (time.time() - usage.last_used_at) / (60 * 60 * 24)

    # Exponential decay: halve score every HALF_LIFE_DAYS
    recency_factor = math.pow(0.5, days_since / HALF_LIFE_DAYS)

    # Floor at MIN_RECENCY_FACTOR — don't completely drop heavily used skills
    recency_factor = max(recency_factor, MIN_RECENCY_FACTOR)

    return usage.usage_count * recency_factor


def get_skill_ranking() -> list[tuple[str, float]]:
    """Get all skills ranked by usage score (highest first).

    Returns:
        List of (skill_name, score) tuples, sorted descending.
    """
    rankings = []
    for skill_name in _usage_cache:
        score = get_skill_usage_score(skill_name)
        rankings.append((skill_name, score))

    rankings.sort(key=lambda x: x[1], reverse=True)
    return rankings


def get_skill_status(skill_name: str) -> str:
    """Determine skill status based on usage data.

    - draft: < 3 uses
    - active: 3-9 uses
    - proven: 10+ uses with effectiveness > 0.8
    - archived: effectiveness < 0.3 after 10+ uses

    Returns:
        Status string.
    """
    usage = _usage_cache.get(skill_name)
    if not usage:
        return "draft"

    if usage.usage_count < 3:
        return "draft"
    elif usage.usage_count < 10:
        return "active"
    elif usage.effectiveness >= 0.8:
        return "proven"
    elif usage.effectiveness < 0.3:
        return "archived"
    else:
        return "active"


def _get_or_create(skill_name: str) -> SkillUsage:
    """Get or create a SkillUsage entry in the cache."""
    if skill_name not in _usage_cache:
        _usage_cache[skill_name] = SkillUsage(skill_name=skill_name)
    return _usage_cache[skill_name]
