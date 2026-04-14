# 0036 — Marketing Machine: Full Pipeline Build
**Date:** 2026-04-14
**Category:** Marketing Machine — Complete System
**Status:** V1 — All components built, needs API keys + deployment to go live
**SAR:** Secure, Autonomous, Reliable
**Session:** Marketing Machine Tech Build

---

## What Got Built This Session

15 new files + 2 modified files. The complete Marketing Machine pipeline from content creation to lead capture.

---

## File Map

```
content_engine/
├── scoring.py              ← NEW — Multi-signal scoring (5 signals, 0-10 scale)
├── orchestrator.py         ← NEW — Marketing Department conductor (6 roles, daily + continuous)
├── llm_adapter.py          ← NEW — Connects Creator role to brain LLM (API + direct modes)
├── monitor.py              ← NEW — Comment/DM keyword detection + auto-response
├── autoresearch.py         ← MODIFIED — Wired multi-signal scoring into autoresearch loop
├── __init__.py             ← MODIFIED — Updated exports
│
├── publishers/             ← NEW — 6 platform publishers + compliance
│   ├── __init__.py         ← Registration + compliance wrapping for scheduler
│   ├── base.py             ← BasePublisher (retry 3x, error classification, PostPayload)
│   ├── compliance.py       ← Rate limits, disclosure, ban prevention per platform
│   ├── twitter.py          ← Twitter API v2 via tweepy
│   ├── instagram.py        ← Instagram Graph API v20 (container → poll → publish)
│   ├── linkedin.py         ← LinkedIn REST API (chunked upload, 2MB)
│   ├── tiktok.py           ← TikTok Open API v2 (URL + status polling)
│   ├── youtube.py          ← YouTube Data API v3 (resumable upload, 10MB chunks)
│   ├── facebook.py         ← Facebook Graph API v20 (URL-based, reel support)
│   └── nango_adapter.py    ← Nango OAuth token fetcher (auto-refresh)
│
├── capture/                ← NEW — V1 lead capture
│   ├── __init__.py
│   └── waitlist.py         ← Supabase storage + Resend welcome email
│
├── eval.py                 (existed — untouched)
├── pipeline/               (existed — untouched)
│   ├── scheduler.py        (publishers plug in via register_publisher())
│   ├── repurpose.py
│   ├── platforms.py
│   └── funnel.py
├── analytics/              (existed — untouched, 6 platform read adapters)
└── influencers/            (existed — untouched, 3 YAML profiles + loader)
```

---

## Component Summary

### 1. Multi-Signal Scoring Engine (`scoring.py`)
- 5 weighted signals: Hook (30%), Retention (25%), Engagement (20%), Conversion (15%), Outlier (10%)
- Platform-aware thresholds (different "good"/"great" per platform)
- Configurable weights for tuning with real data
- 3-tier benchmarks: YOUR avg, NICHE avg, TOP 10%
- Verdicts: VIRAL (>8.0) → HIT → SOLID → WEAK → MISS (<2.0)
- Auto lesson extraction + pattern tagging

### 2. Platform Publishers (`publishers/`)
- 6 platforms: Twitter, Instagram, LinkedIn, TikTok, YouTube, Facebook
- Patterns harvested from Postiz (reference/postiz/) — not a dependency, our own code
- BasePublisher with 3x retry, exponential backoff, error classification
- Compliance layer: rate limits per face per platform, disclosure enforcement
- Plugs into existing scheduler.py via register_publisher()
- Nango adapter for OAuth token management (auto-refresh)

### 3. Orchestrator (`orchestrator.py`)
- Marketing Department structure: Strategist → Creator → QA → Publisher → Analyst → Scout
- Daily cycle: plan → write → score → schedule → post → measure → learn
- Continuous mode: runs forever, daily content at morning, publisher checks every 5 min
- Funnel balance enforcement (50% TOF / 30% MOF / 20% BOF)
- Rework loop: failed QA pieces get revised up to 2x
- V1: template-based text generation. V2: LLM-powered via llm_adapter

### 4. LLM Adapter (`llm_adapter.py`)
- Connects orchestrator Creator role to brain's LLM
- Two modes: Brain API (HTTP) or direct LiteLLM call
- Prompt construction with: Lamar structure, brand voice, platform specs, learned rules, funnel stage
- Also provides evaluate_script() for QA Gate V2

### 5. Keyword Monitor (`monitor.py`)
- Polls platform APIs every 60s for keyword triggers in comments/DMs
- 5 keywords: BUILD, SCALE, BRAND, OPERATOR, START
- Auto-DM response with lead magnet + qualifying question
- Deduplication (won't re-trigger on same interaction)
- Pluggable: register any publisher that implements get_comments/get_dms/send_dm

### 6. Waitlist Capture (`capture/waitlist.py`)
- V1 lead capture: email → Supabase → Resend welcome email → done
- UTM tracking (source platform, influencer, campaign)
- Duplicate detection (existing emails skipped gracefully)
- Stats endpoint (total leads, by platform, by influencer)
- Welcome email with branded HTML template

---

## What's Needed to Go Live

| Requirement | Status | Action |
|------------|--------|--------|
| Supabase `waitlist` table | Not created | Run CREATE TABLE SQL |
| RESEND_API_KEY | Not set | Sign up at resend.com, add to .env |
| NANGO_SECRET_KEY | Not set | Already deployed, get key from Nango dashboard |
| Platform OAuth tokens | Not connected | Set up via Nango for each face × platform |
| BRAIN_URL | Already set (8100) | Brain must be running for LLM generation |
| Influencer YAML profiles | 3 exist | Need influencer_0_anthony.yaml |
| Topic bank | Not populated | Seed with initial topics for Content Strategist |
| Landing page | Not built | Simple Next.js page on Vercel |

---

## Environment Variables Needed

```bash
# Existing (already in .env.example)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...

# New — add to .env
RESEND_API_KEY=re_xxxxxxxxxx
RESEND_FROM_NAME=Cocreatiq
RESEND_FROM_EMAIL=hello@cocreatiq.com
NANGO_BASE_URL=http://localhost:3003
NANGO_SECRET_KEY=xxxxxxxxxxxx

# Per-platform (if not using Nango, set these directly)
X_API_KEY=xxxxxxxxxx
X_API_SECRET=xxxxxxxxxx
X_ACCESS_TOKEN=xxxxxxxxxx
X_ACCESS_SECRET=xxxxxxxxxx
INSTAGRAM_ACCESS_TOKEN=xxxxxxxxxx
INSTAGRAM_BUSINESS_ID=xxxxxxxxxx
LINKEDIN_ACCESS_TOKEN=xxxxxxxxxx
LINKEDIN_PERSON_ID=xxxxxxxxxx
TIKTOK_ACCESS_TOKEN=xxxxxxxxxx
TIKTOK_OPEN_ID=xxxxxxxxxx
YOUTUBE_CLIENT_ID=xxxxxxxxxx
YOUTUBE_CLIENT_SECRET=xxxxxxxxxx
YOUTUBE_REFRESH_TOKEN=xxxxxxxxxx
FACEBOOK_PAGE_ACCESS_TOKEN=xxxxxxxxxx
FACEBOOK_PAGE_ID=xxxxxxxxxx
```

---

## Supabase Migration

```sql
-- Run this to create the waitlist table
CREATE TABLE IF NOT EXISTS waitlist (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    source_platform TEXT,
    source_influencer TEXT,
    source_campaign TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_content TEXT,
    status TEXT DEFAULT 'active',
    welcome_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE waitlist ENABLE ROW LEVEL SECURITY;

-- Index for fast lookups
CREATE INDEX idx_waitlist_email ON waitlist(email);
CREATE INDEX idx_waitlist_source ON waitlist(source_platform, source_influencer);
```

---

## Development Docs Created

| Doc | Covers |
|-----|--------|
| `0032_marketing_machine_scoring_engine.md` | Scoring engine: 5 signals, weights, thresholds, benchmarks |
| `0035_marketing_machine_publishers.md` | Publishers: 6 platforms, compliance, Postiz harvest patterns |
| `0036_marketing_machine_full_pipeline.md` | This doc — complete system overview |
