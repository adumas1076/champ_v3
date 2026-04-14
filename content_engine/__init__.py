# Cocreatiq OS — Content Engine
# Phase 3: Clone Setup, Autoresearch Loop, Content Pipeline
#
# Modules:
#   eval.py         — Pre-publish binary scoring (Lamar + Gary Vee criteria)
#   scoring.py      — Post-publish multi-signal scoring (Hook/Retention/Engagement/Conversion/Outlier)
#   autoresearch.py — Self-improving loop (pull analytics → score → correlate → learn → repeat)
#   analytics/      — 6 platform adapters (YouTube, IG, TikTok, X, LinkedIn, Facebook)
#   pipeline/       — Content production (repurpose, format, schedule, funnel)
#   influencers/    — AI clone profiles and loader

from content_engine.scoring import (
    score_content_multi_signal,
    ContentScore,
    Benchmark,
    Verdict,
    SignalName,
    DEFAULT_WEIGHTS,
    compute_channel_benchmarks,
    compute_top_10_benchmark,
    score_distribution,
    signal_averages,
    score_to_dict,
    score_summary,
)
from content_engine.eval import (
    score_content,
    ContentScoreCard,
    build_eval_prompt,
)
