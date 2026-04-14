# 0039 — AI Influencer Setup SOP
**Date:** 2026-04-14
**Owner:** Anthony (Client 0) executes — automation kicks in after
**Status:** Ready to execute. All platform rules verified with cited 2026 sources.
**Dependencies:** Verified platform matrix (0036, 0038); influencer YAML profiles (0, 1, 2, 3)

---

## Purpose

Step-by-step runbook for creating the 3 AI influencer identities (Alex, Marcus, Sage) across their assigned platforms. Each identity is ONE person with accounts on multiple platforms — exactly how a real human operates online.

All steps grounded in verified 2026 sources. Nothing speculative.

---

## Pre-Flight Checklist (Gather Before Starting)

Required before any account creation:

- [ ] **1 Gmail account** you control (for aliases OR as recovery)
- [ ] **3 unique phone numbers** — Google Voice numbers work ($0/mo for personal use, ~$10 one-time for Google Voice business line; or real SIMs if you prefer)
- [ ] **Freepik or Midjourney or Flux subscription** (face generation — ~$10/mo)
- [ ] **ElevenLabs account** (voice cloning — $5/mo starter, $22/mo scale)
- [ ] **Meta Business Manager** (already exists — your personal BM)
- [ ] **Different devices / browsers available** — laptop + phone minimum, ideally a second browser (Firefox or Edge) for fingerprint variation

---

## Persona Template (Fill This For Each AI Influencer)

Before creating any account, complete this for Alex, Marcus, and Sage:

```yaml
influencer_id:         # alex_volta / marcus_cole / sage_moreno (or your picks)
display_name:          # "Alex Volta" — first + last, human-sounding
handle_base:           # "alexvolta" or "alex.volta" — what you'll try on each platform
email:                 # anthony+alex@yourgmail.com (alias) OR alex.volta@somedomain.com
phone:                 # Google Voice number
date_of_birth:         # Pick a plausible 28-38 year old
location:              # City (helps contextualize bio)
face_reference:        # Which AI model generated the face (Flux/Midjourney/HeyGen)
voice_id:              # ElevenLabs voice_id once cloned
bio_tagline:           # ONE sentence — includes AI disclosure
```

**Example — Alex Volta:**
```yaml
influencer_id: alex_volta
display_name: Alex Volta
handle_base: alexvolta  (fall back to alex.volta or alexvoltaai)
email: anthony+alex@[your-gmail].com
phone: (google voice #1)
date_of_birth: 1994-03-15
location: Austin, TX
face_reference: flux-pro-face-001.jpg
voice_id: (pending ElevenLabs clone)
bio_tagline: "🤖 AI-generated creator • Building in public • Powered by Cocreatiq"
```

---

## Phase 1 — Generate the Persona Assets (Day 0, 1 hour per influencer)

### 1.1 Generate the Face (~15 min)

**Tool:** Freepik Flux (or Midjourney)

**Prompt template for consistent character:**
```
Professional headshot portrait of a [28-35 year old] [gender] [ethnicity/look],
[hair/style], [glasses/no glasses], confident expression, soft natural lighting,
neutral background, photographed with 85mm lens, shallow depth of field,
high detail, --ar 1:1 --seed [fixed number for consistency]
```

**Requirements:**
- **Use a fixed seed** so the SAME face can be regenerated later for video/other content
- Generate 5-10 variations (different expressions/outfits) using the same seed — you need these for profile pics, story posts, variety
- Save to `content_engine/influencers/assets/[influencer_id]/photos/`
- Record the seed number in the YAML profile

**Sources:**
- [ScaleLab 2026](https://scalelab.com/en/why-youtube-is-cracking-down-on-ai-generated-content-in-2026) — disclose AI content, doesn't ban for faces

### 1.2 Clone the Voice (~15 min)

**Tool:** ElevenLabs

**Options:**
- **Instant Voice Clone** ($5/mo Starter) — upload 1 min of sample audio (can be synthetic/royalty-free voice, public domain speech, or actor read)
- **Voice Design** — generate a completely synthetic voice from text description (no sample needed)

For AI influencers, **Voice Design is safer** (no risk of cloning a real person's voice accidentally). Design parameters:
- Gender, age, accent, tone (matches the face)

Save the `voice_id` and update the YAML profile.

### 1.3 Write the Persona Brief (~10 min)

Refer to `content_engine/influencers/influencer_1_tech.yaml` (or 2/3) — already has brand voice, pillars, platforms, one_thing.

Only thing to fill in per persona: the specific **bio tagline** that includes AI disclosure. Examples:

- **Alex (Tech):** "🤖 AI creator teaching the stack • Building live with Cocreatiq • Get the stack breakdown → DM 'BUILD'"
- **Marcus (Business):** "🤖 AI business strategist • Frameworks that scale • Free diagnostic → DM 'SCALE'"
- **Sage (Creative):** "🤖 AI creative director • Brands that convert • Brand audit → DM 'BRAND'"

The 🤖 emoji + "AI" in bio = passive disclosure, runs everywhere.

### 1.4 Sanity Check the Persona

Before account creation, answer these:
- [ ] Is the face consistent across 5+ variations?
- [ ] Does the bio include AI disclosure?
- [ ] Does the persona have a clear "one thing" (from their YAML)?
- [ ] Do you have 3-5 starter post ideas for Day 1 (not mass-produced-feeling)?

---

## Phase 2 — Account Creation (Day 1-3, spread across contexts)

### Platform Order (Sequence Matters)

Start with the platforms that have the loosest new-account rules and best tolerance for multi-account creators:

**Day 1 — Twitter + Instagram**
**Day 2 — TikTok + Facebook**
**Day 3 — YouTube** (Google accounts — slower to warm up)

Skip LinkedIn entirely for AI personas. See 0038 runbook for why.

### Fingerprint Isolation Rules (THE ONLY RULE THAT MATTERS)

Cited source: [Geelark 2026](https://www.geelark.com/blog/can-i-have-multiple-instagram-accounts/) — platforms track User Agent, WebGL, AudioContext, WebRTC, Canvas fingerprinting.

**Minimum acceptable isolation:**
- Chrome for Alex, Firefox for Marcus, Safari (or Edge) for Sage
- Incognito/private mode alone is NOT enough — use different browsers
- Alternate between home wifi and cellular (phone hotspot) to vary IP
- Don't create more than 1 new account per platform per hour from the same context

**Stronger isolation (recommended for scale):**
- Use a multi-account browser like GeeLark, Multilogin, or AdsPower ($20-80/mo) — these create separate browser fingerprints per "profile"
- Each influencer gets their own profile = effectively their own virtual machine
- Makes running 3+ AI personas trivially safe from fingerprint detection

### 2.1 Twitter/X Signup

**Source:** [Social Rails 2026 Twitter Guide](https://socialrails.com/blog/how-to-create-multiple-twitter-accounts) — 10 accounts per person officially allowed

**Steps:**
1. Open browser X (Alex = Chrome, Marcus = Firefox, Sage = Safari)
2. Go to x.com → Sign up
3. Use Alex's email (`anthony+alex@gmail.com`) + Alex's phone
4. Pick handle (`@alexvolta`, fall back to `@alex.volta`, `@alexvoltaai`)
5. Verify email + phone
6. **Set profile pic** (generated face) **BEFORE first post** — new accounts with no photo = flagged
7. Write bio with 🤖 AI disclosure
8. Follow 10-20 relevant accounts (not each other — Twitter flags self-networks)
9. **Wait 1 hour minimum before first post** — lets account settle
10. First post: something genuine-looking, NOT a product pitch

### 2.2 Instagram Signup (Business Account)

**Sources:**
- [Social Rails 2025 IG Guide](https://socialrails.com/blog/multiple-instagram-accounts-guide) — 5/device, Gmail +aliases work
- Your cited Instagram help doc

**Steps:**
1. Different browser from Twitter session (if on laptop) OR switch to phone
2. Instagram app → Profile → Menu (☰) → Add account → Create new account
3. Or instagram.com → Sign up
4. Use Alex's email + Alex's phone
5. Pick handle (same as Twitter ideally — consistency across platforms)
6. Set profile pic (generated face) + bio (with 🤖 disclosure)
7. **Switch to Business/Creator account**: Settings → Account type → Switch to Business
8. **Link to Facebook Page** (you'll create/link in Phase 3)
9. Follow 10-20 relevant accounts
10. Wait 1 hour
11. First post: a branded carousel or a simple "hey, I'm Alex" reel with **Made with AI label turned ON at post time**

**Critical:** When you upload the first post, toggle "AI-generated content" / "Made with AI" in advanced settings. Our publisher code handles this automatically for automated posts, but the FIRST manual post should also have it.

### 2.3 TikTok Signup

**Source:** [TikTok Newsroom](https://newsroom.tiktok.com/en-us/new-labels-for-disclosing-ai-generated-content) — AI content label REQUIRED

**Steps:**
1. Different browser / device
2. tiktok.com → Sign up (or TikTok app)
3. Use Alex's email OR phone
4. Pick username (same handle as Twitter/IG)
5. Set profile pic + bio (🤖 AI disclosure)
6. Age verification — pick age matching persona's DOB
7. Switch to Business account: Settings → Account → Switch to Business Account
8. **First post: use AI-Generated Content toggle ON** at publish time

**Warning:** TikTok strike = 73% reach drop within 48 hours. One strike isn't fatal, but don't get one by forgetting the label.

### 2.4 Facebook Page + Meta Business Linkage

**This is where Instagram + Facebook share infrastructure. Do this AFTER creating the IG account.**

**Steps:**
1. Go to Meta Business Manager (business.facebook.com)
2. Pages → Add → Create a new Page
3. Page name: "Alex Volta" (same as persona)
4. Category: Creator, Digital Creator, or Personal Blog
5. Set page profile picture (same face)
6. Page About: 🤖 AI disclosure + one_thing
7. Still in Business Manager → Accounts → Instagram Accounts → Add → Claim Alex's IG account
8. Link the IG to the Facebook Page just created

**Why this matters:**
- Our `publishers/instagram.py` requires IG Business Account linked to FB Page (Meta Graph API requirement)
- Our `publishers/facebook.py` posts to the Page
- Both use the **same access token**

### 2.5 YouTube Channel

**Source:** [Knolli.ai YouTube 2026](https://www.knolli.ai/post/youtube-ai-monetization-policy-2025) — inauthentic content policy

**Steps:**
1. Use Alex's Google account (alex.volta@gmail.com or an alias)
2. Go to youtube.com → sign in → Create Channel
3. Channel name: "Alex Volta"
4. Channel handle: @alexvolta (match other platforms)
5. Upload channel art (use the AI face, larger format)
6. Write "About" section with 🤖 AI disclosure
7. **DO NOT start posting immediately** — YouTube new channels flagged for rapid posting
8. Wait 2-3 days after channel creation before first upload

**When you DO post:**
- First upload should be high-quality (not templated, has genuine insight)
- ALWAYS toggle the "Altered content / Contains: Altered or synthetic content" checkbox at upload
- Our publisher code sets `containsSyntheticMedia=true` automatically for API uploads

### 2.6 Skip LinkedIn

**Do not create LinkedIn accounts for Alex, Marcus, or Sage.**

Cited: [Multilogin](https://multilogin.com/blog/mobile/can-i-create-multiple-linkedin-accounts/) — LinkedIn's 2026 neural networks detect AI faces at 99% accuracy. Account ban cascades to your REAL LinkedIn.

Anthony posts on LinkedIn from his real account only.

---

## Phase 3 — Capture OAuth Tokens (Day 3-5, 30 min per platform per face)

After accounts are created, our code needs API access to post autonomously.

### Fastest Path (V1) — Direct Tokens into .env

For each platform, generate the access token and paste into `.env`:

**Twitter:**
- developer.x.com → Projects → Your App → Keys and Tokens
- Generate "Access Token + Secret" for each Alex/Marcus/Sage account
- Put in `.env` per face (need multi-face env var pattern OR Nango)

**Instagram / Facebook (shared token):**
- Graph API Explorer → select app → Get Token → User Token → Switch to Page → Get Page Access Token
- Extend to long-lived token (60 days)
- Put `FACEBOOK_PAGE_ACCESS_TOKEN` + `INSTAGRAM_ACCESS_TOKEN` (same token) in `.env`

**TikTok:**
- TikTok Developer portal → Your app → Add URL redirect → OAuth flow → capture access_token
- Put in `.env`

**YouTube:**
- Google Cloud Console → OAuth 2.0 credentials → run OAuth flow (one-time) → get refresh_token
- Our code uses the refresh token to mint fresh access tokens automatically

### Better Path (For MaaS Scale) — Nango OAuth Manager

Once we add Nango wiring (next todo), we use connection IDs:

```
twitter-alex_volta
twitter-marcus_cole
twitter-sage_moreno
twitter-anthony  (your personal)
instagram-alex_volta
...etc
```

24 connections (6 platforms × 4 faces) — all managed in Nango, automatic refresh, one unified API.

For Day 1 launch though, direct env vars work. Nango wiring is an upgrade for when scale demands it.

---

## Phase 4 — Warmup Period (Day 3-10, 1 week minimum)

Per verified sources, new accounts posting 3x/day immediately = shadow ban risk.

### Warmup Schedule Per Account

| Day Since Created | Activity |
|-------------------|----------|
| Day 0-1 | Profile complete, follow 10-20 accounts, no posts |
| Day 2-3 | 1 post/day, manual, conversational |
| Day 4-7 | 1-2 posts/day, mix of content types |
| Day 8-14 | Scale to 2-3 posts/day if engagement looks healthy |
| Day 15+ | Full cadence (3/day per platform per YAML) |

### What "Healthy" Looks Like (Signs We're OK)
- Posts getting views (even if small numbers)
- No "post failed to publish" errors
- Followers can engage with posts (no shadow block)
- Platform app works normally when you log in manually

### Red Flags (Pause Posting)
- Posts showing "only visible to you"
- Reach suddenly drops 70%+ overnight
- Platform prompts for identity verification
- Emails about "suspicious activity"

If red flags appear → pause that account, let it sit 3-7 days, check email for platform messages, engage manually (like/comment from that account) to look human.

---

## Phase 5 — Enable Automation (Day 10+)

Once warmup is complete:

1. Run `python scripts/test_publish.py --platform twitter --influencer alex_volta` (dry-run)
2. Then `--live` for one real post
3. Verify post appears with AI disclosure enabled
4. Enable orchestrator to include that face in daily cycles
5. Watch graph data: `python -c "from content_engine import graph_writer; print(graph_writer.get_analyst_view())"`

Repeat for each influencer × platform combo.

---

## Daily Operational Rules (Post-Launch)

**For the operator to avoid platform flags:**

1. **Never have AI faces engage with each other** — no likes/comments/follows between Alex/Marcus/Sage (Twitter platform manipulation rule)
2. **Vary post timing** — don't post all 3 faces at exactly :00 minutes, stagger across the hour
3. **Vary content structure** — if Alex's posts always have the same structure, YouTube flags as templated (inauthentic)
4. **Track rate limits in compliance.py** — already wired, but monitor weekly
5. **Review each AI disclosure flag** — if any post went live WITHOUT the flag, remove it immediately

---

## Total Setup Time Estimate

| Task | Per-Influencer Time | Total (3 AI) |
|------|---------------------|--------------|
| Generate face + voice + persona brief | 1 hr | 3 hrs |
| Account creation across 5 platforms | 2 hrs (spread over 3 days) | 6 hrs |
| OAuth token capture | 1 hr | 3 hrs |
| Warmup (passive — 1 manual post/day) | 10-15 min/day × 7 days | 2-3 hrs total |
| **Total active work** | ~5 hrs per persona | **~14-15 hours total** |
| **Calendar time** | Day 0 → Day 10 ready to automate | **~10 days** |

Can be compressed if you dedicate a full weekend to it.

---

## What Happens After Day 10

- 3 AI influencers posting 12 pieces/day each = 36/day from AI
- Plus Anthony's 15/day across 5 platforms + YT weekly
- **Total daily output: ~51 pieces/day**
- Every piece writes to MarketingGraph
- Scoring loop runs 48hr post-publish
- Autoresearch promotes patterns to PROVEN after repeat evidence
- Killer query tells you what's working
- Kill decoration weekly
- Tune based on data

---

## Cited Sources (Complete List)

1. **Instagram multi-account** — [Social Rails 2025](https://socialrails.com/blog/multiple-instagram-accounts-guide), [Instagram Help](https://help.instagram.com/1696686240613595)
2. **Instagram fingerprinting** — [Geelark 2026](https://www.geelark.com/blog/can-i-have-multiple-instagram-accounts/)
3. **Twitter multi-account** — [Social Rails 2026](https://socialrails.com/blog/how-to-create-multiple-twitter-accounts)
4. **TikTok AI labeling** — [TikTok Newsroom](https://newsroom.tiktok.com/en-us/new-labels-for-disclosing-ai-generated-content), [Oreate AI](https://www.oreateai.com/blog/tiktoks-20242025-ai-content-labeling-navigating-the-new-frontier-of-digital-authenticity/1330d4e6743e1a0fbeef953bf23220a2)
5. **LinkedIn AI detection** — [Multilogin](https://multilogin.com/blog/mobile/can-i-create-multiple-linkedin-accounts/), [GoLogin](https://gologin.com/blog/linkedin-multiple-accounts/)
6. **YouTube inauthentic content** — [Knolli.ai 2025](https://www.knolli.ai/post/youtube-ai-monetization-policy-2025), [ScaleLab 2026](https://scalelab.com/en/why-youtube-is-cracking-down-on-ai-generated-content-in-2026)
7. **YouTube Shorts limits** — [reShorts 2026](https://reshorts.ai/blog/how-many-shorts-can-i-upload-on-youtube-per-day-a-guide-for-new-creators), [Social Rails YT Guide](https://socialrails.com/blog/youtube-upload-limits-complete-guide)
8. **2025 Meta Ban Wave context** — [Medium: Meta Ban Wave 2025](https://medium.com/@ceo_46231/the-great-meta-ban-wave-2025-instagram-accounts-caught-in-the-crossfire-ef007135a19f)

All 8 sources verified between April 12-14, 2026 for this runbook.

---

## One-Page Summary

1. Generate face + voice + persona brief (1hr each AI influencer)
2. Create 5 platform accounts per influencer over 3 days (Twitter, IG, TikTok, FB, YT — NOT LinkedIn)
3. Use different browser fingerprints per influencer (Chrome/Firefox/Safari minimum)
4. Use Gmail +aliases for emails, Google Voice for phones
5. Set profile pic + 🤖 AI disclosure bio BEFORE first post
6. Warmup 7 days with 1-2 posts/day (manual) before enabling automation
7. Enable AI-content labels on EVERY post (API flags already wired in our publishers)
8. Capture OAuth tokens → .env (or Nango for scale)
9. Run `test_publish.py --live` on first real automated post per face/platform
10. Automation takes over at Day 10, graph learns from there