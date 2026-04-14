# 0035 — Marketing Machine: Platform Publishers
**Date:** 2026-04-12
**Category:** Marketing Machine — Content Distribution Layer
**Status:** V1 — Built, needs API keys to test live
**SAR:** Secure, Autonomous, Reliable
**Depends on:** 0033 (AI influencers), 0034 (wiring spec), 0032 (scoring engine)

---

## What This Is

Platform publishers that post content to Twitter, Instagram, LinkedIn, and TikTok via their native APIs. Posting patterns harvested from Postiz (reference/postiz/) — we studied their 34-provider implementation and extracted the API flows we need.

We built our own instead of using Postiz as a dependency because:
1. We want full control over the posting pipeline
2. The publishers are thin — same pattern as our existing analytics adapters (content_engine/analytics/)
3. Our compliance layer is more conservative than Postiz's defaults
4. No AGPL license concerns
5. Direct integration with our scheduler, not through a middleware service

---

## Architecture

```
Content Engine (scoring, eval, scheduling)
       ↓
  Compliance Checker (rate limits, disclosure, ban prevention)
       ↓
  Publisher (platform-specific API calls)
       ↓
  Platform API (Twitter v2, IG Graph, LinkedIn REST, TikTok Open)
       ↓
  Post goes live → URL returned → tracked in scheduler
```

All OAuth tokens: env vars now, Nango integration planned (Nango already deployed with 700+ providers).

---

## Files Built

| File | Lines | What It Does |
|------|-------|-------------|
| `publishers/__init__.py` | ~80 | Package init, `register_all_publishers()` wires into scheduler with compliance wrapping |
| `publishers/base.py` | ~180 | Abstract `BasePublisher` with retry (3x exponential backoff), error classification, `PostPayload` + `PublishResult` data models |
| `publishers/compliance.py` | ~200 | `ComplianceChecker` — rate limits per platform per influencer, action recording, daily summary |
| `publishers/twitter.py` | ~150 | Twitter API v2 via tweepy — text posts, media upload (v1.1 for media), threads via reply_to |
| `publishers/instagram.py` | ~200 | Instagram Graph API v20 — container → poll → publish flow. Images, videos/reels, carousels |
| `publishers/linkedin.py` | ~200 | LinkedIn REST API — 3-step media upload (init → chunked PUT → finalize), text/image/video/carousel |
| `publishers/tiktok.py` | ~180 | TikTok Open API v2 — URL-based media, async publish with status polling, video + photo carousel |

---

## Platform Posting Patterns (Harvested from Postiz)

| Platform | Auth | Media Upload | Post Flow | Async? |
|----------|------|-------------|-----------|--------|
| **Twitter** | OAuth 1.0a (consumer + access tokens) | Buffer upload via v1.1 API | `client.v2.tweet()` | No — immediate |
| **Instagram** | OAuth 2.0 (FB page token) | URL-based (host media first) | Container → poll status → publish | Yes — poll every 10s |
| **LinkedIn** | OAuth 2.0 (bearer token) | Chunked PUT (2MB chunks) + finalize | REST POST to /rest/posts | No — immediate |
| **TikTok** | OAuth 2.0 (bearer token) | URL-based (PULL_FROM_URL) | Init publish → poll status | Yes — poll every 10s |

---

## Compliance Layer (from 0033)

| Platform | Posts/Day | DMs/Day | Min Interval | Disclosure Required |
|----------|-----------|---------|--------------|-------------------|
| Twitter | 3 per face | 50 | 2 min | Yes (API flag) |
| Instagram | 3 per face | 30 | 10 min | Yes (Meta policy) |
| TikTok | 3 per face | 20 | 20 min | No |
| LinkedIn | 2 per face | 25 | 20 min | Yes (professional standards) |

Compliance checker runs BEFORE every post. If limit reached → post rejected with "next safe time" message. No exceptions, no overrides.

---

## How to Use

```python
from content_engine.pipeline.scheduler import ContentScheduler
from content_engine.publishers import register_all_publishers

# Create scheduler
scheduler = ContentScheduler(approval_mode="auto_post")

# Register all publishers (compliance-wrapped)
publishers = register_all_publishers(scheduler)

# Queue content
scheduler.add_to_queue(
    content_id="post_001",
    pillar_id="pillar_001",
    influencer_id="influencer_1",
    platform="twitter",
    caption="Your AI team never sleeps. Here's how we built ours:",
    hashtags=["AI", "automation", "marketing"],
    funnel_stage="tof",
    content_type="micro",
)

# Publish when due
results = await scheduler.publish_due()
```

---

## What's Next

1. **Nango integration** — swap env var tokens for Nango-managed OAuth (auto-refresh)
2. **Orchestrator** — `orchestrator.py` that runs the full generate → eval → schedule → publish → score → learn loop
3. **Comment/DM monitor** — `monitor.py` for keyword trigger detection
4. **YouTube + Facebook publishers** — Phase 3 (after MVP Wednesday)
5. **Media hosting** — need a place to host video/image URLs for IG + TikTok (they pull from URL)
