# 0041 — Marketing Machine: Complete Pipeline (Final Blueprint)
**Date:** 2026-04-16
**Category:** Marketing Machine — Master Build Spec
**Status:** LOCKED — all decisions made, ready for build session execution
**SAR:** Secure, Autonomous, Reliable
**Owner:** Session 0002 (concept) → Build Session (execution)

---

## Overview

This is the FINAL pipeline spec incorporating all decisions made across sessions 0032-0042 + this design session. Every tech choice, cost model, content flow, and platform strategy is locked here.

**DDO turned the Marketing Machine from "we post your content" into "we show you exactly which content made you money and automatically make more of it."**

Generate content → post content → automatically track every click through the entire journey → know EXACTLY which post by which face on which platform drove which lead to which dollar → auto-adjust the next batch based on what actually converted. That's not a scheduling tool. That's a **revenue attribution engine.**

- The content gets better automatically because the data tells it what works.
- Hot leads get routed to sales in <60 seconds. Cold leads get content dripped. No human guessing.
- Every AI company optimizes the MODEL. Cocreatiq optimizes the INTERACTION. The interaction intelligence is proprietary data that compounds over time.

### Core Principles
- **SAR:** Secure, Autonomous, Reliable — every component
- **Click to Client:** Every post feeds the pipeline (Stranger → Client)
- **DDO:** Data-Driven Optimization — system-wide behavioral intelligence, not just analytics
- **Dr. Frankenstein:** Use what exists, build only the gap
- **Client 0:** Anthony is the first user. Test everything on HIS business.
- **Batch first, automate second:** Pre-produce 2 weeks of content, then turn on the machine

---

## Phase 1: Anthony Only (This Week)

### Why Anthony First
- Real accounts with history = low ban risk
- Voice already cloned (Qwen3-TTS on Modal)
- Face/photo assets exist
- One debug surface — fix issues before 4x scaling
- Real engagement from Day 1

### Phase 2-5: AI Faces (Weeks 2-5)
- Week 2: Alex (Tech) — accounts created + 5-7 days manual warmup
- Week 3: Marcus (Business) — same pattern
- Week 4: Sage (Creative) — same pattern
- Week 5: All 4 faces running = 48 pieces/day

---

## The 3-Tool Pipeline

### Tool 1: Figma (Brand System — Anthony designs)
**Job:** Design templates, lock typography, define layout rules

**Outputs:**
- 4 master size templates (1080×1920, 1080×1080, 1080×1350, 1920×1080)
- Typography system: Montage (headlines) + Lemon Tuesday (accents)
- Color palette: Yellow/gold accent + dark backgrounds + white text
- Layout positions: hook text (top), punch text (center), subject (bottom), brand tag, CTA
- Yellow brush accent PNG

### Tool 2: Freepik Spaces (Visual Asset Generation — API automated)
**Job:** Produce raw images at scale from node graph templates

**Inputs:** Face reference + brand colors + scene prompt + topic
**Outputs:** .png/.jpg images (scenes, poses, backgrounds — no text baked in)

**Node graph per face:**
- Face reference node (Anthony's photo locked)
- Brand color node (yellow/gold palette)
- Scene prompt node (dynamic per topic)
- Output: 3-12 scene variations per batch

**Plan:** Premium+ Plus (~$25/mo) — verify unlimited Nano Banana Pro 2K
**API:** REST + MCP server available
**Env var needed:** `FREEPIK_API_KEY`

### Tool 3: Remotion (Video Assembly — Code automated)
**Job:** Assemble finished videos from Freepik images + voice + captions + brand assets

**Inputs:**
- Freepik-generated scene images (background layer)
- Qwen3-TTS voice audio (Anthony's cloned voice)
- Whisper transcription (word-level timestamps for captions)
- Brand assets from Figma/AE (intro, outro, transitions, lower thirds, fonts)

**Components to build:**
| Component | What It Does | Priority |
|-----------|-------------|----------|
| `<VideoPost>` | Base composition — layers all elements | P0 |
| `<Caption>` | Word-by-word highlight sync from Whisper SRT | P0 |
| `<HookText>` | First 3 sec — big punch typography (your "20 YEARS" style) | P0 |
| `<BrandTag>` | Bottom tagline ("Creator Create" / "Cocreatiq") | P0 |
| `<CTAOutro>` | Last 3 sec — DM keyword CTA card | P0 |
| `<BrandIntro>` | Logo reveal from AE export (1.5s) | P1 |
| `<Transition>` | Custom transitions from AE exports | P2 |
| `<MusicBed>` | Background audio with ducking under voice | P1 |
| `<Watermark>` | Small Cocreatiq mark, corner | P2 |
| `<Disclosure>` | "AI generated" label for Meta compliance | P0 |

**Deploy on:** Modal (already using for voice/avatar)
**Render target:** < 90 sec per video, 4 aspect ratios per piece

---

## Content Types → Tool Routing

| Content Type | LLM | Freepik | Remotion | Daily Volume |
|--------------|-----|---------|----------|--------------|
| Text post (Twitter, LinkedIn) | ✅ | ❌ | ❌ | 5 |
| Static image (IG feed, carousel) | ✅ caption | ✅ generates | ❌ | 3 |
| Video (Reel, TikTok, Short, FB) | ✅ script | ✅ scene image | ✅ assembles | 4 |
| **Total** | | | | **12/day** |

---

## LLM Cost Optimization — Tiered Cortex Routing

| Content Type | Model | Cost/1M tokens | Why |
|--------------|-------|----------------|-----|
| TOFU text posts (60%) | Gemini 2.5 Flash | $0.075 in / $0.30 out | Fast, cheap, good enough |
| MOFU posts (30%) | GPT-4o or Haiku 4.5 | $1-2.50 in / $5-10 out | Better persuasion |
| BOFU posts (10%) | Claude Sonnet 4.6 | $3 in / $15 out | Best brand voice |
| Voice scripts | Grok 3 Mini | $0.30 in / $0.50 out | Natural conversational tone |
| Hook A/B generation | Llama 3.1 8B (Groq) | $0.05 in / $0.08 out | Generate 20, pick best |
| QA eval scoring | Haiku 4.5 | $1 in / $5 out | Structured analysis |
| Autoresearch analysis | Claude Sonnet 4.6 | $3 in / $15 out | Deep pattern extraction |

**Blended daily cost: ~$0.16/day = $4.80/month**

---

## Voice Pipeline

| Step | Tool | What It Does |
|------|------|-------------|
| Script writing | Grok 3 Mini | Writes natural conversational voice script |
| Voice synthesis | Qwen3-TTS on Modal | Generates Anthony's cloned voice (0.95+ SECS) |
| Transcription | Whisper on Modal | Word-level timestamps for caption sync |

**Cost:** ~$0.78/day for 4 voice videos

---

## Visual Generation Pipeline

### For Image Posts (Freepik Only)
```
Topic + Face + Brand → Freepik Spaces API → finished image → Publisher
```

### For Video Posts (Freepik + Remotion)
```
Topic + Face + Brand → Freepik Spaces API → scene image (.png)
Script → Grok 3 Mini → voice script
Voice script → Qwen3-TTS Modal → audio (.mp3)
Audio → Whisper Modal → captions (.srt with word timestamps)

All above → Remotion:
  Layer 1: Freepik scene image (background)
  Layer 2: Voice audio track
  Layer 3: Caption overlay (word-by-word sync)
  Layer 4: Hook text (first 3 sec, your Figma typography)
  Layer 5: Brand intro (AE export, 1.5s)
  Layer 6: CTA outro (AE export, last 3 sec)
  Layer 7: Music bed (ducked under voice)
  Layer 8: Watermark + AI disclosure

→ Renders 4 aspect ratios (9:16, 1:1, 4:5, 16:9)
→ Stored in cloud (Supabase Storage / R2)
→ CDN URL returned
→ Publisher posts to platform
```

---

## Brand Asset Library

### From Figma (design specs)
- 4 master size templates
- Typography: Montage + Lemon Tuesday
- Color palette: yellow/gold + dark + white
- Layout positions per size

### From Premiere / After Effects (Anthony exports)
```
/cocreatiq_brand_assets/
├── fonts/
│   ├── Montage-Bold.ttf
│   ├── Montage-Regular.ttf
│   └── LemonTuesday.ttf
├── intros/
│   └── cocreatiq_logo_reveal.mov (1.5s, alpha)
├── outros/
│   ├── cta_dm_operator.mov
│   ├── cta_link_in_bio.mov
│   └── cta_follow_for_more.mov
├── overlays/
│   ├── caption_bold.mov
│   ├── caption_glitch.mov
│   └── caption_typewriter.mov
├── accents/
│   └── yellow_brush_stroke.png (alpha)
├── transitions/
│   └── (Anthony exports as created)
├── color_grades/
│   └── cocreatiq_main.cube
├── audio/
│   ├── music/ (3 mood beds)
│   └── sfx/ (whoosh, ding, glitch)
└── manifest.json (metadata tags per asset)
```

---

## Master Content Sizes (Locked from Figma)

| Name | Dimensions | Aspect | Used For |
|------|-----------|--------|----------|
| Vertical | 1080×1920 | 9:16 | IG Reels, TikTok, YT Shorts, FB Reels, Stories |
| Square | 1080×1080 | 1:1 | IG Feed, LinkedIn, Twitter, FB Feed |
| Portrait | 1080×1350 | 4:5 | IG Feed (preferred — takes most screen space) |
| Landscape | 1920×1080 | 16:9 | YouTube long-form, LinkedIn Video |

**Caption safe zones:**
- Vertical 9:16: keep text between 15% from top and 25% from bottom
- Square 1:1: keep text within 90% center
- Landscape 16:9: keep text within 90% center

---

## Platform Strategy

### Posting Order (by setup complexity)
1. Twitter/X (easiest API, fastest approval)
2. Instagram + Facebook (same Meta app)
3. TikTok (submit audit ASAP — 3-7 day wait)
4. LinkedIn (Anthony only — AI faces banned)
5. YouTube (Phase 2 — pillar content only)

### Daily Schedule Per Platform
| Slot | Time | Funnel | Content |
|------|------|--------|---------|
| Morning | 8-10am ET | TOFU | Value/framework |
| Afternoon | 12-2pm ET | TOFU | Story/case study |
| Evening | 5-7pm ET | MOFU | CTA → DM keyword |

### Platform Limits (Compliance Layer)
| Platform | Posts/Day | DMs/Day | Min Interval | AI Disclosure |
|----------|-----------|---------|--------------|---------------|
| Twitter | 3 | 50 | 2 min | API flag |
| Instagram | 3 | 30 | 10 min | Meta requires label |
| Facebook | 3 | 30 | 10 min | Meta requires label |
| TikTok | 3 | 20 | 20 min | Not required yet |
| LinkedIn | 2 (Anthony only) | 25 | 20 min | Professional standards |

---

## Launch Strategy: Batch First, Then Automate

### Pre-Launch Batch (Before Going Live)
| Content | Volume | Why |
|---------|--------|-----|
| Videos | 30-40 | Feed looks established |
| Static images | 10-15 | Mix variety |
| Text posts | 20-30 | Engagement starters |
| **Total pre-launch** | **60-85 pieces** | **Feed has depth from Day 1** |

### Batch Production Day
```
Morning:   Seed 30 topics → LLM generates 30 scripts → QA scores all
Afternoon: Qwen3-TTS generates 30 voice tracks → Freepik generates 30 images
Evening:   Remotion renders 30 videos × 4 sizes → Queue loaded
Next day:  Anthony reviews → approves → Post 15 immediately (backfill feed)
Then:      Automation kicks in: 3/day per platform
```

### Go-Live Sequence
1. Post 15 videos immediately (backfill feed — looks established)
2. Post 10 images across platforms
3. Turn on 3/day automation
4. Monitor for 24 hours
5. Fix anything that breaks
6. Scale to full daily cadence

---

## Click to Client Wiring

Every post feeds the pipeline:

```
Content posted → Stranger sees it
  → Comments keyword (BUILD / SCALE / BRAND / OPERATOR)
  → Monitor detects keyword (60s polling)
  → Auto-DM: lead magnet + qualifying question
  → Lead captured → Supabase waitlist
  → Resend Day 0 email fires (welcome + lead magnet)
  → 7-day nurture sequence (behavior-triggered)
  → Hot lead (80+) → route to booking page
  → Warm lead (50-79) → continue nurture
  → Cold lead (<50) → content drip
```

---

## Marketing Department (Orchestrator — 6 Roles)

| Role | Job | Tech |
|------|-----|------|
| Strategist | Plans daily mix (topics, funnel stage, CTAs) | orchestrator.py + Topic Bank |
| Creator | Writes content (scripts, posts, captions) | Cortex Router → tiered LLMs |
| QA | Evaluates quality (75%+ score gate, 2x rework) | eval.py |
| Publisher | Schedules + posts via compliance-wrapped APIs | scheduler.py + publishers/ |
| Analyst | Pulls 48hr post-publish analytics, scores | scoring.py + autoresearch.py |
| Scout | Watches competitors + trends | Future — manual for now |

---

## Monthly Cost Model (Anthony Only — Phase 1)

| Component | Monthly |
|-----------|---------|
| LLM (tiered Cortex Routing) | $5 |
| Voice scripts (Grok 3 Mini) | $1 |
| Voice synthesis (Qwen3-TTS Modal) | $19 |
| Freepik Premium+ Plus | $25 |
| Remotion render (Modal) | $8 |
| Captions (Whisper Modal) | $2 |
| Storage + CDN | $1 |
| Nango Cloud | Free |
| Resend (email) | Free tier |
| **Total Phase 1** | **~$61/month** |

### Phase 2 (All 4 Faces)
~$61 × 2.5 (voice/render scale, LLM is cheap) = **~$150/month for 48 pieces/day**

---

## Environment Variables Needed

```bash
# Already in .env
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
XAI_API_KEY=...
ELEVENLABS_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
RESEND_API_KEY=...
NANGO_BASE_URL=https://api.nango.dev
NANGO_SECRET_KEY=4388fe4e-...

# Need to add
FREEPIK_API_KEY=PASTE_FREEPIK_API_KEY_HERE
```

---

## Files the Build Session Creates

```
content_engine/
├── video/                         ← NEW
│   ├── __init__.py
│   ├── freepik_adapter.py         ← Freepik Spaces API wrapper
│   ├── remotion_render.py         ← Triggers Remotion renders on Modal
│   ├── whisper_caption.py         ← Whisper transcription → SRT
│   └── video_router.py            ← Routes: text-only / image / video
├── influencers/
│   └── influencer_0_anthony.yaml  ← NEW — Anthony's clone profile
└── topic_bank.py                  ← NEW — seed + manage topics

remotion/                          ← NEW — Remotion project
├── package.json
├── src/
│   ├── VideoPost.tsx              ← Base composition
│   ├── Caption.tsx                ← Word-sync captions
│   ├── HookText.tsx               ← Punch typography
│   ├── BrandTag.tsx               ← Bottom tagline
│   ├── CTAOutro.tsx               ← DM keyword CTA
│   ├── BrandIntro.tsx             ← Logo reveal
│   ├── MusicBed.tsx               ← Audio with ducking
│   ├── Disclosure.tsx             ← AI label
│   └── compositions/
│       ├── Vertical.tsx           ← 1080×1920
│       ├── Square.tsx             ← 1080×1080
│       ├── Portrait.tsx           ← 1080×1350
│       └── Landscape.tsx          ← 1920×1080
├── public/
│   └── fonts/                     ← Montage + Lemon Tuesday
└── remotion.config.ts

cocreatiq_brand_assets/            ← NEW — Anthony fills this
├── fonts/
├── intros/
├── outros/
├── overlays/
├── accents/
├── transitions/
├── color_grades/
├── audio/
└── manifest.json
```

---

## Files the Build Session Must NOT Touch

```
brain/*
mind/*
self_mode/*
hands/cursor_telemetry.py
operators/configs/qa.yaml
persona/qa_core.md
development/0025-0040 (read only — strategy docs)
content_engine/eval.py
content_engine/scoring.py
content_engine/autoresearch.py
content_engine/pipeline/*
content_engine/analytics/*
content_engine/influencers/influencer_1-3.yaml
content_engine/influencers/loader.py
```

---

## Definition of Done

The Marketing Machine is "live" when:

1. ✅ 30+ videos rendered and queued (pre-launch batch)
2. ✅ 15+ videos posted to backfill feed
3. ✅ 3/day automation running on Twitter + IG + FB + TikTok
4. ✅ Comment keyword monitor detecting "OPERATOR"
5. ✅ Auto-DM responder sending lead magnet
6. ✅ Landing page capturing email
7. ✅ Resend Day 0 nurture email firing
8. ✅ Full loop runs 24 hours with zero human touch
9. ✅ Zero platform warnings or bans
10. ✅ Anthony can see what happened (dashboard or report)

---

## Coined Terms
- **SAR** — Secure, Autonomous, Reliable. The three non-negotiable pillars every Cocreatiq component must satisfy. Secure = credential isolation, secret scanning, injection protection, multi-tenant separation. Autonomous = runs 24hrs with zero human touch. Reliable = retry, checkpoint, rollback, heartbeat, ACK/NACK on every handoff. If it's not SAR, it doesn't ship.
- **Marketing Machine** — complete autonomous Click to Client revenue engine
- **Content Army** — 4 faces × 4 platforms × 3/day = 48 pieces/day (Phase 2)
- **Marketing Department** — 6-role orchestrator (Strategist → Creator → QA → Publisher → Analyst → Scout)
- **Batch First** — pre-produce 2 weeks, then automate daily generation
- **3-Tool Pipeline** — Figma (design) → Freepik (generate) → Remotion (assemble)
- **Tiered Cortex** — route LLM calls by stakes (Flash for volume, Sonnet for sales)
- **Proof of Work** — "Other AI says 'I did it.' Ours shows the tape." Every operator in Self Mode produces a full screen recording with cursor tracking and step annotations. Verifiable proof, not just a text summary.

---

## Key References

| Doc | What It Covers |
|-----|---------------|
| 0029 | Click to Client framework (11 stages) |
| 0030 | Marketing Machine product concept + pricing |
| 0031 | 6 data intelligence pipelines |
| 0032 | Multi-signal scoring engine (5 signals) |
| 0033 | AI Influencer System (4 faces, compliance, CTAs) |
| 0034 | Click to Client technical wiring (publishers, monitor, email, Stripe) |
| 0035 | Platform publishers spec (6 platforms, Postiz harvest) |
| 0036 | Full pipeline build (15 new files, 6-role orchestrator) |
| 0037 | Capture system |
| 0038 | Launch runbook |
| 0039 | AI influencer setup SOP |
| 0040 | Nango social media OAuth setup |
| **0041** | **THIS DOC — complete pipeline, all decisions locked** |