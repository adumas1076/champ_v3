"""
Multi-Signal Content Scoring Engine — Marketing Machine Intelligence Layer

Weighted 5-signal scoring system that grades every piece of content
against real analytics data, not just binary pass/fail criteria.

Signals:
  Hook Score      (30%) — First 3s retention (YT) or scroll-stop rate (IG/TT)
  Retention Score (25%) — Average view duration / total duration
  Engagement Score(20%) — (Comments + Saves) / Views (depth, not vanity)
  Conversion Score(15%) — CTA click-through rate
  Outlier Score   (10%) — Performance vs channel 90-day average

Three benchmark levels:
  YOUR average     — personal baseline
  NICHE average    — competitive benchmark
  TOP 10%          — aspiration target

Verdicts:
  VIRAL (>8.0) | HIT (6.0-8.0) | SOLID (4.0-6.0) | WEAK (2.0-4.0) | MISS (<2.0)

Integrates with:
  - content_engine.eval        (pre-publish binary criteria — Lamar + Gary Vee)
  - content_engine.autoresearch (post-publish analytics loop)
  - content_engine.analytics.*  (platform data sources)
  - operators/configs/qa.yaml   (QA Operator thresholds)

Spec: development/0031_marketing_matrix_data_intelligence.md — Pipeline 3
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================
# Enums & Constants
# ============================================

class Verdict(str, Enum):
    VIRAL = "viral"       # > 8.0
    HIT = "hit"           # 6.0 - 8.0
    SOLID = "solid"       # 4.0 - 6.0
    WEAK = "weak"         # 2.0 - 4.0
    MISS = "miss"         # < 2.0
    PENDING = "pending"


class SignalName(str, Enum):
    HOOK = "hook"
    RETENTION = "retention"
    ENGAGEMENT = "engagement"
    CONVERSION = "conversion"
    OUTLIER = "outlier"


# Default weights — configurable per client for tuning with real data
DEFAULT_WEIGHTS = {
    SignalName.HOOK: 0.30,
    SignalName.RETENTION: 0.25,
    SignalName.ENGAGEMENT: 0.20,
    SignalName.CONVERSION: 0.15,
    SignalName.OUTLIER: 0.10,
}

# Platform-aware thresholds: {signal: {platform: (good, great)}}
# "Good" = solid performance, "Great" = top 10% territory
PLATFORM_THRESHOLDS = {
    SignalName.HOOK: {
        "youtube": (0.65, 0.80),      # First 3s retention %
        "instagram": (0.50, 0.70),    # Scroll-stop rate (reel plays / impressions)
        "tiktok": (0.55, 0.75),       # Scroll-stop rate
        "linkedin": (0.40, 0.60),     # Impression-to-read ratio
        "twitter": (0.30, 0.50),      # Impression-to-engage ratio
        "facebook": (0.45, 0.65),     # Scroll-stop rate
        "_default": (0.50, 0.70),
    },
    SignalName.RETENTION: {
        "youtube": (0.40, 0.60),      # Avg view duration / total duration
        "instagram": (0.50, 0.70),    # Reel completion rate
        "tiktok": (0.50, 0.70),       # Completion rate
        "linkedin": (0.30, 0.50),     # Article read-through
        "twitter": (0.20, 0.40),      # Thread completion (estimated)
        "facebook": (0.40, 0.60),     # Video watch-through
        "_default": (0.40, 0.60),
    },
    SignalName.ENGAGEMENT: {
        "youtube": (0.02, 0.05),      # (Comments + Saves) / Views
        "instagram": (0.03, 0.06),    # Higher engagement expected on IG
        "tiktok": (0.02, 0.05),
        "linkedin": (0.03, 0.07),     # LinkedIn audiences engage more deeply
        "twitter": (0.01, 0.03),      # Lower per-impression engagement
        "facebook": (0.02, 0.05),
        "_default": (0.02, 0.05),
    },
    SignalName.CONVERSION: {
        "youtube": (0.01, 0.03),      # CTA clicks / views
        "instagram": (0.01, 0.03),    # Profile visits or link clicks / views
        "tiktok": (0.005, 0.02),      # Bio link clicks / views
        "linkedin": (0.02, 0.05),     # Higher intent audience
        "twitter": (0.01, 0.03),      # Link clicks / impressions
        "facebook": (0.01, 0.03),
        "_default": (0.01, 0.03),
    },
    SignalName.OUTLIER: {
        # Outlier thresholds are platform-agnostic (views / channel avg)
        "_default": (5.0, 10.0),      # 5x = outlier, 10x = viral
    },
}


def _get_threshold(signal: SignalName, platform: str) -> tuple[float, float]:
    """Get (good, great) threshold for a signal on a platform."""
    signal_thresholds = PLATFORM_THRESHOLDS.get(signal, {})
    return signal_thresholds.get(platform, signal_thresholds.get("_default", (0.5, 0.8)))


# ============================================
# Signal Calculation
# ============================================

@dataclass
class SignalResult:
    """Result of computing one signal."""
    signal: str
    raw_value: float          # The actual metric value
    normalized: float         # 0.0 - 10.0 scale
    weight: float             # Signal weight (0.0 - 1.0)
    weighted_score: float     # normalized * weight
    grade: str                # "great" | "good" | "below" | "poor" | "no_data"
    threshold_good: float
    threshold_great: float
    platform: str


def _normalize_signal(raw: float, good: float, great: float) -> tuple[float, str]:
    """Normalize a raw metric value to 0-10 scale using thresholds.

    Scoring curve:
      0.0 raw  → 0.0 score
      good     → 5.0 score
      great    → 8.0 score
      2x great → 10.0 score (cap)

    Returns (normalized_score, grade).
    """
    if raw <= 0:
        return 0.0, "no_data"

    if great <= 0:
        return 0.0, "no_data"

    if raw >= great * 2:
        return 10.0, "great"
    elif raw >= great:
        # Scale 8.0 → 10.0 between great and 2x great
        score = 8.0 + (raw - great) / max(great, 0.001) * 2.0
        return min(score, 10.0), "great"
    elif raw >= good:
        # Scale 5.0 → 8.0 between good and great
        score = 5.0 + (raw - good) / max(great - good, 0.001) * 3.0
        return min(score, 8.0), "good"
    elif raw >= good * 0.5:
        # Scale 2.0 → 5.0 between half-good and good
        score = 2.0 + (raw - good * 0.5) / max(good * 0.5, 0.001) * 3.0
        return min(score, 5.0), "below"
    else:
        # Scale 0.0 → 2.0 below half-good
        score = raw / max(good * 0.5, 0.001) * 2.0
        return max(min(score, 2.0), 0.0), "poor"


def compute_hook_score(
    first_3s_retention: Optional[float] = None,
    scroll_stop_rate: Optional[float] = None,
    impressions: int = 0,
    initial_plays: int = 0,
    platform: str = "youtube",
) -> float:
    """Compute hook score from platform-specific signals.

    YouTube: first 3-second retention percentage (from retention curve)
    IG/TikTok: scroll-stop rate = plays / impressions
    LinkedIn/Twitter: engagement / impressions as proxy
    """
    if first_3s_retention is not None:
        return first_3s_retention

    if scroll_stop_rate is not None:
        return scroll_stop_rate

    if impressions > 0 and initial_plays > 0:
        return initial_plays / impressions

    return 0.0


def compute_retention_score(
    avg_view_duration: float = 0.0,
    total_duration: float = 0.0,
    completion_rate: Optional[float] = None,
    avg_view_percentage: float = 0.0,
) -> float:
    """Compute retention score.

    YouTube: avg_view_percentage (directly from API) or avg_view_duration / total_duration
    Short-form (IG/TT): completion_rate (full watches / total views)
    """
    if completion_rate is not None:
        return completion_rate

    if avg_view_percentage > 0:
        return avg_view_percentage / 100.0  # API returns as percentage

    if total_duration > 0 and avg_view_duration > 0:
        return avg_view_duration / total_duration

    return 0.0


def compute_engagement_score(
    comments: int = 0,
    saves: int = 0,
    shares: int = 0,
    views: int = 0,
) -> float:
    """Compute engagement depth score.

    Formula: (Comments + Saves) / Views
    Saves and comments indicate DEPTH — not vanity likes.
    Shares included as a bonus signal but weighted via share_velocity separately.
    """
    if views <= 0:
        return 0.0
    return (comments + saves) / views


def compute_conversion_score(
    cta_clicks: int = 0,
    link_clicks: int = 0,
    profile_visits: int = 0,
    views: int = 0,
) -> float:
    """Compute CTA conversion score.

    CTA clicks / total views. Uses best available conversion signal.
    """
    if views <= 0:
        return 0.0
    clicks = cta_clicks or link_clicks or profile_visits
    return clicks / views


def compute_outlier_score(
    views: int = 0,
    channel_avg_views: float = 0.0,
) -> float:
    """Compute outlier score.

    Video views / channel 90-day average views.
    Outlier: >5x, Viral: >10x
    """
    if channel_avg_views <= 0:
        return 0.0
    return views / channel_avg_views


# ============================================
# Benchmarks
# ============================================

@dataclass
class Benchmark:
    """Benchmark data for comparison — YOUR avg, NICHE avg, TOP 10%."""
    label: str                          # "your_average" | "niche_average" | "top_10_percent"
    hook: float = 0.0
    retention: float = 0.0
    engagement: float = 0.0
    conversion: float = 0.0
    outlier: float = 1.0               # 1.0 = channel average by definition
    sample_size: int = 0
    period_days: int = 90


@dataclass
class BenchmarkComparison:
    """How this content compares to benchmarks."""
    your_avg: Optional[Benchmark] = None
    niche_avg: Optional[Benchmark] = None
    top_10: Optional[Benchmark] = None
    vs_your_avg: dict = field(default_factory=dict)     # {signal: "+15%" or "-8%"}
    vs_niche_avg: dict = field(default_factory=dict)
    vs_top_10: dict = field(default_factory=dict)


def _compare_to_benchmark(signals: dict[str, float], benchmark: Benchmark) -> dict[str, str]:
    """Compare raw signal values against a benchmark. Returns delta strings."""
    if not benchmark or benchmark.sample_size == 0:
        return {}
    deltas = {}
    benchmark_vals = {
        "hook": benchmark.hook,
        "retention": benchmark.retention,
        "engagement": benchmark.engagement,
        "conversion": benchmark.conversion,
        "outlier": benchmark.outlier,
    }
    for signal_name, raw_val in signals.items():
        bench_val = benchmark_vals.get(signal_name, 0)
        if bench_val > 0:
            pct = ((raw_val - bench_val) / bench_val) * 100
            deltas[signal_name] = f"{pct:+.1f}%"
        elif raw_val > 0:
            deltas[signal_name] = "+∞"
        else:
            deltas[signal_name] = "0%"
    return deltas


# ============================================
# Content Scorecard (Multi-Signal)
# ============================================

@dataclass
class ContentScore:
    """Complete multi-signal score for a content piece."""
    content_id: str
    influencer_id: str
    platform: str
    content_type: str               # pillar | long_form | micro | micro_micro | static
    funnel_stage: str               # tof | mof | bof

    # Signal results
    signals: list[SignalResult] = field(default_factory=list)

    # Aggregate
    total_score: float = 0.0        # 0.0 - 10.0 weighted composite
    verdict: str = "pending"        # viral | hit | solid | weak | miss
    weights_used: dict = field(default_factory=dict)

    # Benchmarks
    benchmarks: Optional[BenchmarkComparison] = None

    # Lesson extraction
    lesson: str = ""                # Auto-generated: "What worked" or "What failed"
    pattern_tags: list[str] = field(default_factory=list)  # ["hook_strong", "retention_weak"]

    # Pre-publish eval integration (from eval.py)
    pre_publish_score: Optional[float] = None     # Lamar + Gary Vee binary eval %
    pre_publish_verdict: Optional[str] = None

    # Metadata
    scored_at: str = ""
    analytics_delay_hours: int = 48


def score_content_multi_signal(
    content_id: str,
    influencer_id: str,
    platform: str,
    content_type: str,
    funnel_stage: str,
    # Raw metrics — pass what you have, leave rest as defaults
    first_3s_retention: Optional[float] = None,
    scroll_stop_rate: Optional[float] = None,
    impressions: int = 0,
    initial_plays: int = 0,
    avg_view_duration: float = 0.0,
    total_duration: float = 0.0,
    completion_rate: Optional[float] = None,
    avg_view_percentage: float = 0.0,
    views: int = 0,
    comments: int = 0,
    saves: int = 0,
    shares: int = 0,
    likes: int = 0,
    cta_clicks: int = 0,
    link_clicks: int = 0,
    profile_visits: int = 0,
    channel_avg_views: float = 0.0,
    # Benchmarks (optional)
    your_avg: Optional[Benchmark] = None,
    niche_avg: Optional[Benchmark] = None,
    top_10: Optional[Benchmark] = None,
    # Pre-publish eval score (from eval.py)
    pre_publish_score: Optional[float] = None,
    pre_publish_verdict: Optional[str] = None,
    # Configurable weights (override defaults for tuning)
    weights: Optional[dict] = None,
) -> ContentScore:
    """Score a content piece using 5 weighted signals from real analytics.

    This is the main entry point for post-publish content scoring.
    Call this 48+ hours after publishing once analytics data is available.

    The weights are configurable — start with defaults, tune with real data
    after your first 50-100 scored posts.

    Returns a ContentScore with:
      - Individual signal breakdowns (raw, normalized, weighted)
      - Composite score (0-10)
      - Verdict (viral/hit/solid/weak/miss)
      - Benchmark comparisons (your avg, niche, top 10%)
      - Auto-extracted lesson
      - Pattern tags for the autoresearch loop
    """
    active_weights = dict(DEFAULT_WEIGHTS)
    if weights:
        for k, v in weights.items():
            if isinstance(k, str):
                k = SignalName(k)
            active_weights[k] = v

    # Normalize weights to sum to 1.0
    total_weight = sum(active_weights.values())
    if total_weight > 0 and abs(total_weight - 1.0) > 0.01:
        active_weights = {k: v / total_weight for k, v in active_weights.items()}

    # Compute raw signals
    raw_hook = compute_hook_score(first_3s_retention, scroll_stop_rate, impressions, initial_plays, platform)
    raw_retention = compute_retention_score(avg_view_duration, total_duration, completion_rate, avg_view_percentage)
    raw_engagement = compute_engagement_score(comments, saves, shares, views)
    raw_conversion = compute_conversion_score(cta_clicks, link_clicks, profile_visits, views)
    raw_outlier = compute_outlier_score(views, channel_avg_views)

    raw_signals = {
        SignalName.HOOK: raw_hook,
        SignalName.RETENTION: raw_retention,
        SignalName.ENGAGEMENT: raw_engagement,
        SignalName.CONVERSION: raw_conversion,
        SignalName.OUTLIER: raw_outlier,
    }

    # Normalize each signal and build results
    signal_results = []
    total_score = 0.0

    for signal_name, raw_val in raw_signals.items():
        good, great = _get_threshold(signal_name, platform)
        normalized, grade = _normalize_signal(raw_val, good, great)
        weight = active_weights.get(signal_name, 0.0)
        weighted = normalized * weight

        signal_results.append(SignalResult(
            signal=signal_name.value,
            raw_value=round(raw_val, 6),
            normalized=round(normalized, 2),
            weight=round(weight, 2),
            weighted_score=round(weighted, 3),
            grade=grade,
            threshold_good=good,
            threshold_great=great,
            platform=platform,
        ))
        total_score += weighted

    total_score = round(total_score, 2)

    # Determine verdict
    if total_score >= 8.0:
        verdict = Verdict.VIRAL
    elif total_score >= 6.0:
        verdict = Verdict.HIT
    elif total_score >= 4.0:
        verdict = Verdict.SOLID
    elif total_score >= 2.0:
        verdict = Verdict.WEAK
    else:
        verdict = Verdict.MISS

    # Benchmark comparisons
    raw_for_comparison = {
        "hook": raw_hook,
        "retention": raw_retention,
        "engagement": raw_engagement,
        "conversion": raw_conversion,
        "outlier": raw_outlier,
    }
    bench_comparison = BenchmarkComparison(
        your_avg=your_avg,
        niche_avg=niche_avg,
        top_10=top_10,
        vs_your_avg=_compare_to_benchmark(raw_for_comparison, your_avg),
        vs_niche_avg=_compare_to_benchmark(raw_for_comparison, niche_avg),
        vs_top_10=_compare_to_benchmark(raw_for_comparison, top_10),
    )

    # Extract lesson and pattern tags
    lesson, tags = _extract_lesson(signal_results, verdict.value, platform)

    score = ContentScore(
        content_id=content_id,
        influencer_id=influencer_id,
        platform=platform,
        content_type=content_type,
        funnel_stage=funnel_stage,
        signals=signal_results,
        total_score=total_score,
        verdict=verdict.value,
        weights_used={k.value: v for k, v in active_weights.items()},
        benchmarks=bench_comparison,
        lesson=lesson,
        pattern_tags=tags,
        pre_publish_score=pre_publish_score,
        pre_publish_verdict=pre_publish_verdict,
        scored_at=datetime.utcnow().isoformat(),
    )

    logger.info(
        f"[SCORING] {content_id} on {platform}: "
        f"{total_score}/10.0 → {verdict.value.upper()} | "
        f"Hook={raw_hook:.3f} Ret={raw_retention:.3f} "
        f"Eng={raw_engagement:.4f} Conv={raw_conversion:.4f} "
        f"Out={raw_outlier:.1f}x"
    )

    return score


# ============================================
# Lesson Extraction
# ============================================

def _extract_lesson(
    signals: list[SignalResult],
    verdict: str,
    platform: str,
) -> tuple[str, list[str]]:
    """Auto-extract a lesson and pattern tags from signal results.

    VIRAL/HIT → "What worked?" → pattern library
    WEAK/MISS → "What failed?" → anti-pattern library
    """
    tags = []
    strengths = []
    weaknesses = []

    for s in signals:
        tag_prefix = s.signal
        if s.grade == "great":
            tags.append(f"{tag_prefix}_strong")
            strengths.append(s.signal)
        elif s.grade == "good":
            tags.append(f"{tag_prefix}_solid")
        elif s.grade == "below":
            tags.append(f"{tag_prefix}_weak")
            weaknesses.append(s.signal)
        elif s.grade == "poor":
            tags.append(f"{tag_prefix}_failing")
            weaknesses.append(s.signal)
        elif s.grade == "no_data":
            tags.append(f"{tag_prefix}_no_data")

    if verdict in ("viral", "hit"):
        if strengths:
            lesson = f"WIN on {platform}: Strong {', '.join(strengths)}. Pattern to replicate."
        else:
            lesson = f"WIN on {platform}: Balanced performance across all signals."
    elif verdict == "solid":
        if weaknesses:
            lesson = f"SOLID on {platform}: Improve {', '.join(weaknesses)} to reach HIT tier."
        else:
            lesson = f"SOLID on {platform}: Consistent but no standout signal. Add a spike."
    else:
        if weaknesses:
            lesson = f"MISS on {platform}: Failed on {', '.join(weaknesses)}. Investigate root cause."
        else:
            lesson = f"MISS on {platform}: Low performance across all signals. Review content-platform fit."

    return lesson, tags


# ============================================
# Aggregate Scoring (Batch)
# ============================================

def compute_channel_benchmarks(
    scores: list[ContentScore],
    period_days: int = 90,
) -> Benchmark:
    """Compute YOUR average benchmark from a list of scored content.

    Call this with your last 90 days of scored content to build
    the 'your_average' benchmark for future comparisons.
    """
    if not scores:
        return Benchmark(label="your_average", period_days=period_days)

    raw_signals = {name: [] for name in SignalName}
    for score in scores:
        for s in score.signals:
            signal_name = SignalName(s.signal)
            if s.raw_value > 0:
                raw_signals[signal_name].append(s.raw_value)

    def _avg(vals):
        return sum(vals) / len(vals) if vals else 0.0

    return Benchmark(
        label="your_average",
        hook=round(_avg(raw_signals[SignalName.HOOK]), 4),
        retention=round(_avg(raw_signals[SignalName.RETENTION]), 4),
        engagement=round(_avg(raw_signals[SignalName.ENGAGEMENT]), 6),
        conversion=round(_avg(raw_signals[SignalName.CONVERSION]), 6),
        outlier=1.0,  # By definition, your average outlier is 1.0x
        sample_size=len(scores),
        period_days=period_days,
    )


def compute_top_10_benchmark(scores: list[ContentScore]) -> Benchmark:
    """Compute TOP 10% benchmark from your scored content.

    Takes the top 10% performers and averages their signals
    to give you an aspiration target.
    """
    if len(scores) < 10:
        return Benchmark(label="top_10_percent")

    sorted_scores = sorted(scores, key=lambda s: s.total_score, reverse=True)
    top_n = max(1, len(sorted_scores) // 10)
    top_scores = sorted_scores[:top_n]

    return compute_channel_benchmarks(top_scores, period_days=90)


def score_distribution(scores: list[ContentScore]) -> dict:
    """Get distribution of verdicts across scored content.

    Returns: {"viral": 2, "hit": 5, "solid": 12, "weak": 8, "miss": 3}
    """
    dist = {v.value: 0 for v in Verdict if v != Verdict.PENDING}
    for s in scores:
        if s.verdict in dist:
            dist[s.verdict] += 1
    return dist


def signal_averages(scores: list[ContentScore]) -> dict[str, float]:
    """Average normalized score per signal across all content.

    Useful for identifying systemic strengths and weaknesses:
    "Our hooks are consistently 7.2 but our conversions are 2.1"
    """
    sums = {}
    counts = {}
    for score in scores:
        for s in score.signals:
            sums[s.signal] = sums.get(s.signal, 0) + s.normalized
            counts[s.signal] = counts.get(s.signal, 0) + 1
    return {k: round(sums[k] / counts[k], 2) for k in sums if counts[k] > 0}


# ============================================
# Serialization
# ============================================

def score_to_dict(score: ContentScore) -> dict:
    """Serialize a ContentScore to a JSON-safe dict for storage/API."""
    d = {
        "content_id": score.content_id,
        "influencer_id": score.influencer_id,
        "platform": score.platform,
        "content_type": score.content_type,
        "funnel_stage": score.funnel_stage,
        "total_score": score.total_score,
        "verdict": score.verdict,
        "weights_used": score.weights_used,
        "lesson": score.lesson,
        "pattern_tags": score.pattern_tags,
        "pre_publish_score": score.pre_publish_score,
        "pre_publish_verdict": score.pre_publish_verdict,
        "scored_at": score.scored_at,
        "signals": [
            {
                "signal": s.signal,
                "raw_value": s.raw_value,
                "normalized": s.normalized,
                "weight": s.weight,
                "weighted_score": s.weighted_score,
                "grade": s.grade,
            }
            for s in score.signals
        ],
    }
    if score.benchmarks:
        d["benchmarks"] = {
            "vs_your_avg": score.benchmarks.vs_your_avg,
            "vs_niche_avg": score.benchmarks.vs_niche_avg,
            "vs_top_10": score.benchmarks.vs_top_10,
        }
    return d


def score_summary(score: ContentScore) -> str:
    """Human-readable summary of a content score."""
    lines = [
        f"{'='*60}",
        f"  CONTENT SCORE: {score.content_id}",
        f"  {score.platform.upper()} | {score.content_type} | {score.funnel_stage.upper()}",
        f"{'='*60}",
        f"",
        f"  TOTAL: {score.total_score}/10.0 → {score.verdict.upper()}",
        f"",
        f"  SIGNALS:",
    ]
    for s in score.signals:
        bar_len = int(s.normalized)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(
            f"    {s.signal:<12} {bar} {s.normalized:>5.1f}/10 "
            f"({s.grade:<6}) [raw: {s.raw_value:.4f}] × {s.weight:.0%}"
        )

    if score.benchmarks:
        if score.benchmarks.vs_your_avg:
            lines.append(f"")
            lines.append(f"  VS YOUR AVG: {score.benchmarks.vs_your_avg}")
        if score.benchmarks.vs_niche_avg:
            lines.append(f"  VS NICHE:    {score.benchmarks.vs_niche_avg}")

    lines.append(f"")
    lines.append(f"  LESSON: {score.lesson}")
    lines.append(f"  TAGS:   {', '.join(score.pattern_tags)}")

    if score.pre_publish_score is not None:
        lines.append(f"  PRE-PUB: {score.pre_publish_score:.0f}% ({score.pre_publish_verdict})")

    lines.append(f"{'='*60}")
    return "\n".join(lines)
