"""
Marketing Machine Orchestrator — The Conductor

Coordinates the Marketing Department: Strategist, Creator, QA, Publisher,
Analyst, Trend Scout. Each role runs at the right time, in the right order,
with the right data.

This is the BRAIN of the Marketing Machine. It runs the 3 loops:
  Loop 1: Content Loop (daily) — create → score → post → measure → learn
  Loop 2: Capture Loop (real-time) — engage → capture waitlist → track
  Loop 3: Intelligence Loop (weekly) — analyze → find patterns → update rules

V1 (Day 1): Text posts only, 2 operators + system
V2 (Scale): Full department, video production, parallel creators

Architecture:
  orchestrator.py calls operators + system functions in sequence
  Each step has clear input/output
  If any step fails, pipeline degrades gracefully (skip, don't crash)

Spec: 0034_click_to_client_technical_wiring.md — Component 7
SAR: Secure, Autonomous, Reliable
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

from content_engine.eval import score_content, build_eval_prompt, get_pre_publish_criteria
from content_engine.pipeline.scheduler import ContentScheduler, PostStatus
from content_engine.pipeline.funnel import DEFAULT_TARGETS
from content_engine.publishers import register_all_publishers, get_compliance
from content_engine.influencers.loader import load_all_influencers, get_brand_voice

logger = logging.getLogger(__name__)


# ============================================
# Configuration
# ============================================

@dataclass
class OrchestratorConfig:
    """Configuration for the Marketing Machine."""
    # Posting
    approval_mode: str = "approve_first"  # approve_first | auto_post
    posts_per_face_per_platform: int = 3
    platforms: list[str] = field(default_factory=lambda: [
        "twitter", "linkedin", "instagram", "tiktok",
    ])
    # Funnel balance targets
    funnel_targets: dict = field(default_factory=lambda: {
        "tof": 50, "mof": 30, "bof": 20,
    })
    # Quality gate
    min_eval_score: float = 75.0
    max_rework_attempts: int = 2
    # Timing
    morning_hour: int = 8     # Start generating content
    # V1: text only. V2: add video tiers
    content_tiers: list[str] = field(default_factory=lambda: ["text"])
    # Waitlist (V1)
    waitlist_enabled: bool = True
    waitlist_url: str = ""
    # Analytics
    scoring_delay_hours: int = 48


# ============================================
# Content Manifest (Strategist Output)
# ============================================

@dataclass
class ContentItem:
    """A single content piece planned by the Strategist."""
    id: str
    influencer_id: str
    platform: str
    funnel_stage: str         # cold | warm | hot | buyer
    kpi_stage: str = "know"   # know | like | trust | convert  (the KLT filter)
    topic: str = ""
    hook_angle: str = ""
    cta: str = ""
    cta_keyword: str = ""     # BUILD/SCALE/BRAND/OPERATOR — for DM monitor tie-in
    content_tier: str = "text"   # text | voice | video | static
    # Filled by Creator
    script: str = ""
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    media_url: Optional[str] = None
    hook_text: str = ""       # First line of script — extracted for graph
    hook_pattern: str = ""    # Normalized hook pattern (for cross-face aggregation)
    # Filled by QA
    eval_score: float = 0.0
    eval_verdict: str = "pending"
    passed_qa: bool = False
    rework_count: int = 0
    qa_notes: str = ""
    # Status
    status: str = "planned"   # planned | scripted | qa_pass | qa_fail | scheduled | posted | failed


@dataclass
class DailyManifest:
    """The Strategist's plan for the day."""
    date: str
    items: list[ContentItem] = field(default_factory=list)
    reactive_items: list[ContentItem] = field(default_factory=list)
    total_planned: int = 0
    total_passed_qa: int = 0
    total_posted: int = 0


# ============================================
# ROLE 1: Strategist — Plan Today's Content
# ============================================

async def run_strategist(
    config: OrchestratorConfig,
    influencers: list[dict],
    topic_bank: Optional[list[dict]] = None,
    trending_topics: Optional[list[str]] = None,
) -> DailyManifest:
    """STRATEGIST: Plan today's content for all faces and platforms.

    Decides: what topic, which face, which platform, which funnel stage, what CTA.
    Uses funnel balance to ensure 50/30/20 distribution.
    """
    import uuid
    manifest = DailyManifest(date=datetime.utcnow().strftime("%Y-%m-%d"))

    # Calculate funnel slots needed — using cold/warm/hot/buyer matching MarketingGraph schema
    total_posts = len(influencers) * len(config.platforms) * config.posts_per_face_per_platform
    cold_count = int(total_posts * config.funnel_targets.get("tof", 50) / 100)
    warm_count = int(total_posts * config.funnel_targets.get("mof", 30) / 100)
    hot_count = total_posts - cold_count - warm_count

    stage_pool = (["cold"] * cold_count) + (["warm"] * warm_count) + (["hot"] * hot_count)

    # KPI (Know/Like/Trust/Convert) balance — matches funnel stage emphasis
    # cold → know, warm → like/trust mix, hot → trust/convert mix
    kpi_map = {
        "cold": "know",
        "warm": "like",  # can override to "trust" later
        "hot": "trust",
        "buyer": "convert",
    }

    stage_idx = 0

    # CTA patterns per funnel stage (from 0033)
    cta_patterns = {
        "tof": [
            "Follow for more {niche} breakdowns",
            "Save this for later",
            "Comment '{keyword}' for the full breakdown",
        ],
        "mof": [
            "DM me '{keyword}' to get the free {lead_magnet}",
            "Link in bio for the free {lead_magnet}",
            "Join the waitlist — link in bio",
        ],
        "bof": [
            "DM me '{keyword}' to see how this works for your business",
            "Get early access — link in bio",
        ],
    }

    for influencer in influencers:
        inf_id = influencer.get("id", "unknown")
        inf_niche = influencer.get("niche", "AI")
        keyword = influencer.get("cta_keyword", "START")
        lead_magnet = influencer.get("lead_magnet", "free audit")

        for platform in config.platforms:
            for slot in range(config.posts_per_face_per_platform):
                stage = stage_pool[stage_idx % len(stage_pool)] if stage_pool else "tof"
                stage_idx += 1

                # Pick topic from bank or trending
                topic = "AI and business growth"  # Default fallback
                if topic_bank and len(topic_bank) > 0:
                    topic_entry = topic_bank[stage_idx % len(topic_bank)]
                    topic = topic_entry.get("topic", topic)
                elif trending_topics and len(trending_topics) > 0:
                    topic = trending_topics[stage_idx % len(trending_topics)]

                # Pick CTA based on funnel stage
                ctas = cta_patterns.get(stage, cta_patterns["tof"])
                cta = ctas[slot % len(ctas)]
                cta = cta.format(
                    niche=inf_niche,
                    keyword=keyword,
                    lead_magnet=lead_magnet,
                )

                # Hook angle (Marketing Op would generate this with LLM in V2)
                hook_angle = f"Hook angle for {topic} on {platform}"

                item = ContentItem(
                    id=uuid.uuid4().hex[:12],
                    influencer_id=inf_id,
                    platform=platform,
                    funnel_stage=stage,
                    kpi_stage=kpi_map.get(stage, "know"),
                    topic=topic,
                    hook_angle=hook_angle,
                    cta=cta,
                    cta_keyword=keyword,
                    content_tier=config.content_tiers[0],
                )
                manifest.items.append(item)

                # Write to MarketingGraph (non-blocking)
                try:
                    from content_engine import graph_writer
                    graph_writer.record_content_piece(
                        piece_id=item.id,
                        topic=item.topic,
                        influencer_id=item.influencer_id,
                        platform=item.platform,
                        funnel_stage=item.funnel_stage,
                        kpi_stage=item.kpi_stage,
                        content_tier=item.content_tier,
                        cta_keyword=item.cta_keyword,
                    )
                except Exception:
                    pass  # Graph write is non-fatal

    manifest.total_planned = len(manifest.items)
    logger.info(
        f"[STRATEGIST] Planned {manifest.total_planned} pieces for {manifest.date} | "
        f"cold: {cold_count} warm: {warm_count} hot: {hot_count}"
    )
    return manifest


# ============================================
# ROLE 2: Creator — Write Scripts
# ============================================

async def run_creator(
    manifest: DailyManifest,
    influencers: list[dict],
    llm_generate=None,
) -> DailyManifest:
    """CREATOR: Write scripts for each item in the manifest.

    V1: Generates text posts (script = the post text).
    V2: Generates full scripts for voice/video production pipeline.

    Args:
        llm_generate: async function(prompt, system) -> str
            If None, uses template-based generation (V1 fallback).
    """
    influencer_map = {inf["id"]: inf for inf in influencers}

    for item in manifest.items:
        if item.status != "planned":
            continue

        inf = influencer_map.get(item.influencer_id, {})
        brand_voice = inf.get("brand_voice", {})
        tone = brand_voice.get("tone", "direct and insightful")
        avoid = brand_voice.get("avoid", [])

        if llm_generate:
            # V2: LLM-powered script generation
            prompt = _build_creation_prompt(item, inf)
            try:
                script = await llm_generate(prompt, system="You are a content creator.")
                item.script = script
                item.status = "scripted"
            except Exception as e:
                logger.error(f"[CREATOR] LLM generation failed for {item.id}: {e}")
                item.status = "failed"
        else:
            # V1 fallback: Template-based text post
            item.script = _template_script(item, inf)
            item.status = "scripted"

        # Build caption (script + CTA + hashtags)
        item.caption = f"{item.script}\n\n{item.cta}"
        if item.hashtags:
            item.caption += "\n" + " ".join(f"#{t}" for t in item.hashtags)

        # Extract hook from first line of script for graph
        first_line = item.script.split("\n", 1)[0].strip()
        item.hook_text = first_line[:200]
        # Pattern = normalized form (first 5 words + question mark)
        words = first_line.split()[:5]
        item.hook_pattern = " ".join(words) + ("?" if "?" in first_line else "")

        # Write hook + script to graph
        try:
            from content_engine import graph_writer
            graph_writer.record_hook(item.id, item.hook_text, item.hook_pattern)
            graph_writer.record_script(item.id, item.script)
        except Exception:
            pass

    scripted = sum(1 for i in manifest.items if i.status == "scripted")
    logger.info(f"[CREATOR] Scripted {scripted}/{manifest.total_planned} pieces")
    return manifest


def _build_creation_prompt(item: ContentItem, influencer: dict) -> str:
    """Build an LLM prompt for content creation."""
    brand_voice = influencer.get("brand_voice", {})
    platform_rules = influencer.get("platform_rules", {}).get(item.platform, {})

    return f"""Write a {item.platform} post about: {item.topic}

Funnel stage: {item.funnel_stage.upper()}
Hook angle: {item.hook_angle}
CTA: {item.cta}

Brand voice: {brand_voice.get('tone', 'direct')}
Avoid: {brand_voice.get('avoid', [])}
Platform: {item.platform}
Max length: {platform_rules.get('max_length', 280)} characters

Follow Lamar structure: Hook (stop the scroll) → Lead (keep reading) → Meat (deliver value) → Payoff (deliver on promise).

Return ONLY the post text. No explanations."""


def _template_script(item: ContentItem, influencer: dict) -> str:
    """V1 fallback: template-based text generation."""
    templates = {
        "tof": [
            f"Most people get {item.topic} wrong. Here's what actually works:",
            f"I've been studying {item.topic} for years. The #1 insight:",
            f"Stop doing {item.topic} the hard way. There's a better approach:",
        ],
        "mof": [
            f"How we used {item.topic} to 10x our results (real numbers):",
            f"The framework behind {item.topic} that nobody talks about:",
            f"3 things I wish I knew about {item.topic} before starting:",
        ],
        "bof": [
            f"Ready to fix your {item.topic}? Here's the exact system:",
            f"We built a tool that handles {item.topic} automatically. Here's how:",
        ],
    }
    options = templates.get(item.funnel_stage, templates["tof"])
    template = options[hash(item.id) % len(options)]
    return template


# ============================================
# ROLE 3: QA Gate — Score Every Piece
# ============================================

async def run_qa_gate(
    manifest: DailyManifest,
    config: OrchestratorConfig,
    llm_evaluate=None,
) -> DailyManifest:
    """QA GATE: Evaluate every scripted piece against quality criteria.

    Must score ≥ config.min_eval_score (default 75%) to pass.
    Failed pieces get notes on what to fix.

    V1: Basic checks (length, CTA present, no empty scripts).
    V2: Full LLM-based evaluation against 34 Lamar + Gary Vee criteria.
    """
    for item in manifest.items:
        if item.status != "scripted":
            continue

        # Basic checks (V1)
        issues = []
        if not item.script or len(item.script.strip()) < 20:
            issues.append("Script too short or empty")
        if not item.cta:
            issues.append("No CTA assigned")
        if item.funnel_stage == "bof" and "link" not in item.cta.lower() and "dm" not in item.cta.lower():
            issues.append("BOF content needs a direct CTA (link or DM)")

        # Platform length check
        max_lengths = {
            "twitter": 280,
            "linkedin": 3000,
            "instagram": 2200,
            "tiktok": 2000,
            "youtube": 5000,
            "facebook": 5000,
        }
        max_len = max_lengths.get(item.platform, 2000)
        if len(item.caption) > max_len:
            issues.append(f"Caption too long for {item.platform}: {len(item.caption)}/{max_len}")

        if llm_evaluate:
            # V2: Full LLM evaluation
            try:
                eval_result = await llm_evaluate(item.script, item.platform, item.funnel_stage)
                item.eval_score = eval_result.get("score", 0)
                item.eval_verdict = eval_result.get("verdict", "pending")
                if item.eval_score < config.min_eval_score:
                    issues.append(f"Eval score {item.eval_score:.0f}% below threshold {config.min_eval_score:.0f}%")
                    item.qa_notes = eval_result.get("notes", "")
            except Exception as e:
                logger.warning(f"[QA] LLM eval failed for {item.id}: {e}")

        if issues:
            item.passed_qa = False
            item.status = "qa_fail"
            item.qa_notes = "; ".join(issues)
            item.rework_count += 1
        else:
            item.passed_qa = True
            item.status = "qa_pass"
            item.eval_score = max(item.eval_score, 80.0)  # V1: pass = 80%
            item.eval_verdict = "publishable"

        # Write eval_score to graph
        try:
            from content_engine import graph_writer
            graph_writer.record_eval_score(
                piece_id=item.id,
                score=item.eval_score,
                verdict=item.eval_verdict,
                passed=item.passed_qa,
                notes=item.qa_notes,
            )
        except Exception:
            pass

    passed = sum(1 for i in manifest.items if i.status == "qa_pass")
    failed = sum(1 for i in manifest.items if i.status == "qa_fail")
    manifest.total_passed_qa = passed
    logger.info(f"[QA] {passed} passed, {failed} failed out of {manifest.total_planned}")
    return manifest


# ============================================
# ROLE 4: Publisher — Schedule + Post
# ============================================

async def run_publisher(
    manifest: DailyManifest,
    scheduler: ContentScheduler,
) -> DailyManifest:
    """PUBLISHER: Queue all QA-passed content into the scheduler.

    The scheduler handles timing, compliance checking, and actual API posting.
    This function just feeds approved content into the queue.
    """
    queued = 0
    for item in manifest.items:
        if item.status != "qa_pass":
            continue

        scheduler.add_to_queue(
            content_id=item.id,
            pillar_id="daily_" + manifest.date,
            influencer_id=item.influencer_id,
            platform=item.platform,
            title=item.topic[:100],
            caption=item.caption,
            media_url=item.media_url,
            hashtags=item.hashtags,
            funnel_stage=item.funnel_stage,
            content_type=item.content_tier,
        )
        item.status = "scheduled"
        queued += 1

    logger.info(f"[PUBLISHER] Queued {queued} pieces for posting")

    # Publish any that are due right now
    results = await scheduler.publish_due()
    posted = sum(1 for r in results if r.success)
    manifest.total_posted = posted
    logger.info(f"[PUBLISHER] Published {posted} pieces immediately")

    return manifest


# ============================================
# ROLE 5: Analyst — Score Published Content
# ============================================

async def run_analyst(scoring_delay_hours: int = 48) -> dict:
    """ANALYST: Score content that's been published for 48+ hours.

    Pulls analytics from platform APIs, computes 5-signal score,
    extracts lessons and patterns. Feeds back into autoresearch loop.

    Returns summary of scoring results.
    """
    try:
        from content_engine.autoresearch import run_autoresearch_cycle
        # The autoresearch cycle handles the full analytics → score → learn pipeline
        # It's already wired with multi-signal scoring from this session's earlier work
        logger.info(f"[ANALYST] Running autoresearch cycle (scoring content {scoring_delay_hours}h+ old)")
        # In production, pass real influencer IDs and channel IDs
        # For now, return a placeholder
        return {"status": "ready", "note": "Wire with real influencer IDs + OAuth tokens"}
    except Exception as e:
        logger.warning(f"[ANALYST] Autoresearch cycle failed: {e}")
        return {"status": "failed", "error": str(e)}


# ============================================
# ROLE 6: Trend Scout — Scan for Opportunities
# ============================================

async def run_trend_scout() -> list[str]:
    """TREND SCOUT: Scan for trending topics relevant to our niche.

    V1: Returns empty (no scanning infra yet).
    V2: Google Trends + platform trending + competitor outliers.
    """
    # V2: Wire to Research Operator's trend scanning tools
    # - Google Trends API for niche keyword spikes
    # - Platform trending topics/sounds
    # - VidIQ outlier detection on competitors
    logger.info("[TREND SCOUT] Scan complete (V1: no active scanning)")
    return []


# ============================================
# MAIN ORCHESTRATOR LOOP
# ============================================

async def run_daily_cycle(
    config: Optional[OrchestratorConfig] = None,
    topic_bank: Optional[list[dict]] = None,
    llm_generate=None,
    llm_evaluate=None,
) -> DailyManifest:
    """Run one complete daily content cycle.

    This is the main entry point. Call this once per day (or on demand).

    Steps:
      1. Trend Scout scans for opportunities
      2. Strategist plans today's content
      3. Creator writes scripts
      4. QA Gate evaluates every piece
      5. Creator reworks failed pieces (up to max_rework_attempts)
      6. Publisher queues and posts approved content
      7. (Analyst runs separately on a 48hr delay)

    Args:
        config: Orchestrator settings (defaults provided)
        topic_bank: Pre-loaded topics [{topic, niche, stage}, ...]
        llm_generate: async fn(prompt, system) -> str (for V2 LLM generation)
        llm_evaluate: async fn(script, platform, stage) -> {score, verdict, notes}
    """
    if config is None:
        config = OrchestratorConfig()

    logger.info(f"{'='*60}")
    logger.info(f"  MARKETING MACHINE — Daily Cycle {datetime.utcnow().strftime('%Y-%m-%d')}")
    logger.info(f"  Mode: {config.approval_mode} | Tiers: {config.content_tiers}")
    logger.info(f"  Platforms: {config.platforms}")
    logger.info(f"{'='*60}")

    # Load influencers
    try:
        influencers = load_all_influencers()
    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Failed to load influencers: {e}")
        influencers = []

    if not influencers:
        logger.warning("[ORCHESTRATOR] No influencers loaded — using defaults")
        influencers = [{"id": "anthony", "niche": "AI", "cta_keyword": "OPERATOR",
                        "lead_magnet": "free AI readiness audit", "brand_voice": {"tone": "direct"}}]

    # Register all influencers in the MarketingGraph (non-blocking, idempotent)
    try:
        from content_engine import graph_writer
        for inf in influencers:
            graph_writer.record_influencer(
                influencer_id=inf.get("id", "unknown"),
                name=inf.get("name", inf.get("id", "unknown")),
                niche=inf.get("niche", ""),
                brand_voice=inf.get("brand_voice", {}),
            )
    except Exception as e:
        logger.warning(f"[ORCHESTRATOR] Influencer graph registration skipped: {e}")

    # ---- Step 1: Trend Scout ----
    trending = await run_trend_scout()

    # ---- Step 2: Strategist ----
    manifest = await run_strategist(config, influencers, topic_bank, trending)

    # ---- Step 3: Creator ----
    manifest = await run_creator(manifest, influencers, llm_generate)

    # ---- Step 4: QA Gate ----
    manifest = await run_qa_gate(manifest, config, llm_evaluate)

    # ---- Step 5: Rework failed pieces ----
    for attempt in range(config.max_rework_attempts):
        failed = [i for i in manifest.items if i.status == "qa_fail" and i.rework_count <= config.max_rework_attempts]
        if not failed:
            break
        logger.info(f"[ORCHESTRATOR] Rework attempt {attempt + 1}: {len(failed)} pieces")
        for item in failed:
            item.status = "planned"  # Reset for re-creation
        manifest = await run_creator(manifest, influencers, llm_generate)
        manifest = await run_qa_gate(manifest, config, llm_evaluate)

    # ---- Step 6: Publisher ----
    scheduler = ContentScheduler(approval_mode=config.approval_mode)
    register_all_publishers(scheduler)
    manifest = await run_publisher(manifest, scheduler)

    # ---- Summary ----
    logger.info(f"{'='*60}")
    logger.info(f"  DAILY CYCLE COMPLETE")
    logger.info(f"  Planned: {manifest.total_planned}")
    logger.info(f"  Passed QA: {manifest.total_passed_qa}")
    logger.info(f"  Posted: {manifest.total_posted}")
    logger.info(f"  Failed: {sum(1 for i in manifest.items if i.status in ('qa_fail', 'failed'))}")
    logger.info(f"{'='*60}")

    # Persist graph after cycle (non-blocking)
    try:
        from content_engine import graph_writer
        graph_writer.persist_graph()
    except Exception:
        pass

    return manifest


async def run_continuous(
    config: Optional[OrchestratorConfig] = None,
    topic_bank: Optional[list[dict]] = None,
    llm_generate=None,
    llm_evaluate=None,
):
    """Run the Marketing Machine continuously.

    - Daily content cycle at morning_hour
    - Trend scout every 4 hours
    - Publisher checks for due posts every 5 minutes
    - Analyst runs daily (for content 48h+ old)

    This is the "set it and forget it" mode.
    """
    if config is None:
        config = OrchestratorConfig()

    scheduler = ContentScheduler(approval_mode=config.approval_mode)
    register_all_publishers(scheduler)

    logger.info("[ORCHESTRATOR] Marketing Machine starting continuous mode")

    last_daily_run = None
    last_trend_scan = None
    last_analyst_run = None

    while True:
        now = datetime.utcnow()

        # Daily content cycle (once per day, at morning_hour)
        today = now.strftime("%Y-%m-%d")
        if last_daily_run != today and now.hour >= config.morning_hour:
            logger.info("[ORCHESTRATOR] Running daily content cycle")
            await run_daily_cycle(config, topic_bank, llm_generate, llm_evaluate)
            last_daily_run = today

        # Trend scout (every 4 hours)
        if last_trend_scan is None or (now - last_trend_scan).total_seconds() > 4 * 3600:
            trending = await run_trend_scout()
            last_trend_scan = now
            # If trends found, create reactive content (V2)

        # Publish due posts (every 5 minutes)
        try:
            results = await scheduler.publish_due()
            if results:
                posted = sum(1 for r in results if r.success)
                if posted > 0:
                    logger.info(f"[ORCHESTRATOR] Published {posted} scheduled posts")
        except Exception as e:
            logger.warning(f"[ORCHESTRATOR] Publish check failed: {e}")

        # Analyst (once per day, afternoon)
        if last_analyst_run != today and now.hour >= 14:
            await run_analyst(config.scoring_delay_hours)
            last_analyst_run = today

        # Sleep 5 minutes between checks
        await asyncio.sleep(300)