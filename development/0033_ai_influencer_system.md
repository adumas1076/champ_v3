# 0033 — AI Influencer System: Autonomous Content Army
**Date:** 2026-04-12
**Category:** Marketing Machine — Core Revenue Engine
**Status:** V1 — Concept locked, ready for build session
**Deadline:** Wednesday 2026-04-15 — production-ready, posting live
**SAR:** Secure, Autonomous, Reliable — every component
**Owner:** Marketing Machine Session 0002 (concept) → Build Session (execution)

---

## What This Is

An autonomous AI influencer system that runs 24/7 without human intervention. 3 AI influencers + Anthony's AI clone = 4 faces posting 3x/day across 4 platforms (YouTube excluded from MVP), feeding the Click to Client pipeline. Every post is a pipeline stage. Every CTA drives toward capture. Every interaction triggers the next step.

**The pitch to businesses:** "We scale your outreach while you work ON your company instead of IN your company."

**For Anthony (Client 0):** His AI clone posts on self-mode. He drops in to post for real only when he WANTS to. The system never stops.

### Launch Sequence
1. **Wednesday (04/15):** ALL 4 faces live → 3 posts/day × 4 platforms × 4 faces = **48 pieces/day** — tracking everything from day one
2. **Week 2+:** YouTube pillar content → 1→64 repurposing pipeline kicks in
3. **Ongoing:** Autoresearch loop scores, learns, improves every cycle

Ship all 4. Track all 4. Learn from day one.

---

## The 4 Faces

### Face 0: Anthony's AI Clone (PRIMARY)
- **Role:** The real founder. Main brand. Cocreatiq's face.
- **Face source:** Anthony's 2-min reference video (already in avatar pipeline)
- **Voice source:** Anthony's voice clone via Qwen3-TTS (ClipCannon centroid, already built)
- **Mode:** Self-mode autonomous + Anthony can override with real posts anytime
- **Niche overlap:** ALL — he's the umbrella brand, the others are verticals
- **CTA pattern:** "DM me 'operator' to get your free AI readiness audit"
- **Platform priority:** Twitter (hot takes), LinkedIn (B2B), Instagram (reels), TikTok (shorts) — YouTube Week 3+ (pillar only)
- **Posting cadence:** 3x/day on each platform (12 posts/day total)

### Face 1: Tech Influencer — "The Builder"
- **Role:** Shows what's possible with AI. Demos, builds, tutorials.
- **Face source:** AI-generated face (Freepik AI / Midjourney / Flux) — person who doesn't exist
- **Voice source:** ElevenLabs voice clone OR Qwen3-TTS voice design (no real person needed)
- **Name/handle:** TBD by Anthony (e.g., "Alex Volta", "@buildwithalex")
- **One Thing:** Building AI-powered tools and showing the process
- **Content pillars:** AI tool builds, tech stack breakdowns, behind-the-scenes shipping, AI news + opinion
- **CTA pattern:** "Comment 'BUILD' and I'll send you the stack breakdown"
- **Platform priority:** Twitter (primary), LinkedIn, TikTok, Instagram — YouTube Week 3+
- **Posting cadence:** 3x/day on each platform (12 posts/day total)
- **Full profile:** `content_engine/influencers/influencer_1_tech.yaml`

### Face 2: Business Influencer — "The Operator"
- **Role:** Shows how to scale. Frameworks, results, case studies.
- **Face source:** AI-generated face — person who doesn't exist
- **Voice source:** ElevenLabs / Qwen3-TTS voice design
- **Name/handle:** TBD by Anthony (e.g., "Marcus Cole", "@scalewithmarcus")
- **One Thing:** Business systems that actually scale
- **Content pillars:** Sales frameworks (CLOSER), retention, scaling diagnostics, hiring
- **CTA pattern:** "DM 'SCALE' for the free business diagnostic"
- **Platform priority:** LinkedIn (primary), Twitter, TikTok, Instagram — YouTube Week 3+
- **Posting cadence:** 3x/day on each platform (12 posts/day total)
- **Full profile:** `content_engine/influencers/influencer_2_business.yaml`

### Face 3: Creative Influencer — "The Director"
- **Role:** Makes brands that convert. Design, content, visual storytelling.
- **Face source:** AI-generated face — person who doesn't exist
- **Voice source:** ElevenLabs / Qwen3-TTS voice design
- **Name/handle:** TBD by Anthony (e.g., "Sage Moreno", "@sagebuildsbrands")
- **One Thing:** Making brands that convert — the creative process
- **Content pillars:** Brand building, content creation process, agency ops, AI + creative tools
- **CTA pattern:** "Comment 'BRAND' for the free brand audit template"
- **Platform priority:** Instagram (primary), TikTok, Twitter, LinkedIn — YouTube Week 3+
- **Posting cadence:** 3x/day on each platform (12 posts/day total)
- **Full profile:** `content_engine/influencers/influencer_3_creative.yaml`

---

## Posting Cadence — 3x/Day Everywhere (Except YouTube)

### Daily Schedule Per Face Per Platform

| Time Slot | Content Type | Funnel Stage |
|-----------|-------------|--------------|
| **Morning (8-10am)** | Value post — framework, tip, breakdown | TOFU (attract) |
| **Afternoon (12-2pm)** | Engagement post — story, case study, opinion | TOFU (attract) |
| **Evening (5-7pm)** | CTA post — DM trigger, link in bio, lead magnet | MOFU (engage) |

**Daily funnel mix: 2 TOFU + 1 MOFU. BOFU sprinkled 1-2x/week (too early to hard sell with no audience).**

### Volume Math

| Phase | Faces Active | Posts/Day | Platforms |
|-------|-------------|-----------|-----------|
| **Wednesday launch** | All 4 faces | **48** | Twitter, LinkedIn, IG, TikTok |
| Week 2+ | All 4 + YouTube | 48 + pillar→64 repurpose | All 5 |

### YouTube Strategy (Week 3+ Only)
YouTube is excluded from the 3x/day cadence. YouTube rewards quality over quantity. When we go YouTube:
- 1-2 pillar videos/week (8-45 min, high production)
- Each pillar feeds the repurpose pipeline → 64+ micro/micro-micro pieces
- Shorts auto-generated from pillar clips (not standalone)
- This is the volume multiplier, not the starting point

---

## Content Tiers (Ship ALL — layered)

### Tier 1: Text Posts (Day 1 — Sunday/Monday)
**Platforms:** Twitter, LinkedIn, Instagram captions, TikTok captions
**Volume:** 3x/day per face per platform — highest volume, lowest failure rate, zero rendering pipeline
**What ships:**
- Twitter threads + single tweets (hot takes, frameworks, build updates)
- LinkedIn posts + articles (professional framing, case studies)
- Instagram captions (paired with static images / carousels)
- TikTok captions (paired with stock/generated visuals)

**SAR compliance:**
- Secure: OAuth tokens via Nango, no plaintext credentials
- Autonomous: Content Engine generates → eval.py quality gate → scheduler posts → autoresearch scores → loop
- Reliable: Queue-based with retry, platform rate limit awareness, no account bans

### Tier 2: Voice + Visuals (Day 2 — Monday/Tuesday)
**Platforms:** YouTube Shorts, podcast clips, Instagram Reels audio
**What ships:**
- AI voice narration over B-roll / screen recordings / stock footage
- Podcast-style commentary clips (voice only, waveform visual)
- Voice-over carousel walkthroughs

**Tech:**
- Qwen3-TTS on Modal (already deployed) for Anthony's clone voice
- ElevenLabs API OR Qwen3-TTS voice design for AI influencer voices
- FFmpeg compositing: voice + visual track → MP4

### Tier 3: Talking Head Video (Day 2-3 — Tuesday/Wednesday)
**Platforms:** YouTube (pillar + shorts), Instagram Reels, TikTok, LinkedIn video
**What ships:**
- AI-generated talking head videos (single reference image + audio → video)
- Short-form (15s, 30s, 60s) for reels/shorts/TikTok
- Mid-form (2-5 min) for YouTube + LinkedIn

**Tech (two options — build session picks best):**

**Option A: InfiniteTalk (NEW — evaluate first)**
- Wan2.1-I2V-14B base model
- Single image + audio → talking head video
- Supports unlimited length via streaming mode
- Batch generation via JSON config
- Multi-GPU inference
- Repo: `github.com/MeiGen-AI/InfiniteTalk`
- Deploy on: Modal A100-40GB or Hetzner GPU
- Quality: Good lip sync, some color drift after 1 min (acceptable for short-form)

**Option B: FlashHead (EXISTING — already built)**
- Already in `champ_v3/avatar/renderer.py`
- 28 frames/chunk, 3.8x realtime on RTX 4090
- Built for LIVE calls — needs adaptation for batch/pre-recorded content
- Requires: strip WebRTC, add file output, batch queue

**Option C: Both** (recommended)
- InfiniteTalk for batch content generation (shorts, reels — it's designed for this)
- FlashHead stays for live operator calls (it's already optimized for that)
- Same voice pipeline feeds both

### Tier 4: Full Production Pillar Content (Week 2+)
**Platforms:** YouTube long-form (8-45 min)
**What ships:**
- Full pillar videos → Gary Vee reverse pyramid → 64+ pieces
- Requires: B-roll library, screen recordings, multi-segment editing
- NOT in Wednesday MVP — but the repurpose pipeline (`repurpose.py`) is ready to cut pillar → micro → micro-micro when pillar content exists

---

## Click to Client Wiring — Every Touchpoint Is a Pipeline Stage

### The Flow
```
STRANGER sees content (any platform, any influencer)
  → CLICKS (profile link, comment CTA, DM trigger)
  → LANDS on page (one landing page per product)
  → CAPTURES email (lead magnet: free AI readiness audit / content audit / brand audit)
  → NURTURE fires (7-day behavior-triggered email sequence)
  → CONVERTS (self-serve Stripe checkout OR books demo call)
  → CLIENT (onboarding sequence triggers)
```

### Social Media CTA System

Every post ends with ONE of these patterns (rotated by funnel stage):

**TOFU (50% of content) — Attract:**
- "Comment '[KEYWORD]' and I'll send you [specific thing]"
- "Follow for more [niche] breakdowns"
- "Save this for later"
- Bio link → landing page

**MOFU (30% of content) — Engage:**
- "DM me '[KEYWORD]' to get [lead magnet]"
- "Link in bio for the free [audit/template/framework]"
- "Join 2,000+ [niche] operators — link in bio"

**BOFU (20% of content) — Convert:**
- "DM me 'operator' to see how this works for your business"
- "Book your free strategy call — link in bio"
- "Start free → [product link]"

### Comment-to-Client Workflow
```
User comments "[KEYWORD]" on any post
  → Operator detects keyword via platform API polling
  → Auto-DM sends: "Hey [name]! Here's [promised thing]. Quick question — what's your biggest challenge with [niche topic]?"
  → Response triggers lead scoring (BANT + Priestley)
  → Score 80+ → route to Sales Operator (hot lead)
  → Score 50-79 → add to nurture sequence (warm)
  → Score <50 → add to content drip (cold, no pressure)
```

### DM-to-Client Workflow
```
User DMs "[KEYWORD]" (e.g., "operator", "scale", "build", "brand")
  → Operator responds with lead magnet + qualifying question
  → Conversation scored in real-time
  → Hot → "Let me book you a 15-min strategy call. When works?"
  → Warm → "I'll add you to our weekly insights. Check your email."
  → Cold → "Here's some content that'll help: [links]"
```

### Platform Compliance Layer (NO ACCOUNT BANS)

**Rules hardcoded into every publisher:**
- Rate limits per platform (Twitter: 300 tweets/day, IG: 25 posts/day, TikTok: no official limit but 3-5/day safe, LinkedIn: 20 posts/day)
- No duplicate content across platforms (repurpose.py already reformats per platform)
- No spam patterns (varied CTAs, no identical DM blasts)
- All accounts marked as "automated" where required (Meta, X)
- No follow/unfollow automation (ban risk)
- No purchased engagement
- Captions always include proper disclosures where required
- DM automation respects platform ToS — respond to inbound only, never cold-DM
- Content passes eval.py quality gate BEFORE posting (no low-quality spam)
- Human override: Anthony can pause any influencer instantly via dashboard

**Platform-specific compliance (MVP — 4 platforms, 3 posts/day each):**
| Platform | Our limit | Safe max | DM rules | Automation disclosure | Ban triggers to avoid |
|----------|-----------|----------|----------|----------------------|----------------------|
| Twitter/X | 3/day | 15-20 | Respond only, no cold DM | Label as automated if using API | Mass follow/unfollow, duplicate tweets |
| Instagram | 3/day | 5-8 | Respond only | Meta requires disclosure | Rapid actions, engagement pods |
| TikTok | 3/day | 3-5 | Respond only | Not required yet | Reposted content, engagement bait |
| LinkedIn | 3/day | 2-3 | InMail only with connection | Professional standards | Automation without disclosure |

**Note:** LinkedIn safe max is 2-3, so 3/day is on the edge. Build session should implement 2/day for LinkedIn with 1 bonus slot only if engagement is high. YouTube and Facebook added in Phase 3.

---

## Tech Stack — What Exists vs What to Build

### EXISTS (Dr. Frankenstein inventory — DO NOT REBUILD)

| Component | File | Status |
|-----------|------|--------|
| Content evaluation (pre-publish) | `content_engine/eval.py` | Working |
| Multi-signal scoring (post-publish) | `content_engine/scoring.py` | Working (0032) |
| Autoresearch loop | `content_engine/autoresearch.py` | Working |
| 1→64 repurposing pipeline | `content_engine/pipeline/repurpose.py` | Working |
| Platform formatting (16 formats) | `content_engine/pipeline/platforms.py` | Working |
| Content scheduler + queue | `content_engine/pipeline/scheduler.py` | Working |
| Funnel tracker (TOF/MOF/BOF) | `content_engine/pipeline/funnel.py` | Working |
| Influencer profiles (3 YAML) | `content_engine/influencers/*.yaml` | Working |
| Influencer loader | `content_engine/influencers/loader.py` | Working |
| 6 analytics adapters | `content_engine/analytics/*.py` | Working (need OAuth) |
| Voice cloner (Qwen3-TTS) | `avatar/voice/voice_cloner.py` | Working (Modal) |
| Voice engine (dual router) | `avatar/voice/voice_engine.py` | Working |
| FlashHead renderer | `avatar/renderer.py` | Working (live mode) |
| Avatar registry | `avatar/training/avatar_registry.py` | Working |
| Marketing Operator config | `operators/configs/marketing.yaml` | Complete |
| Lead Gen Operator config | `operators/configs/lead_gen.yaml` | Complete |

### BUILD (Wednesday deadline — build session scope)

| # | Component | Priority | Est. Effort | Depends On |
|---|-----------|----------|-------------|------------|
| 1 | **AI face generation** — generate 3 synthetic faces (Freepik/Flux/Midjourney) | P0 | 2 hrs | Nothing — manual + API |
| 2 | **AI voice creation** — 3 unique voices via ElevenLabs or Qwen3-TTS voice design | P0 | 2 hrs | Face identities chosen |
| 3 | **InfiniteTalk deployment** — clone repo, deploy on Modal/Hetzner, batch API | P0 | 4 hrs | Faces + voices ready |
| 4 | **Platform publishers** — actual API posting (Twitter, LinkedIn, IG, TikTok, YT) | P0 | 6 hrs | OAuth via Nango |
| 5 | **Comment/DM keyword monitor** — poll platform APIs for trigger keywords | P0 | 4 hrs | Publishers working |
| 6 | **Auto-DM responder** — send lead magnet + qualifying question on keyword trigger | P0 | 3 hrs | Monitor working |
| 7 | **Landing page** — Vercel, headline + proof + demo video + CTA + email capture | P0 | 3 hrs | Nothing |
| 8 | **Email capture + nurture** — Resend, 7-day sequence, behavior triggers | P0 | 4 hrs | Landing page |
| 9 | **Lead scoring engine** — BANT + Priestley, auto-route hot/warm/cold | P1 | 3 hrs | Email capture |
| 10 | **Stripe checkout** — webhook, subscription management, confirmation flow | P1 | 3 hrs | Landing page |
| 11 | **Orchestrator** — ties content engine → publisher → monitor → DM → nurture → convert | P0 | 4 hrs | All above |
| 12 | **Dashboard** — real-time view of all 4 influencers, pipeline, conversions | P2 | 4 hrs | Orchestrator |
| 13 | **Anthony's clone YAML** — Face 0 profile matching influencer format | P0 | 1 hr | Nothing |
| 14 | **Platform compliance layer** — rate limits, disclosure, ban prevention | P0 | 2 hrs | Publishers |
| 15 | **Content generation prompts** — brand-voice-aware generation per influencer per platform | P0 | 3 hrs | Profiles complete |

**Total estimated: ~48 hrs of work. With parallel build sessions: 2-3 days.**

---

## Content Generation Pipeline (End to End)

```
1. GENERATE
   Content Engine receives: influencer_id + platform + funnel_stage + topic
   → Loads brand voice from YAML
   → Loads learned rules from autoresearch (Letta knowledge block)
   → Generates content (text, script, or full outline)
   → Applies platform formatting (platforms.py)

2. EVALUATE
   eval.py runs quality gate:
   → Lamar retention criteria (10 checks)
   → Lamar growth criteria (5 checks)
   → Lamar 7 mistakes (anti-pattern scan)
   → Gary Vee distribution check
   → Score must be 75%+ to proceed (90%+ = excellent)
   → Below 75% → regenerate with specific feedback

3. PRODUCE
   Based on content tier:
   → Text: ready to post
   → Voice: Qwen3-TTS / ElevenLabs generates audio → FFmpeg composites with visuals
   → Video: InfiniteTalk generates talking head from reference image + audio
   → All get captions (always-on for TikTok/IG/Reels)

4. SCHEDULE
   scheduler.py queues content:
   → Checks platform optimal posting time (platforms.py)
   → Checks daily rate limits (compliance layer)
   → Checks funnel balance (funnel.py — 50/30/20 TOF/MOF/BOF)
   → Queues with calculated post time

5. PUBLISH
   Publisher sends to platform API:
   → Retries on failure (3 attempts, exponential backoff)
   → Logs success/failure
   → Records UTM parameters for attribution

6. MONITOR
   48 hours after publish:
   → Pull analytics from platform API
   → Score with multi-signal engine (scoring.py — 5 signals)
   → Compare to 3 benchmarks (personal, niche, top 10%)
   → Extract lesson + pattern tags
   → Feed back to autoresearch loop

7. LEARN
   Autoresearch loop:
   → Correlate eval criteria with real performance
   → Generate updated rules
   → Store in Letta knowledge block
   → Next generation cycle uses updated rules
   → LOOP
```

---

## MVP Wednesday Checklist

### Must ship by Wednesday 2026-04-15 (ALL 4 faces, 4 platforms, 3x/day, 48 pieces/day):

- [ ] 3 AI faces generated and stored (Freepik/Flux/Midjourney)
- [ ] 3 AI voices created and tested (ElevenLabs / Qwen3-TTS voice design)
- [ ] Anthony's clone profile (Face 0) created — YAML + voice + reference image
- [ ] Content generation working for ALL 4 faces
- [ ] Content generation prompts per platform (Twitter, LinkedIn, IG, TikTok)
- [ ] Platform publishers posting to Twitter + LinkedIn + Instagram + TikTok
- [ ] 3x/day schedule running for ALL 4 faces: morning (TOFU) + afternoon (TOFU) + evening (MOFU)
- [ ] Platform compliance layer active (rate limits, disclosure, no ban risk)
- [ ] Comment keyword monitor running on all 4 platforms
- [ ] Auto-DM responder working (keyword → lead magnet + qualifying question)
- [ ] Landing page live on Vercel (headline + proof + CTA + email capture)
- [ ] Email capture working (Resend)
- [ ] 7-day nurture sequence loaded and triggering
- [ ] Orchestrator running the full loop autonomously
- [ ] Content flowing: generate → evaluate → schedule → post → monitor
- [ ] Analytics tracking from day one (every post, every platform, every face)
- [ ] Anthony can see what's happening (minimum: terminal dashboard or web UI)
- [ ] System runs 24 hours with zero human intervention
- [ ] 48 pieces/day hitting 4 platforms from 4 faces

### Ship Week 2+ (YouTube + video + payments):
- [ ] YouTube pillar content strategy (1-2 videos/week)
- [ ] InfiniteTalk or FlashHead batch video pipeline
- [ ] Pillar → 64-piece repurposing pipeline live
- [ ] Stripe checkout + subscription management
- [ ] Full lead scoring engine (BANT + Priestley)
- [ ] Competitive benchmarking pipeline
- [ ] Ad creative testing (70/20/10)
- [ ] Full analytics dashboard

---

## DDO Integration (from 0042)

**DDO turned the Marketing Machine from "we post your content" into "we show you exactly which content made you money and automatically make more of it."**

Every post by every face on every platform is tracked through the FULL conversion journey:
- Content → click → page visit (Clarity heatmap + GA4 + FB Pixel) → lead capture → email nurture → Stripe conversion
- Attribution graph connects every node — trace any dollar back to the exact post that started it
- Autoresearch loop reads DDO patterns → auto-adjusts next content batch
- Hot leads routed to sales in <60 seconds. Cold leads get content dripped. No human guessing.
- The content gets better automatically because the data tells it what works.

**8 Supabase DDO tables LIVE:** content_posts, content_performance, page_visits, leads, email_events, conversions, attribution_graph, ddo_optimizations

---

## Revenue Model (from 0030, updated with DDO tiers)

| Tier | Price | What They Get |
|------|-------|---------------|
| Creator | $29/mo | 1 AI influencer, 2 platforms, basic analytics, email capture |
| Pro | $97/mo | 3 AI influencers, 5 platforms, **full DDO attribution + auto-optimization**, nurture sequences, lead scoring |
| Agency | $299/mo | Unlimited influencers, white-label, **cross-client DDO intelligence**, client dashboards, API access |
| OS Integration | Included | Full Marketing Machine + DDO powers Cocreatiq OS operators |

---

## Key References

| Doc | What It Provides |
|-----|-----------------|
| `0029_click_to_client_framework.md` | Full 11-stage pipeline, funnel logic, operator ownership |
| `0030_marketing_machine_product.md` | Product tiers, data sources, competitive landscape |
| `0031_marketing_matrix_data_intelligence.md` | 6 intelligence pipelines, scraping methods |
| `0032_marketing_machine_scoring_engine.md` | 5-signal scoring, benchmarks, autoresearch wiring |
| `influencer_1_tech.yaml` | Tech influencer full profile |
| `influencer_2_business.yaml` | Business influencer full profile |
| `influencer_3_creative.yaml` | Creative influencer full profile |
| InfiniteTalk repo | `github.com/MeiGen-AI/InfiniteTalk` — Wan2.1 talking head generation |

---

## Coined Terms
- **AI Influencer System** — autonomous AI-generated content creators that run 24/7
- **4 Faces** — Anthony's clone + 3 AI influencers covering tech, business, creative
- **Comment-to-Client** — keyword comment → auto-DM → lead capture → nurture → convert
- **Self-Mode Clone** — Anthony's AI running autonomously, real Anthony drops in when he wants
- **Content Army** — 48 pieces/day from day one (4 faces × 4 platforms × 3/day), Week 2+ adds YouTube pillar→64 repurpose
- **Platform Compliance Layer** — rate limits, disclosure rules, ban prevention baked into every publisher
