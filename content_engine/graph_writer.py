"""
Graph Writer — Bridge between Content Engine and MarketingGraph.

Single entry point for every module in content_engine/ that writes to the graph.
Lazy-loaded, singleton-instance MarketingGraph — one graph per process.

Called by:
  - publishers/*.py       → record_publish_result()
  - scoring.py            → record_performance_score()
  - eval.py               → record_eval_score()
  - orchestrator.py       → record_content_piece(), record_hook()
  - capture/waitlist.py   → record_waitlist_lead()
  - capture/assessment.py → record_assessment_lead()
  - autoresearch.py       → record_pattern(), promote_pattern()
  - monitor.py            → record_dm_lead()

All functions are SAFE — if graph isn't available (import fails, not set up yet),
they log and move on. Never blocks publishing.

V1 launch: graph is optional. Content must post even if graph is down.
V2+: graph drives ideation + reverse engineering.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_graph = None
_graph_disabled = False


def _get_graph():
    """Lazy-load the MarketingGraph singleton."""
    global _graph, _graph_disabled
    if _graph_disabled:
        return None
    if _graph:
        return _graph

    try:
        from content_matrix.marketing_graph import MarketingGraph
        _graph = MarketingGraph()
        logger.info("[GRAPH_WRITER] MarketingGraph connected")
        return _graph
    except ImportError as e:
        logger.info(f"[GRAPH_WRITER] MarketingGraph not available ({e}) — graph writes disabled")
        _graph_disabled = True
        return None
    except Exception as e:
        logger.warning(f"[GRAPH_WRITER] Failed to init MarketingGraph: {e}")
        _graph_disabled = True
        return None


def _safe(fn):
    """Decorator — swallows exceptions. Graph writes never break content pipeline."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"[GRAPH_WRITER] {fn.__name__} failed: {e}")
            return None
    return wrapper


# ============================================
# Influencer + Platform (setup — called once)
# ============================================

@_safe
def record_influencer(influencer_id: str, name: str, niche: str = "", brand_voice: dict = None):
    """Register an influencer in the graph. Called on orchestrator startup."""
    g = _get_graph()
    if not g:
        return False
    return g.write_influencer(influencer_id, name, niche, brand_voice or {})


@_safe
def record_platform(platform: str):
    """Register a platform. Auto-called by write_content_piece too."""
    g = _get_graph()
    if not g:
        return False
    return g.write_platform(platform)


# ============================================
# Content Pipeline (Strategist → Creator → QA → Publisher)
# ============================================

@_safe
def record_content_piece(
    piece_id: str,
    topic: str,
    influencer_id: str,
    platform: str,
    funnel_stage: str = "cold",
    kpi_stage: str = "know",
    content_tier: str = "text",
    cta_keyword: str = "",
):
    """STRATEGIST output — write a planned content piece."""
    g = _get_graph()
    if not g:
        return False
    return g.write_content_piece(
        piece_id=piece_id,
        topic=topic,
        influencer_id=influencer_id,
        platform=platform,
        funnel_stage=funnel_stage,
        kpi_stage=kpi_stage,
        content_tier=content_tier,
        cta_keyword=cta_keyword,
    )


@_safe
def record_hook(piece_id: str, hook_text: str, hook_pattern: str = ""):
    """CREATOR output — write hook and link to content piece."""
    g = _get_graph()
    if not g:
        return None
    hook_id = g.write_hook(hook_text, hook_pattern)
    if hook_id and piece_id:
        g.link_hook_to_content(piece_id, hook_id)
    return hook_id


@_safe
def record_script(piece_id: str, script_text: str):
    """CREATOR output — attach script to content piece."""
    g = _get_graph()
    if not g:
        return False
    return g.write_script(piece_id, script_text)


@_safe
def record_eval_score(
    piece_id: str,
    score: float,
    verdict: str,
    passed: bool,
    notes: str = "",
):
    """QA OPERATOR output — pre-publish score."""
    g = _get_graph()
    if not g:
        return False
    return g.write_eval_score(piece_id, score, verdict, passed, notes)


@_safe
def record_publish_result(
    piece_id: str,
    platform: str,
    success: bool,
    post_id: str = "",
    post_url: str = "",
    error: str = "",
):
    """PUBLISHER output — API post result. Called after every publisher.post()."""
    g = _get_graph()
    if not g:
        return False
    return g.write_publish_result(piece_id, platform, success, post_id, post_url, error)


@_safe
def record_performance_score(
    piece_id: str,
    window: str,
    overall: float,
    verdict: str,
    signals: dict = None,
):
    """ANALYST output — 48hr/7day/30day post-publish score from scoring.py."""
    g = _get_graph()
    if not g:
        return False
    return g.write_performance_score(piece_id, window, overall, verdict, signals or {})


# ============================================
# Capture (V1 METRIC EDGE — content → lead)
# ============================================

@_safe
def record_waitlist_lead(
    lead_id: str,
    email: str,
    source_content_id: str = "",
    source_influencer_id: str = "",
    metadata: dict = None,
):
    """Basic waitlist signup (landing page form)."""
    g = _get_graph()
    if not g:
        return False
    return g.write_waitlist_lead(
        lead_id=lead_id,
        email=email,
        source_type="waitlist",
        tier=None,
        source_content_id=source_content_id,
        source_influencer_id=source_influencer_id,
        metadata=metadata or {},
    )


@_safe
def record_assessment_lead(
    lead_id: str,
    email: str,
    tier: str,
    assessment_id: str,
    percentage: float,
    source_content_id: str = "",
    source_influencer_id: str = "",
    metadata: dict = None,
):
    """Assessment-captured lead with tier (cold/warm/hot/buyer)."""
    g = _get_graph()
    if not g:
        return False
    enriched = {
        "assessment_id": assessment_id,
        "percentage": percentage,
        **(metadata or {}),
    }
    return g.write_waitlist_lead(
        lead_id=lead_id,
        email=email,
        source_type="assessment",
        tier=tier,
        source_content_id=source_content_id,
        source_influencer_id=source_influencer_id,
        metadata=enriched,
    )


@_safe
def record_dm_lead(
    lead_id: str,
    platform_user_id: str,
    keyword: str,
    source_content_id: str = "",
    source_influencer_id: str = "",
    metadata: dict = None,
):
    """DM-keyword-triggered lead (monitor.py)."""
    g = _get_graph()
    if not g:
        return False
    enriched = {"keyword": keyword, "platform_user_id": platform_user_id, **(metadata or {})}
    return g.write_waitlist_lead(
        lead_id=lead_id,
        email=platform_user_id,  # no email from DM yet — platform ID as placeholder
        source_type="dm_keyword",
        tier=None,
        source_content_id=source_content_id,
        source_influencer_id=source_influencer_id,
        metadata=enriched,
    )


# ============================================
# Intelligence (Autoresearch + Trends)
# ============================================

@_safe
def record_pattern(pattern_text: str, confidence: str = "INFERRED", evidence_count: int = 1):
    """Autoresearch output — learned pattern. Promotes with evidence over time."""
    g = _get_graph()
    if not g:
        return None
    return g.write_pattern(pattern_text, confidence, evidence_count)


@_safe
def record_trend(trend_text: str, source: str = "trend_scout", metadata: dict = None):
    """Trend Scout output — discovered trend."""
    g = _get_graph()
    if not g:
        return None
    return g.write_trend(trend_text, source, metadata or {})


@_safe
def link_pattern_to_performance(pattern_id: str, perf_id: str):
    """Pattern proved by specific performance score."""
    g = _get_graph()
    if not g:
        return False
    return g.link_pattern_to_performance(pattern_id, perf_id)


@_safe
def link_content_outperformed(winner_piece_id: str, loser_piece_id: str, margin: float = 0.5):
    """Record that one piece outperformed another (for A/B insights)."""
    g = _get_graph()
    if not g:
        return False
    return g.link_outperformed(winner_piece_id, loser_piece_id, margin)


# ============================================
# Query Helpers (for Ideation Engine + dashboards)
# ============================================

@_safe
def run_killer_query(**kwargs):
    """
    The V1 killer query:
    "Which face + platform + kpi_stage + hook captured the most hot/buyer leads?"

    Wraps MarketingGraph.killer_query() with safe error handling.
    """
    g = _get_graph()
    if not g:
        return []
    return g.killer_query(**kwargs)


@_safe
def get_strategist_view():
    """Return graph summary for Strategist to inform next cycle."""
    g = _get_graph()
    if not g:
        return {}
    return g.strategist_view()


@_safe
def get_analyst_view():
    """Return graph summary for Analyst reports."""
    g = _get_graph()
    if not g:
        return {}
    return g.analyst_view()


@_safe
def find_decoration(days_threshold: int = 7):
    """Find content that captured 0 leads over N days — kill-list candidates."""
    g = _get_graph()
    if not g:
        return []
    return g.find_decoration(days_threshold)


@_safe
def persist_graph():
    """Save graph to disk. Call on orchestrator shutdown or periodically."""
    g = _get_graph()
    if not g:
        return False
    try:
        g.persist()
        logger.info("[GRAPH_WRITER] MarketingGraph persisted")
        return True
    except Exception as e:
        logger.warning(f"[GRAPH_WRITER] Persist failed: {e}")
        return False