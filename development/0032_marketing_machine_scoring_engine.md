# 0032 — Marketing Machine: Multi-Signal Content Scoring Engine
**Date:** 2026-04-12
**Category:** Marketing Machine — Content Engine Intelligence Layer
**Status:** V1 — Built and wired
**Owner:** Marketing Machine Tech Session

---

## What This Is

The multi-signal content scoring engine replaces the old binary pass/fail eval system with a **weighted 5-signal analytics-driven scoring system** that grades every piece of content against real platform data.

**Old system** (eval.py): 34 binary criteria (yes/no) → percentage → verdict. Pre-publish only. No analytics.

**New system** (scoring.py): 5 weighted signals computed from real API data → 0-10 composite score → verdict + lesson + pattern tags. Post-publish, analytics-driven. Feeds autoresearch loop.

**Both systems work together:**
- eval.py scores content BEFORE publish (quality gate)
- scoring.py scores content AFTER publish (performance measurement)
- Autoresearch loop correlates both to learn what quality criteria actually predict real-world performance

---

## The 5 Signals

| # | Signal | Weight | What It Measures | Why It Matters |
|---|--------|--------|------------------|----------------|
| 1 | **Hook** | 30% | First 3s retention (YT) or scroll-stop rate (IG/TT) | If they don't stop, nothing else matters |
| 2 | **Retention** | 25% | Avg view duration / total duration | Did they stay? Measures content substance |
| 3 | **Engagement** | 20% | (Comments + Saves) / Views | Depth over vanity — saves and comments mean value |
| 4 | **Conversion** | 15% | CTA clicks / total views | Did it drive action? The business signal |
| 5 | **Outlier** | 10% | Views / channel 90-day avg views | Is this punching above its weight? |

### Why These Weights

- **Hook at 30%**: Nothing else matters if they scroll past. This is the Lamar Mistake #1 filter — are you stopping the RIGHT people?
- **Retention at 25%**: The content has to deliver. High hook + low retention = clickbait = brand death (Lamar payoff rule)
- **Engagement at 20%**: Comments and saves indicate DEPTH. Likes are vanity. Authority > attention.
- **Conversion at 15%**: This is a business, not a hobby. Content without conversion is entertainment, not marketing.
- **Outlier at 10%**: Bonus signal. When something goes 5-10x above your average, pay attention — there's a pattern to extract.

### Weights Are Configurable

These defaults are educated guesses from the Lamar + Hormozi frameworks. After scoring 50-100 real posts, tune the weights based on what actually correlates with business outcomes (revenue, signups, retention).

```python
# Override weights for Client 0 tuning
custom_weights = {
    "hook": 0.35,       # Anthony's audience needs harder hooks
    "retention": 0.20,
    "engagement": 0.20,
    "conversion": 0.20,  # Prioritize conversion for revenue
    "outlier": 0.05,
}
score = score_content_multi_signal(..., weights=custom_weights)
```

---

## Platform-Aware Thresholds

Each signal has different "good" and "great" thresholds per platform because audiences behave differently:

| Signal | YouTube | Instagram | TikTok | LinkedIn | Twitter |
|--------|---------|-----------|--------|----------|---------|
| Hook (good/great) | 65%/80% | 50%/70% | 55%/75% | 40%/60% | 30%/50% |
| Retention (good/great) | 40%/60% | 50%/70% | 50%/70% | 30%/50% | 20%/40% |
| Engagement (good/great) | 2%/5% | 3%/6% | 2%/5% | 3%/7% | 1%/3% |
| Conversion (good/great) | 1%/3% | 1%/3% | 0.5%/2% | 2%/5% | 1%/3% |
| Outlier | 5x/10x | 5x/10x | 5x/10x | 5x/10x | 5x/10x |

---

## Verdicts

| Score | Verdict | Action |
|-------|---------|--------|
| > 8.0 | **VIRAL** | Extract pattern → add to pattern library → replicate |
| 6.0 - 8.0 | **HIT** | Working formula → double down on this format |
| 4.0 - 6.0 | **SOLID** | Acceptable. Identify weakest signal, improve it |
| 2.0 - 4.0 | **WEAK** | Investigate root cause. Check content-platform fit |
| < 2.0 | **MISS** | Content failed. Extract anti-pattern → avoid repeating |

---

## Three Benchmarks

Every score is compared against three reference points:

1. **YOUR Average** — personal baseline computed from your last 90 days of scored content
2. **NICHE Average** — competitive benchmark from Pipeline 6 (competitive benchmarking)
3. **TOP 10%** — your own top 10% performers, showing what YOU are capable of when it clicks

This answers: "Is this good for me? Is this good for my niche? Is this as good as my best?"

---

## Autoresearch Integration

The scoring engine is wired directly into the autoresearch loop (`autoresearch.py`):

```
PUBLISH content
  → WAIT 48 hours
  → PULL analytics from 6 platform APIs
  → COMPUTE 5 signals per piece
  → SCORE (0-10 composite)
  → COMPARE to 3 benchmarks
  → EXTRACT lesson + pattern tags
  → UPDATE Marketing Operator knowledge (Letta)
  → GENERATE next batch using updated rules
  → QA check
  → PUBLISH
  → LOOP
```

Every cycle, the autoresearch loop:
- Scores all recent content with multi-signal scoring
- Computes channel benchmarks (YOUR average)
- Identifies viral/hit patterns and miss anti-patterns
- Generates learned rules incorporating signal-level insights
- Stores everything in Letta knowledge block for the Marketing Operator

---

## Files Modified

| File | What Changed |
|------|-------------|
| `content_engine/scoring.py` | **NEW** — 450+ lines. Multi-signal engine, benchmarks, serialization |
| `content_engine/autoresearch.py` | Imports scoring module, added 13 new fields to ContentPerformance, multi-signal scoring step in cycle, extended platform data extraction, multi-signal lesson generation |
| `content_engine/__init__.py` | Updated exports with scoring module |
| `development/0032_marketing_machine_scoring_engine.md` | **NEW** — this doc |

---

## What's Next

1. **Scraping pipelines** — Thumbnail intelligence, title intelligence, VidIQ outlier detection (Pipeline 1 + 2 from 0031)
2. **Platform publishers** — Actual API posting to YouTube, IG, TikTok, X, LinkedIn (content_engine/publishers/)
3. **Lead scoring engine** — Intent + Fit scoring for Click to Client funnel routing
4. **Email infrastructure** — Resend/SendGrid, templates, 7-day nurture sequence
5. **Stripe checkout** — Webhook handler, subscription management

---

## Coined Terms Used
- **Content Engine** — the AI-powered content creation + analytics + self-improvement system
- **Marketing Machine** — the complete click-to-client marketing infrastructure
- **Click to Client** — the universal 10-step funnel framework
- **Smart Funnels** — score-based adaptive routing (TOFU/MOFU/BOFU)
- **Autoresearch Loop** — generate → score → learn → improve → repeat
