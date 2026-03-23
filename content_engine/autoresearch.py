"""
Autoresearch Loop — Self-Improving Content Engine
Pull analytics → Score against eval criteria → Correlate with performance →
Update rules in Letta knowledge block → Generate better content next cycle.

This is the Karpathy autoresearch pattern applied to content:
  generate → evaluate → learn → generate better → repeat

Integrates:
  - content_engine.analytics.youtube  (pull YouTube data)
  - content_engine.analytics.instagram (pull Instagram data)
  - content_engine.eval               (score against Lamar + Gary Vee criteria)
  - mind.letta_memory                 (store self-improving rules in knowledge block)
  - self_mode.engine                  (autonomous iteration via Self Mode)
"""

import json
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict

from content_engine.eval import (
    score_content,
    ContentScoreCard,
    ALL_CRITERIA,
    build_eval_prompt,
)

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

@dataclass
class ContentPerformance:
    """Links a content piece's eval score to its real-world performance."""
    content_id: str
    influencer_id: str
    platform: str
    content_type: str
    funnel_stage: str
    eval_score: float            # Pre-publish eval percentage
    eval_verdict: str            # excellent | publishable | rework | reject
    # Real-world metrics (filled after analytics pull)
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    impressions: int = 0
    engagement_rate: float = 0.0
    retention_level: str = ""    # drop_off | early_plateau | even_scale
    avg_view_percentage: float = 0.0
    # Correlation
    performance_tier: str = ""   # top | average | below_average | poor
    published_at: str = ""
    analyzed_at: str = ""


@dataclass
class AutoresearchCycle:
    """One complete cycle of the autoresearch loop."""
    cycle_id: str
    influencer_id: str
    started_at: str
    completed_at: str = ""
    # Inputs
    posts_analyzed: int = 0
    platforms: list[str] = field(default_factory=list)
    # Findings
    performances: list[ContentPerformance] = field(default_factory=list)
    top_performers: list[str] = field(default_factory=list)       # content_ids
    worst_performers: list[str] = field(default_factory=list)     # content_ids
    # Correlations
    criteria_correlations: dict = field(default_factory=dict)     # criterion_id → correlation with performance
    # Learned rules
    new_rules: list[str] = field(default_factory=list)
    updated_rules: list[str] = field(default_factory=list)
    # Status
    status: str = "running"      # running | completed | failed


# ============================================
# Correlation Engine
# ============================================

def classify_performance(perf: ContentPerformance, avg_views: float, avg_engagement: float) -> str:
    """Classify a post's performance relative to average.

    Uses both views AND engagement to avoid the Lamar Mistake #1 trap
    (attention ≠ authority — high views but low engagement = wrong audience).
    """
    view_ratio = perf.views / max(1, avg_views)
    eng_ratio = perf.engagement_rate / max(0.01, avg_engagement)

    # Weight engagement higher than views (authority > attention)
    combined = view_ratio * 0.4 + eng_ratio * 0.6

    if combined >= 1.5:
        return "top"
    elif combined >= 0.8:
        return "average"
    elif combined >= 0.4:
        return "below_average"
    else:
        return "poor"


def correlate_criteria_with_performance(performances: list[ContentPerformance]) -> dict:
    """Find which eval criteria correlate with real-world performance.

    Returns: {criterion_id: correlation_score}
    where positive = criterion predicts good performance,
    negative = criterion presence doesn't help.

    This is the LEARNING step — the autoresearch loop discovers
    which quality rules actually matter for THIS audience.
    """
    if len(performances) < 5:
        return {}  # Need minimum data to correlate

    correlations = {}
    tier_scores = {"top": 3, "average": 2, "below_average": 1, "poor": 0}

    for criterion in ALL_CRITERIA:
        cid = criterion["id"]
        # For each criterion, compare avg performance of posts that passed vs failed
        passed_scores = []
        failed_scores = []

        for perf in performances:
            tier_score = tier_scores.get(perf.performance_tier, 1)
            # We need the eval results stored alongside — for now use eval_score as proxy
            # In full implementation, store per-criterion pass/fail with performance data
            if perf.eval_score >= 75:
                passed_scores.append(tier_score)
            else:
                failed_scores.append(tier_score)

        if passed_scores and failed_scores:
            avg_passed = sum(passed_scores) / len(passed_scores)
            avg_failed = sum(failed_scores) / len(failed_scores)
            correlations[cid] = round(avg_passed - avg_failed, 2)

    return correlations


# ============================================
# Rule Generation
# ============================================

def generate_learned_rules(
    correlations: dict,
    top_performers: list[ContentPerformance],
    worst_performers: list[ContentPerformance],
) -> list[str]:
    """Generate self-improving rules from correlation data.

    These rules get stored in Letta's knowledge block and
    influence future content generation.
    """
    rules = []

    # Rules from correlations
    strong_positive = {k: v for k, v in correlations.items() if v >= 1.0}
    strong_negative = {k: v for k, v in correlations.items() if v <= -0.5}

    criteria_map = {c["id"]: c["question"] for c in ALL_CRITERIA}

    for cid, score in sorted(strong_positive.items(), key=lambda x: x[1], reverse=True):
        question = criteria_map.get(cid, cid)
        rules.append(f"CONFIRMED: '{question}' strongly correlates with top performance (score: {score}). Prioritize this.")

    for cid, score in sorted(strong_negative.items(), key=lambda x: x[1]):
        question = criteria_map.get(cid, cid)
        rules.append(f"WEAK: '{question}' does not correlate with performance (score: {score}). Deprioritize or investigate.")

    # Rules from top performers pattern analysis
    if top_performers:
        top_types = [p.content_type for p in top_performers]
        top_platforms = [p.platform for p in top_performers]
        top_funnels = [p.funnel_stage for p in top_performers]

        # Find dominant patterns
        for label, values in [("content_type", top_types), ("platform", top_platforms), ("funnel_stage", top_funnels)]:
            from collections import Counter
            counts = Counter(values)
            dominant = counts.most_common(1)[0] if counts else None
            if dominant and dominant[1] >= len(top_performers) * 0.6:
                rules.append(f"PATTERN: Top performers are predominantly {label}='{dominant[0]}' ({dominant[1]}/{len(top_performers)}). Double down.")

    return rules


def format_rules_for_letta(rules: list[str], existing_rules: str = "") -> str:
    """Format learned rules for Letta knowledge block storage.

    Keeps the block under 5000 chars (Letta limit).
    Newer rules take priority over older ones.
    """
    header = "## Content Engine — Learned Rules (Autoresearch Loop)\n"
    header += f"Last updated: {datetime.utcnow().isoformat()}\n\n"

    # Parse existing rules
    existing = []
    if existing_rules:
        for line in existing_rules.split("\n"):
            line = line.strip()
            if line.startswith(("CONFIRMED:", "WEAK:", "PATTERN:", "RULE:")):
                existing.append(line)

    # Merge: new rules override existing if same criterion
    merged = {}
    for rule in existing + rules:  # New rules come last = override
        # Use first ~50 chars as dedup key
        key = rule[:50]
        merged[key] = rule

    all_rules = list(merged.values())

    body = "\n".join(f"- {r}" for r in all_rules)
    full_text = header + body

    # Trim to fit Letta's 5000 char limit
    if len(full_text) > 4800:
        # Keep most recent rules (at the end of the list)
        while len(full_text) > 4800 and all_rules:
            all_rules.pop(0)  # Remove oldest
            body = "\n".join(f"- {r}" for r in all_rules)
            full_text = header + body

    return full_text


# ============================================
# Main Autoresearch Loop
# ============================================

async def _pull_platform_posts(platform: str, data: dict, influencer_id: str) -> list[ContentPerformance]:
    """Convert platform-specific data into normalized ContentPerformance objects."""
    performances = []
    posts = data.get("posts", data.get("videos", []))

    for post in posts:
        # Normalize field names across platforms
        content_id = (
            post.get("video_id")
            or post.get("media_id")
            or post.get("tweet_id")
            or post.get("post_urn")
            or post.get("id", "")
        )
        views = (
            post.get("views", 0)
            or post.get("impressions", 0)
            or post.get("plays", 0)
            or 0
        )
        likes = post.get("likes", 0) or post.get("like_count", 0) or 0
        comments = post.get("comments", 0) or post.get("comment_count", 0) or 0
        shares = (
            post.get("shares", 0)
            or post.get("share_count", 0)
            or post.get("retweets", 0)
            or 0
        )
        impressions = post.get("impressions", 0) or views
        published_at = (
            post.get("published_at")
            or post.get("timestamp")
            or post.get("created_at")
            or post.get("create_time", "")
        )

        # Determine content type from platform-specific fields
        media_type = post.get("media_type", "")
        has_media = post.get("has_media", False)
        duration = post.get("duration_sec", 0) or post.get("duration", 0) or 0
        if platform == "youtube":
            stats = post.get("stats") or {}
            analytics = post.get("analytics") or {}
            views = stats.get("views", views)
            likes = stats.get("likes", likes)
            comments = stats.get("comments", comments)
            impressions = analytics.get("views", views)
            content_type = "pillar" if stats.get("duration", "PT0S") > "PT600S" else "micro"
        elif platform == "instagram":
            insights = post.get("insights") or {}
            views = insights.get("plays", views)
            shares = insights.get("shares", shares)
            impressions = insights.get("impressions", impressions)
            content_type = "micro" if media_type == "VIDEO" else "static"
        elif platform == "tiktok":
            content_type = "micro_micro" if duration and duration <= 60 else "micro"
        elif platform == "twitter":
            content_type = "micro_micro" if has_media else "static"
        elif platform == "linkedin":
            content_type = "long_form" if media_type in ("ARTICLE", "NONE") else "micro"
        elif platform == "facebook":
            is_video = post.get("is_video", False) or post.get("type") == "video"
            content_type = "micro" if is_video else "static"
        else:
            content_type = "micro"

        perf = ContentPerformance(
            content_id=str(content_id),
            influencer_id=influencer_id,
            platform=platform,
            content_type=content_type,
            funnel_stage="tof",  # Default — should be tagged in metadata
            eval_score=0,
            eval_verdict="pending",
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            impressions=impressions,
            published_at=str(published_at),
        )
        if perf.impressions > 0:
            perf.engagement_rate = (perf.likes + perf.comments + perf.shares) / perf.impressions * 100

        # YouTube-specific: retention data
        if platform == "youtube":
            retention = post.get("retention") or {}
            perf.retention_level = retention.get("retention_level", "")
            analytics = post.get("analytics") or {}
            perf.avg_view_percentage = analytics.get("averageViewPercentage", 0)

        performances.append(perf)

    return performances


async def run_autoresearch_cycle(
    influencer_id: str,
    letta_memory=None,
    youtube_channel_id: Optional[str] = None,
    instagram_business_id: Optional[str] = None,
    tiktok_enabled: bool = True,
    twitter_user_id: Optional[str] = None,
    linkedin_enabled: bool = True,
    facebook_enabled: bool = True,
) -> AutoresearchCycle:
    """Run one complete autoresearch cycle across ALL social platforms.

    Platforms pulled:
      1. YouTube    (channel analytics + retention curves)
      2. Instagram  (post insights + engagement)
      3. TikTok     (video metrics + engagement)
      4. Twitter/X  (tweet metrics + impressions)
      5. LinkedIn   (post stats + engagement)
      6. Facebook   (page posts, videos, reels + insights)

    Pipeline:
      Pull analytics -> Normalize -> Classify tiers ->
      Correlate eval criteria with performance ->
      Generate learned rules -> Store in Letta knowledge block

    This should be run on a schedule (weekly) or triggered manually.
    """
    cycle = AutoresearchCycle(
        cycle_id=f"ar_{influencer_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        influencer_id=influencer_id,
        started_at=datetime.utcnow().isoformat(),
    )

    try:
        performances = []

        # ---- Platform 1: YouTube ----
        if youtube_channel_id:
            try:
                from content_engine.analytics.youtube import pull_channel_analytics
                yt_data = await pull_channel_analytics(youtube_channel_id)
                cycle.platforms.append("youtube")
                perfs = await _pull_platform_posts("youtube", yt_data, influencer_id)
                performances.extend(perfs)
                logger.info(f"[AUTORESEARCH] YouTube: {len(perfs)} videos pulled")
            except Exception as e:
                logger.warning(f"[AUTORESEARCH] YouTube pull failed: {e}")

        # ---- Platform 2: Instagram ----
        if instagram_business_id:
            try:
                from content_engine.analytics.instagram import pull_content_performance as ig_pull
                ig_data = await ig_pull()
                cycle.platforms.append("instagram")
                perfs = await _pull_platform_posts("instagram", ig_data, influencer_id)
                performances.extend(perfs)
                logger.info(f"[AUTORESEARCH] Instagram: {len(perfs)} posts pulled")
            except Exception as e:
                logger.warning(f"[AUTORESEARCH] Instagram pull failed: {e}")

        # ---- Platform 3: TikTok ----
        if tiktok_enabled:
            try:
                from content_engine.analytics.tiktok import pull_content_performance as tt_pull
                tt_data = await tt_pull()
                if tt_data.get("posts_analyzed", 0) > 0:
                    cycle.platforms.append("tiktok")
                    perfs = await _pull_platform_posts("tiktok", tt_data, influencer_id)
                    performances.extend(perfs)
                    logger.info(f"[AUTORESEARCH] TikTok: {len(perfs)} videos pulled")
            except Exception as e:
                logger.warning(f"[AUTORESEARCH] TikTok pull failed: {e}")

        # ---- Platform 4: Twitter/X ----
        if twitter_user_id:
            try:
                from content_engine.analytics.twitter import pull_content_performance as tw_pull
                tw_data = await tw_pull(user_id=twitter_user_id)
                if tw_data.get("posts_analyzed", 0) > 0:
                    cycle.platforms.append("twitter")
                    perfs = await _pull_platform_posts("twitter", tw_data, influencer_id)
                    performances.extend(perfs)
                    logger.info(f"[AUTORESEARCH] Twitter: {len(perfs)} tweets pulled")
            except Exception as e:
                logger.warning(f"[AUTORESEARCH] Twitter pull failed: {e}")

        # ---- Platform 5: LinkedIn ----
        if linkedin_enabled:
            try:
                from content_engine.analytics.linkedin import pull_content_performance as li_pull
                li_data = await li_pull()
                if li_data.get("posts_analyzed", 0) > 0:
                    cycle.platforms.append("linkedin")
                    perfs = await _pull_platform_posts("linkedin", li_data, influencer_id)
                    performances.extend(perfs)
                    logger.info(f"[AUTORESEARCH] LinkedIn: {len(perfs)} posts pulled")
            except Exception as e:
                logger.warning(f"[AUTORESEARCH] LinkedIn pull failed: {e}")

        # ---- Platform 6: Facebook ----
        if facebook_enabled:
            try:
                from content_engine.analytics.facebook import pull_content_performance as fb_pull
                fb_data = await fb_pull()
                if fb_data.get("posts_analyzed", 0) > 0:
                    cycle.platforms.append("facebook")
                    perfs = await _pull_platform_posts("facebook", fb_data, influencer_id)
                    performances.extend(perfs)
                    logger.info(f"[AUTORESEARCH] Facebook: {len(perfs)} posts pulled")
            except Exception as e:
                logger.warning(f"[AUTORESEARCH] Facebook pull failed: {e}")

        cycle.posts_analyzed = len(performances)

        if not performances:
            cycle.status = "completed"
            cycle.completed_at = datetime.utcnow().isoformat()
            logger.info(f"[AUTORESEARCH] No content to analyze for {influencer_id}")
            return cycle

        # ---- Classify performance tiers (per-platform normalization) ----
        # Group by platform so each platform is scored against its own averages
        by_platform = {}
        for perf in performances:
            by_platform.setdefault(perf.platform, []).append(perf)

        for platform, platform_perfs in by_platform.items():
            avg_views = sum(p.views for p in platform_perfs) / len(platform_perfs)
            avg_engagement = sum(p.engagement_rate for p in platform_perfs) / max(1, len(platform_perfs))
            for perf in platform_perfs:
                perf.performance_tier = classify_performance(perf, avg_views, avg_engagement)
                perf.analyzed_at = datetime.utcnow().isoformat()

        # ---- Identify top and worst performers (cross-platform) ----
        top = [p for p in performances if p.performance_tier == "top"]
        worst = [p for p in performances if p.performance_tier in ("below_average", "poor")]
        cycle.top_performers = [p.content_id for p in top]
        cycle.worst_performers = [p.content_id for p in worst]
        cycle.performances = performances

        # ---- Correlate criteria with performance ----
        cycle.criteria_correlations = correlate_criteria_with_performance(performances)

        # ---- Generate learned rules ----
        new_rules = generate_learned_rules(cycle.criteria_correlations, top, worst)

        # Add cross-platform insights
        if len(by_platform) >= 2:
            platform_engagement = {}
            for platform, platform_perfs in by_platform.items():
                avg_eng = sum(p.engagement_rate for p in platform_perfs) / max(1, len(platform_perfs))
                platform_engagement[platform] = round(avg_eng, 2)
            best_platform = max(platform_engagement, key=platform_engagement.get)
            worst_platform = min(platform_engagement, key=platform_engagement.get)
            new_rules.append(
                f"PLATFORM: Best engagement on {best_platform} ({platform_engagement[best_platform]}%), "
                f"worst on {worst_platform} ({platform_engagement[worst_platform]}%). "
                f"Investigate content-platform fit."
            )

        cycle.new_rules = new_rules

        # ---- Store in Letta knowledge block ----
        if letta_memory and letta_memory.available:
            existing_knowledge = await letta_memory.get_block("knowledge") or ""
            updated_knowledge = format_rules_for_letta(new_rules, existing_knowledge)
            await letta_memory.update_block("knowledge", updated_knowledge)
            logger.info(f"[AUTORESEARCH] Updated Letta knowledge block with {len(new_rules)} new rules")

        cycle.status = "completed"
        cycle.completed_at = datetime.utcnow().isoformat()

        logger.info(
            f"[AUTORESEARCH] Cycle complete: {len(cycle.platforms)} platforms, "
            f"{cycle.posts_analyzed} posts analyzed, "
            f"{len(top)} top performers, {len(worst)} underperformers, "
            f"{len(new_rules)} new rules generated"
        )

    except Exception as e:
        cycle.status = "failed"
        cycle.completed_at = datetime.utcnow().isoformat()
        logger.error(f"[AUTORESEARCH] Cycle failed: {e}")

    return cycle


async def run_self_mode_iteration(
    influencer_id: str,
    content_type: str = "micro",
    platform: str = "instagram",
    funnel_stage: str = "tof",
    iterations: int = 3,
    letta_memory=None,
) -> list[dict]:
    """Use Self Mode for fast content iteration.

    Generate N versions → Score each → Pick the best → Learn → Repeat.
    This is the "generate 3 → score → improve → repeat" loop from the checklist.

    Returns list of scored iterations.
    """
    results = []

    # Get learned rules from Letta (if available)
    learned_rules = ""
    if letta_memory and letta_memory.available:
        learned_rules = await letta_memory.get_block("knowledge") or ""

    eval_prompt = build_eval_prompt(content_type)

    for i in range(iterations):
        iteration = {
            "iteration": i + 1,
            "content_type": content_type,
            "platform": platform,
            "funnel_stage": funnel_stage,
            "eval_prompt": eval_prompt,
            "learned_rules": learned_rules,
            "status": "ready_for_self_mode",
        }
        results.append(iteration)
        logger.info(f"[AUTORESEARCH] Prepared iteration {i + 1}/{iterations} for Self Mode")

    # Self Mode integration:
    # Each iteration should be dispatched to Self Mode as a GoalCard:
    #   goal: "Generate a {content_type} for {platform} in {funnel_stage} stage"
    #   constraints: eval criteria + learned rules
    #   success_criteria: eval score >= 75%
    #
    # The Self Mode engine (self_mode/engine.py) handles:
    #   1. Generate content (llm_generate subtask)
    #   2. Self-evaluate against criteria (llm_generate subtask)
    #   3. If score < 75%, revise and re-score (fix step)
    #   4. Package final version (package step)
    #   5. Learn what worked (learn step → feeds back to Letta)

    return results
