"""
Platform Compliance Layer — Rate Limits, Disclosure, Ban Prevention

Every publisher calls compliance.can_post() BEFORE posting.
Every successful post calls compliance.record_action() AFTER.

This is the S and R in SAR:
  Secure  — no account bans, automation disclosed where required
  Reliable — deterministic rate limiting, never exceeds platform rules

Rate limits from 0033_ai_influencer_system.md:
  Twitter:   3 posts/day per face (safe max 15-20)
  Instagram: 3 posts/day per face (safe max 5-8)
  TikTok:    3 posts/day per face (safe max 3-5)
  LinkedIn:  2 posts/day per face (safe max 2-3)

DM limits are separate and more conservative.
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================
# Platform Rate Limits (from 0033)
# ============================================

PLATFORM_LIMITS = {
    "twitter": {
        "posts_per_day": 3,
        "dms_per_day": 50,
        "min_interval_sec": 120,       # 2 min between posts
        "requires_disclosure": True,    # X requires automated account label
        "disclosure_text": None,        # Handled via API automated flag
    },
    "instagram": {
        "posts_per_day": 3,
        "dms_per_day": 30,
        "min_interval_sec": 600,        # 10 min between posts
        "requires_disclosure": True,    # Meta requires disclosure
        "disclosure_text": None,
    },
    "tiktok": {
        "posts_per_day": 3,
        "dms_per_day": 20,
        "min_interval_sec": 1200,       # 20 min between posts
        "requires_disclosure": False,
        "disclosure_text": None,
    },
    "linkedin": {
        "posts_per_day": 2,             # Conservative — 3 is edge of safe
        "dms_per_day": 25,
        "min_interval_sec": 1200,       # 20 min between posts
        "requires_disclosure": True,
        "disclosure_text": None,
    },
    "youtube": {
        "posts_per_day": 2,             # Phase 3 — pillar only
        "dms_per_day": 0,
        "min_interval_sec": 3600,       # 1hr between uploads
        "requires_disclosure": False,
        "disclosure_text": None,
    },
    "facebook": {
        "posts_per_day": 3,             # Phase 3
        "dms_per_day": 30,
        "min_interval_sec": 600,
        "requires_disclosure": True,
        "disclosure_text": None,
    },
}


@dataclass
class ActionRecord:
    """A single recorded action for rate tracking."""
    platform: str
    influencer_id: str
    action_type: str          # "post" | "dm" | "comment_reply"
    timestamp: str
    post_id: Optional[str] = None


@dataclass
class RateLimitStatus:
    """Current rate limit state for an influencer on a platform."""
    platform: str
    influencer_id: str
    posts_today: int = 0
    posts_limit: int = 0
    dms_today: int = 0
    dms_limit: int = 0
    can_post: bool = True
    can_dm: bool = True
    next_post_at: Optional[str] = None
    next_dm_at: Optional[str] = None


class ComplianceChecker:
    """Enforces platform rate limits and compliance rules.

    Usage:
        compliance = ComplianceChecker()
        if compliance.can_post("twitter", "influencer_1"):
            result = await publisher.post(...)
            compliance.record_action("twitter", "influencer_1", "post")
    """

    def __init__(self):
        self._actions: list[ActionRecord] = []

    def _get_today_actions(
        self,
        platform: str,
        influencer_id: str,
        action_type: str,
    ) -> list[ActionRecord]:
        """Get actions from today for rate counting."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat()
        return [
            a for a in self._actions
            if a.platform == platform
            and a.influencer_id == influencer_id
            and a.action_type == action_type
            and a.timestamp >= today_start
        ]

    def _get_last_action_time(
        self,
        platform: str,
        influencer_id: str,
        action_type: str,
    ) -> Optional[datetime]:
        """Get the timestamp of the most recent action."""
        actions = [
            a for a in self._actions
            if a.platform == platform
            and a.influencer_id == influencer_id
            and a.action_type == action_type
        ]
        if not actions:
            return None
        latest = max(actions, key=lambda a: a.timestamp)
        return datetime.fromisoformat(latest.timestamp)

    def can_post(self, platform: str, influencer_id: str) -> bool:
        """Check if posting is allowed right now.

        Checks:
          1. Daily post limit not exceeded
          2. Minimum interval between posts respected
        """
        limits = PLATFORM_LIMITS.get(platform)
        if not limits:
            logger.warning(f"[COMPLIANCE] No limits defined for {platform} — blocking post")
            return False

        # Check daily limit
        today_posts = self._get_today_actions(platform, influencer_id, "post")
        if len(today_posts) >= limits["posts_per_day"]:
            logger.info(
                f"[COMPLIANCE] {influencer_id} hit daily post limit on {platform}: "
                f"{len(today_posts)}/{limits['posts_per_day']}"
            )
            return False

        # Check minimum interval
        last_post = self._get_last_action_time(platform, influencer_id, "post")
        if last_post:
            elapsed = (datetime.utcnow() - last_post).total_seconds()
            if elapsed < limits["min_interval_sec"]:
                logger.info(
                    f"[COMPLIANCE] {influencer_id} too soon on {platform}: "
                    f"{elapsed:.0f}s elapsed, need {limits['min_interval_sec']}s"
                )
                return False

        return True

    def can_dm(self, platform: str, influencer_id: str) -> bool:
        """Check if sending a DM is allowed right now."""
        limits = PLATFORM_LIMITS.get(platform)
        if not limits:
            return False

        today_dms = self._get_today_actions(platform, influencer_id, "dm")
        if len(today_dms) >= limits["dms_per_day"]:
            logger.info(
                f"[COMPLIANCE] {influencer_id} hit daily DM limit on {platform}: "
                f"{len(today_dms)}/{limits['dms_per_day']}"
            )
            return False
        return True

    def record_action(
        self,
        platform: str,
        influencer_id: str,
        action_type: str,
        post_id: Optional[str] = None,
    ):
        """Record an action for rate tracking."""
        record = ActionRecord(
            platform=platform,
            influencer_id=influencer_id,
            action_type=action_type,
            timestamp=datetime.utcnow().isoformat(),
            post_id=post_id,
        )
        self._actions.append(record)
        logger.info(f"[COMPLIANCE] Recorded {action_type} for {influencer_id} on {platform}")

        # Prune old records (keep last 7 days)
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        self._actions = [a for a in self._actions if a.timestamp >= cutoff]

    def get_status(self, platform: str, influencer_id: str) -> RateLimitStatus:
        """Get full rate limit status for an influencer on a platform."""
        limits = PLATFORM_LIMITS.get(platform, {})
        today_posts = self._get_today_actions(platform, influencer_id, "post")
        today_dms = self._get_today_actions(platform, influencer_id, "dm")

        posts_limit = limits.get("posts_per_day", 0)
        dms_limit = limits.get("dms_per_day", 0)

        # Calculate next safe post time
        next_post_at = None
        last_post = self._get_last_action_time(platform, influencer_id, "post")
        if last_post:
            min_interval = limits.get("min_interval_sec", 0)
            next_time = last_post + timedelta(seconds=min_interval)
            if next_time > datetime.utcnow():
                next_post_at = next_time.isoformat()

        return RateLimitStatus(
            platform=platform,
            influencer_id=influencer_id,
            posts_today=len(today_posts),
            posts_limit=posts_limit,
            dms_today=len(today_dms),
            dms_limit=dms_limit,
            can_post=len(today_posts) < posts_limit and next_post_at is None,
            can_dm=len(today_dms) < dms_limit,
            next_post_at=next_post_at,
        )

    def get_next_safe_time(self, platform: str, influencer_id: str) -> datetime:
        """Get the earliest time we can post next."""
        limits = PLATFORM_LIMITS.get(platform, {})
        min_interval = limits.get("min_interval_sec", 300)

        last_post = self._get_last_action_time(platform, influencer_id, "post")
        if not last_post:
            return datetime.utcnow()

        next_time = last_post + timedelta(seconds=min_interval)
        return max(next_time, datetime.utcnow())

    def add_disclosure(self, content: str, platform: str) -> str:
        """Add required automation disclosure to content.

        Some platforms require labeling automated posts.
        This modifies the content text if needed.
        """
        limits = PLATFORM_LIMITS.get(platform, {})
        if not limits.get("requires_disclosure"):
            return content

        disclosure = limits.get("disclosure_text")
        if disclosure and disclosure not in content:
            return f"{content}\n\n{disclosure}"

        # Most platforms handle disclosure via API flags, not text
        return content

    def get_daily_summary(self) -> dict:
        """Get a summary of all actions today across all influencers."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat()
        today_actions = [a for a in self._actions if a.timestamp >= today_start]

        summary = {}
        for a in today_actions:
            key = f"{a.influencer_id}_{a.platform}"
            if key not in summary:
                summary[key] = {"influencer": a.influencer_id, "platform": a.platform, "posts": 0, "dms": 0}
            if a.action_type == "post":
                summary[key]["posts"] += 1
            elif a.action_type == "dm":
                summary[key]["dms"] += 1

        return summary
