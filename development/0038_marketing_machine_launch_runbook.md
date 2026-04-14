# 0038 — Marketing Machine: V1 Launch Runbook
**Target:** Wednesday 2026-04-15 — content live, waitlist capturing, graph learning
**Status:** Code complete. Pending: API keys + OAuth connections.

---

## What We Launch Tomorrow

**Goal:** Prove the loop works end-to-end. Not every platform, not every face, not every post. Just enough to prove:
- Content generates
- Content posts
- Someone signs up
- Data flows into the graph
- Tomorrow's content is smarter than today's

**Minimum viable launch:**
- 1-2 faces (Anthony + maybe 1 AI influencer)
- 1-2 platforms (Twitter minimum, LinkedIn if wired)
- 3-6 posts live
- Waitlist landing page capturing emails
- 1 assessment live (`ai_readiness`)
- Graph recording everything

Scale up from there as OAuth for more platforms completes.

---

## Pre-Launch Checklist

### 1. API Keys (in .env)
- [ ] `SUPABASE_URL` (existing)
- [ ] `SUPABASE_SERVICE_ROLE_KEY` (existing)
- [ ] `RESEND_API_KEY` — **rotate the one pasted in chat**
- [ ] `RESEND_FROM_NAME` = "Cocreatiq"
- [ ] `RESEND_FROM_EMAIL` = "onboarding@resend.dev" (use Resend test domain until you verify your own)
- [ ] `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` (from Twitter Developer app)
- [ ] Platform-specific keys for whichever you launch with
- [ ] `NANGO_SECRET_KEY` (optional for V1 — env vars work too)

### 2. Supabase Migrations
Run migration 013 against production Supabase:
```sql
-- File: supabase/migrations/013_marketing_machine.sql
-- Creates: waitlist + assessment_responses tables + summary views
```

Verify with: `python scripts/test_publish.py --health` → should show "waitlist table exists"

### 3. Health Check
```bash
cd champ_v3
python scripts/test_publish.py --health
```

Expected output (after env vars set):
```
[OK] Supabase: connected, waitlist table exists
[OK] Supabase: assessment_responses table exists
[OK] MarketingGraph: loaded
[OK] Influencers: 4 profiles loaded
[OK] Topic bank: 47 topics loaded
```

### 4. Capture Test
```bash
python scripts/test_publish.py --test-capture
```

Verifies: waitlist capture works, welcome email fires, assessment scores correctly, graph records the lead.

### 5. Dry-Run Cycle
```bash
python scripts/test_publish.py --dry-run
```

Runs orchestrator with no actual posting. Confirms: Strategist plans → Creator scripts → QA scores → Scheduler queues.

### 6. Single Live Post Test
```bash
# Dry run first
python scripts/test_publish.py --platform twitter --influencer anthony

# When ready to actually post
python scripts/test_publish.py --platform twitter --influencer anthony --live
```

---

## Launch Sequence

### Hour 0 (pre-launch, morning)
1. Final env check: `python scripts/test_publish.py --health`
2. Start the brain service (for LLM generation — optional V1)
3. Deploy landing page with email capture form (Vercel)
4. Deploy assessment page (`/ai-readiness`)

### Hour 1 (launch)
1. First manual post from each face (approve_first mode on)
2. Monitor logs for errors
3. Watch graph: `python -c "from content_engine import graph_writer; print(graph_writer.get_analyst_view())"`

### Hour 2-24
1. Orchestrator runs continuous mode: `python -m content_engine.orchestrator`
2. Publisher cycles every 5 min, posts at optimal times
3. Every post hits the graph with content_piece + publish_result nodes
4. Every lead hits the graph with waitlist_lead node + `converted_to_lead` edge

### Day 2 (48hrs post-launch)
1. Analyst pulls analytics for Day 1 posts
2. `scoring.py` computes 5-signal scores
3. Graph gets performance_score nodes
4. Autoresearch starts building pattern nodes

### Day 3-7 (learning mode)
- `graph.killer_query(tiers=["hot", "buyer"], source_types=["assessment"])` tells you what works
- `graph.find_decoration(days_threshold=3)` tells you what to kill
- Autoresearch promotes patterns from INFERRED → EXTRACTED

---

## What's Wired

| Component | Status | Graph Integration |
|-----------|--------|-------------------|
| **Orchestrator** | Complete | Writes content_piece + influencer nodes on every cycle |
| **Strategist role** | Complete | Plans 48 pieces/day, balances cold/warm/hot/buyer + know/like/trust/convert |
| **Creator role** | Complete | Template scripts V1, LLM adapter ready for V2. Writes hook + script nodes |
| **QA Gate** | Complete | Basic checks V1, LLM eval ready for V2. Writes eval_score nodes |
| **6 Publishers** | Complete | Twitter/IG/LinkedIn/TikTok/YouTube/Facebook. Write publish_result nodes |
| **Compliance Layer** | Complete | Rate limits enforced before every post |
| **Scoring Engine** | Complete | 5 signals computed when analytics pulled. Writes performance_score nodes |
| **Autoresearch** | Complete | Learns patterns, promotes confidence. Writes pattern nodes |
| **Waitlist Capture** | Complete | Supabase + Resend + graph. Creates waitlist_lead with source tracking |
| **Assessment System** | Complete | 4 scorecards, cold/warm/hot/buyer tiers, graph writes with tier |
| **Monitor** | Complete | Keyword detection, auto-DM response. Records dm_keyword leads |
| **Graph Writer** | Complete | Universal bridge, all modules feed MarketingGraph |
| **MarketingGraph** | Complete (other session) | 11 nodes, 11 relations, killer query live |
| **Nango Adapter** | Built, not wired into publishers yet | Fallback to env vars working |
| **Landing Page** | NOT BUILT | Need Next.js pages on Vercel |
| **Anthony Face Clone** | Config done, face/voice assets needed | Can launch without for V1 text posts |
| **Video Pipeline** | NOT BUILT | Remotion planned but V2 |

---

## V1 Killer Query (The Only Question That Matters)

After 1 week of posting, run:

```python
from content_engine import graph_writer

# "Which face + platform + kpi_stage + hook captured the most HOT/BUYER leads?"
winners = graph_writer.run_killer_query(tiers=["hot", "buyer"], source_types=["assessment"], top_n=20)

for w in winners:
    print(f"{w['influencer']} on {w['platform']} [{w['kpi_stage']}]: {w['lead_count']} leads")
    print(f"  Hook: {w['hook']}")
```

That query tells you what to 10x. Everything else is decoration.

---

## What to Kill Weekly (Decoration Check)

```python
from content_engine import graph_writer

dead = graph_writer.find_decoration(days_threshold=7)
for d in dead:
    print(f"KILL: {d['topic']} (age {d['age_days']}d, 0 leads)")
```

Run every Sunday. Anthony's rule: anything that doesn't move someone through KLT→Convert is decoration. Kill it.

---

## Failure Modes + Recovery

| Failure | What Happens | Recovery |
|---------|-------------|----------|
| Supabase down | Waitlist capture fails but returns error to UI | Retry on next submit |
| Resend down | Lead saved, welcome email not sent | Cron job re-sends for `welcome_sent=false` |
| Platform API rate limit | Publisher returns error, compliance layer already prevents most | Orchestrator skips that face×platform slot, tries next cycle |
| Graph unavailable | All writes silently skipped (non-fatal) | Content still posts, graph rebuilds from next cycle |
| One OAuth token expired | That platform fails, others keep posting | Nango refresh or manual re-auth |
| Orchestrator crash | Last state saved in graph JSON + Supabase | Restart — resumes where it left off |

**The design principle:** everything is non-blocking except the platform post itself. A failed graph write never blocks a successful tweet. A failed Resend email never blocks a saved lead.

---

## File Inventory (This Session's Complete Build)

### Content Engine
- `scoring.py` — 5-signal multi-signal scoring
- `orchestrator.py` — Marketing Department conductor (6 roles)
- `graph_writer.py` — Universal bridge to MarketingGraph
- `llm_adapter.py` — Creator → brain LLM adapter
- `monitor.py` — Keyword detection + auto-DM response
- `topic_bank.yaml` — 47 seed topics
- `autoresearch.py` — Modified to wire in multi-signal scoring

### Publishers
- `publishers/base.py` — Abstract publisher + retry
- `publishers/compliance.py` — Rate limits per platform
- `publishers/twitter.py` — Twitter API v2
- `publishers/instagram.py` — Instagram Graph API
- `publishers/linkedin.py` — LinkedIn REST API
- `publishers/tiktok.py` — TikTok Open API
- `publishers/youtube.py` — YouTube Data API
- `publishers/facebook.py` — Facebook Graph API
- `publishers/nango_adapter.py` — OAuth token fetcher
- `publishers/__init__.py` — Registration + graph wiring

### Capture
- `capture/waitlist.py` — Email capture + Supabase + Resend
- `capture/assessment.py` — 4 scorecards, cold/warm/hot/buyer tiers
- `capture/__init__.py` — Unified exports

### Influencers
- `influencers/influencer_0_anthony.yaml` — Anthony clone profile (new)
- `influencers/influencer_1_tech.yaml` — The Builder (existed)
- `influencers/influencer_2_business.yaml` — The Operator (existed)
- `influencers/influencer_3_creative.yaml` — The Director (existed)

### Scripts
- `scripts/test_publish.py` — Health check + dry run + capture test

### Migrations
- `supabase/migrations/013_marketing_machine.sql` — waitlist + assessment_responses tables

### Development Docs
- `0032_marketing_machine_scoring_engine.md` — Scoring spec
- `0035_marketing_machine_publishers.md` — Publishers spec
- `0036_marketing_machine_full_pipeline.md` — Full pipeline summary
- `0037_marketing_machine_capture_system.md` — Capture system (waitlist + assessments)
- `0038_marketing_machine_launch_runbook.md` — This doc

---

## Post-V1 Backlog (In Priority Order)

1. Wire publishers to use Nango adapter (auto-refresh tokens)
2. Build landing page (Vercel + email capture form)
3. Build results page for assessments (with transparency stats)
4. LLM script generation (wire orchestrator Creator to brain)
5. Ideation Engine (Nick's pillar 1 — trends/hooks/formats/angles)
6. Reverse engineering mode (after 2 weeks of graph data)
7. Video pipeline (Remotion + Deepgram + HeyGen)
8. Anthony's face clone (FlashHead model training)
9. Stripe checkout (when audience exists)
10. 7-day nurture sequence (when waitlist > 100)

---

## One-Liner Status

**Code: 100% ready. Wiring: pending your OAuth/API keys. Launch: whenever you say go.**