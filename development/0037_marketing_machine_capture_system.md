# 0037 — Marketing Machine: Capture System (Waitlist + Assessments)
**Date:** 2026-04-14
**Category:** Marketing Machine — Lead Capture Layer
**Status:** V1 — Built + tested (scoring verified)
**Framework:** Daniel Priestley "Over-Subscribed" + Business Matrix 0010
**Depends on:** 0036 (full pipeline), 0010 (Priestley Lead Gen)

---

## What This Is

Two capture mechanisms running in parallel, following Priestley's lead gen framework:

1. **Waitlist** (basic) — Email capture for future/current capacity
2. **Assessment / Scorecard** (advanced) — Readiness quiz that segments buyers into a pyramid

Both feed the same lead pipeline. Assessment submissions ALSO add to waitlist (dual capture, zero leakage).

---

## Why Two Mechanisms

From Daniel Priestley (quoted in `ai influencers development_0001`):

> "For someone to buy, they need to be 90% sure. For someone to signal interest,
> they only need to be 10-20% sure. So signals capture 5-10x more leads than direct CTAs.
> Then the signals let you segment, create Market Forces, and reveal demand/supply tension."

The waitlist captures the "I might want this" crowd.
The assessment captures the "let me see where I stand" crowd — which is WAY bigger and gets segmented for free.

---

## Files Built

| File | Lines | What It Does |
|------|-------|--------------|
| `capture/waitlist.py` | ~260 | Supabase storage + Resend welcome email (V1 basic) |
| `capture/assessment.py` | ~560 | Full assessment engine: 4 pre-built scorecards, scoring, storage, results email, transparency stats |
| `capture/__init__.py` | ~40 | Unified exports for both mechanisms |

---

## The 4 Pre-Built Assessments

One per face, each following Priestley's "Are You Ready for X?" pattern:

| Assessment ID | Name | Face | Questions | Categories |
|---------------|------|------|-----------|------------|
| `ai_readiness` | Are You Ready to Run Your Business on AI? | Anthony (Face 0) | 20 | foundation, marketing, bottleneck, tech, urgency |
| `ai_stack_readiness` | Is Your AI Tech Stack Built Right? | Influencer 1 (The Builder) | 13 | stack, workflow, vision |
| `scale_readiness` | Is Your Business Ready to Scale? | Influencer 2 (The Operator) | 18 | offer, leads, sales, delivery, retention |
| `brand_readiness` | Does Your Brand Actually Convert? | Influencer 3 (The Director) | 16 | identity, positioning, content, experience |

Each assessment:
- Has weighted questions (1-3x weight for critical questions)
- Includes segmentation questions (open text, not scored — used for personalization)
- Classifies into 4 tiers: premium / qualified / aware / early
- Delivers personalized results message + tier-specific CTA
- Tracks via Supabase with full UTM attribution

---

## Scoring Tiers (Priestley Pyramid)

| Tier | Threshold | Routing | Meaning |
|------|-----------|---------|---------|
| **premium** | 80%+ | Route to Sales Operator immediately | Top of pyramid. Hot lead. Ready to buy. |
| **qualified** | 60-80% | 7-day nurture sequence | Good fit. Close 1-2 gaps and they're ready. |
| **aware** | 40-60% | Content drip + waitlist | Needs education first. Show them the problem. |
| **early** | 0-40% | Long-term nurture | Too early. Keep in touch, don't pitch yet. |

**Smoke test results:**
```
All YES:   33/33 = 100% → premium
~80%:      26/33 = 79%  → qualified
Mixed:     17/33 = 52%  → aware
All NO:     0/33 = 0%   → early
```

---

## The Full Capture Flow

```
Stranger sees content
    ↓
Clicks CTA: "Take the AI Readiness Assessment" (from DM keyword, bio link, or ad)
    ↓
Lands on assessment page
    ↓
Answers 20 questions (3 minutes)
    ↓
Enters email + name on final screen
    ↓
submit_assessment() fires:
    ├─→ Scores the answers (weighted)
    ├─→ Stores response in `assessment_responses` table
    ├─→ Dual capture: also adds to `waitlist` table
    ├─→ Sends personalized results email via Resend
    └─→ Returns results payload for immediate display
    ↓
Results page shows:
    ├─→ Score + tier
    ├─→ Personalized message
    ├─→ Tier-specific CTA
    └─→ Transparency stats ("847 people have taken this, top 10% scored 85%+")
    ↓
Lead is now in the pipeline with:
    - Email, name
    - Score + tier
    - Source platform, influencer, campaign, UTM
    - Segmentation data (their answers to open questions)
    - Behavior-triggerable (they scored, they're warm)
```

---

## The Transparency Stats (Market Forces)

Priestley says: the score alone isn't enough. You need to show the Market Forces — the ratio of interest to supply. That's what creates demand tension.

`get_assessment_stats(assessment_id)` returns:

```json
{
    "total_completions": 847,
    "by_tier": {"premium": 72, "qualified": 203, "aware": 412, "early": 160},
    "avg_score": 58.3,
    "top_10_threshold": 85.5
}
```

Display on results page:
> "You scored 73%. That's above the average (58%). 847 people have taken this assessment. The top 10% scored above 85% — you're close."

Now they want to retake it. Now they want to book a call to close the gap. That's Market Forces.

---

## Supabase Migrations Needed

```sql
-- Assessment responses table
CREATE TABLE IF NOT EXISTS assessment_responses (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    assessment_id TEXT NOT NULL,
    respondent_email TEXT NOT NULL,
    respondent_name TEXT,
    source_platform TEXT,
    source_influencer TEXT,
    source_campaign TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_content TEXT,
    answers JSONB,
    segmentation_data JSONB,
    raw_score FLOAT,
    max_score FLOAT,
    percentage FLOAT,
    tier TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_assessments_id ON assessment_responses(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessments_email ON assessment_responses(respondent_email);
CREATE INDEX IF NOT EXISTS idx_assessments_tier ON assessment_responses(tier);

-- RLS
ALTER TABLE assessment_responses ENABLE ROW LEVEL SECURITY;
```

(Waitlist table migration is in 0036.)

---

## Usage Examples

### Render assessment for a landing page

```python
from content_engine.capture import get_assessment_questions

payload = get_assessment_questions("ai_readiness")
# Returns: {id, name, description, intro_text, questions: [{id, text, type, options, category}]}
# Frontend renders the quiz from this payload
```

### Submit assessment from API endpoint

```python
from content_engine.capture import submit_assessment

result = await submit_assessment(
    assessment_id="ai_readiness",
    email="user@example.com",
    name="Jane Doe",
    answers={
        "af_1": True, "af_2": True, "af_3": True, "af_4": False,
        # ... all 20 questions
    },
    source_platform="twitter",
    source_influencer="anthony",
    utm_source="twitter",
    utm_medium="social",
    utm_content="OPERATOR",  # keyword that triggered it
)
# Returns: {success, tier, percentage, message, cta, stats, response_id}
```

### Direct waitlist join (no assessment)

```python
from content_engine.capture import capture_waitlist_lead, WaitlistEntry

result = await capture_waitlist_lead(WaitlistEntry(
    email="user@example.com",
    name="Jane Doe",
    source_platform="instagram",
    source_influencer="influencer_1",
))
# Returns: CaptureResult(success, is_new, welcome_sent)
```

### Get transparency stats for results page

```python
from content_engine.capture import get_assessment_stats

stats = await get_assessment_stats("ai_readiness")
# Returns: {total_completions, by_tier, avg_score, top_10_threshold}
```

---

## What's Next

1. **Landing pages** (Vercel/Next.js) — one per assessment + one unified waitlist page
2. **Backend API endpoints** — expose `submit_assessment()` and `capture_waitlist_lead()` via FastAPI routes in brain
3. **Results page template** — React component that renders score + tier + CTA + stats
4. **Monitor integration** — when a keyword DM fires (BUILD/SCALE/BRAND/OPERATOR), the auto-reply should link to the relevant assessment, not just a magnet
5. **Weekly digest** — Anthony gets a weekly email: "X people scored premium this week. Here's the segmentation data."

---

## Coined Terms Used
- **Signal of Interest** — low-commitment capture (10-20% sure, not 90%)
- **Assessment / Scorecard** — Priestley's readiness quiz mechanism
- **Market Forces** — transparency of demand/supply ratio
- **Over-Subscribed** — state where demand exceeds supply (the goal)
- **Pyramid Segmentation** — premium/qualified/aware/early tiers
- **Dual Capture** — assessment response auto-added to waitlist too