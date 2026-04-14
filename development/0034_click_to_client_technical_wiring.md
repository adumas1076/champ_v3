# 0034 — Click to Client: Technical Wiring Spec
**Date:** 2026-04-12
**Category:** Marketing Machine — Implementation Blueprint
**Status:** V1 — Ready for build session
**Deadline:** Wednesday 2026-04-15
**SAR:** Secure, Autonomous, Reliable
**Depends on:** 0029 (framework), 0030 (product), 0033 (AI influencers)

---

## Purpose

This doc is the WIRING DIAGRAM for the build session. 0033 defines WHO posts and WHAT they post. This doc defines HOW every touchpoint connects to the Click to Client pipeline.

Every social media interaction must flow:

```
Content → Engagement → Capture → Nurture → Convert → Client
```

No dead ends. No content that doesn't feed the pipeline.

---

## Component 1: Platform Publishers

### What to Build
New directory: `content_engine/publishers/`

Each publisher handles OAuth + posting + rate limiting for one platform.

```
content_engine/publishers/
├── __init__.py
├── base.py          # Abstract publisher with retry, rate limit, compliance
├── twitter.py       # Twitter API v2 posting
├── linkedin.py      # LinkedIn UGC posting
├── instagram.py     # Instagram Graph API (via Meta Business)
├── tiktok.py        # TikTok Content Posting API
├── youtube.py       # YouTube Data API v3 upload
├── facebook.py      # Facebook Graph API posting
└── compliance.py    # Rate limits, disclosure rules, ban prevention
```

### Base Publisher Interface
```python
class BasePublisher:
    async def post_text(self, content: str, metadata: dict) -> PublishResult
    async def post_image(self, content: str, image_path: str, metadata: dict) -> PublishResult
    async def post_video(self, content: str, video_path: str, metadata: dict) -> PublishResult
    async def post_carousel(self, content: str, images: list[str], metadata: dict) -> PublishResult
    async def reply_to_comment(self, comment_id: str, reply: str) -> PublishResult
    async def send_dm(self, user_id: str, message: str) -> PublishResult
    async def get_comments(self, post_id: str, since: datetime) -> list[Comment]
    async def get_dms(self, since: datetime) -> list[DirectMessage]
    async def check_rate_limit(self) -> RateLimitStatus
```

### Compliance Layer (`compliance.py`)
```python
PLATFORM_LIMITS = {
    # MVP: 3 posts/day per face on 4 platforms. YouTube + Facebook in Phase 3.
    "twitter": {"posts_per_day": 3, "dms_per_day": 50, "min_interval_sec": 120},
    "instagram": {"posts_per_day": 3, "dms_per_day": 30, "min_interval_sec": 600},
    "tiktok": {"posts_per_day": 3, "dms_per_day": 20, "min_interval_sec": 1200},
    "linkedin": {"posts_per_day": 2, "dms_per_day": 25, "min_interval_sec": 1200},  # LinkedIn safe max is 2-3, stay at 2
    # "youtube": Phase 3 — pillar content only, 1-2/week
    # "facebook": Phase 3
}

class ComplianceChecker:
    def can_post(self, platform: str, influencer_id: str) -> bool
    def record_action(self, platform: str, influencer_id: str, action_type: str)
    def get_next_safe_time(self, platform: str, influencer_id: str) -> datetime
    def add_disclosure(self, content: str, platform: str) -> str  # Adds required automation labels
```

### OAuth / Credentials
- All OAuth tokens managed via Nango (already set up — see `project_nango_oauth_playbook.md`)
- Fallback: environment variables with encrypted storage
- NEVER hardcode tokens. NEVER log tokens. NEVER commit tokens.

---

## Component 2: Comment/DM Keyword Monitor

### What to Build
New file: `content_engine/monitor.py`

Polls platform APIs every 60 seconds for:
1. New comments containing trigger keywords
2. New DMs containing trigger keywords

### Keyword Registry
```python
KEYWORD_TRIGGERS = {
    # Keyword → {influencer, lead_magnet, qualifying_question}
    "BUILD": {
        "influencer": "influencer_1",
        "lead_magnet": "AI Stack Breakdown PDF",
        "qualifying_question": "What are you building right now?",
        "funnel_stage": "MOFU",
    },
    "SCALE": {
        "influencer": "influencer_2",
        "lead_magnet": "Business Diagnostic Template",
        "qualifying_question": "What's your current monthly revenue?",
        "funnel_stage": "MOFU",
    },
    "BRAND": {
        "influencer": "influencer_3",
        "lead_magnet": "Brand Audit Checklist",
        "qualifying_question": "What industry is your brand in?",
        "funnel_stage": "MOFU",
    },
    "OPERATOR": {
        "influencer": "anthony",
        "lead_magnet": "Free AI Readiness Audit",
        "qualifying_question": "What's the biggest bottleneck in your business right now?",
        "funnel_stage": "BOFU",
    },
    "START": {
        "influencer": "any",
        "lead_magnet": None,
        "qualifying_question": None,
        "funnel_stage": "BOFU",
        "action": "route_to_checkout",
    },
}
```

### Monitor Loop
```python
async def monitor_loop():
    while True:
        for platform in active_platforms:
            for influencer in active_influencers:
                # Check comments on recent posts
                comments = await publisher.get_comments(recent_post_ids, since=last_check)
                for comment in comments:
                    keyword = extract_keyword(comment.text)
                    if keyword in KEYWORD_TRIGGERS:
                        await handle_keyword_trigger(comment, keyword, platform, influencer)

                # Check DMs
                dms = await publisher.get_dms(since=last_check)
                for dm in dms:
                    keyword = extract_keyword(dm.text)
                    if keyword in KEYWORD_TRIGGERS:
                        await handle_dm_trigger(dm, keyword, platform, influencer)

        await asyncio.sleep(60)  # Poll every 60 seconds
```

### Trigger Handler
```python
async def handle_keyword_trigger(interaction, keyword, platform, influencer):
    trigger = KEYWORD_TRIGGERS[keyword]

    if trigger.get("action") == "route_to_checkout":
        await publisher.send_dm(interaction.user_id,
            f"Here's your direct link to get started: {CHECKOUT_URL}")
        await log_lead(interaction, stage="BOFU", source="keyword_dm")
        return

    # Send lead magnet + qualifying question
    await publisher.send_dm(interaction.user_id,
        f"Hey {interaction.user_name}! Here's your {trigger['lead_magnet']}: {LEAD_MAGNET_URL}\n\n"
        f"Quick question — {trigger['qualifying_question']}")

    # Capture lead
    await capture_lead(
        platform=platform,
        user_id=interaction.user_id,
        user_name=interaction.user_name,
        source=f"keyword_{keyword}",
        influencer=influencer,
        funnel_stage=trigger["funnel_stage"],
    )
```

---

## Component 3: Landing Page

### What to Build
Single-page Vercel deployment. One page per product initially.

### URL Structure
- `cocreatiq.com/marketing-machine` — main product landing page
- `cocreatiq.com/audit` — free AI readiness audit (lead magnet landing)
- `cocreatiq.com/start` — Stripe checkout

### Landing Page Structure (Above the Fold)
```
[HEADLINE]: "Your AI Marketing Team That Never Sleeps"
[SUBHEADLINE]: "4 AI influencers posting 60-100 pieces/day across 5 platforms. 
               Every post feeds a pipeline. Every click becomes a client."
[HERO]: Demo video (30-60 sec showing the system in action)
[CTA BUTTON]: "Get Your Free Content Audit" → email capture modal
[SOCIAL PROOF]: "Already powering [X] creators" / Stripe revenue screenshot
```

### Below the Fold
```
[PROBLEM]: "You're creating content but not creating clients"
[SOLUTION]: 3-column showing the 3 AI influencers + what they do
[HOW IT WORKS]: 4 steps (Connect → Generate → Publish → Convert)
[PROOF]: Before/after metrics, case study (Anthony = Client 0 data)
[PRICING]: 3 tiers ($29/$97/$299) with feature comparison
[FAQ]: 5-7 common objections addressed
[FINAL CTA]: "Start Your Free Audit" → email capture
```

### Tech
- Next.js on Vercel (already have Vercel deployment from `project_cloud_deployment_status.md`)
- Tailwind CSS
- Email capture form → Resend API
- UTM parameter tracking on all inbound links
- Lead magnet delivery: immediate email with PDF/link after capture

---

## Component 4: Email Infrastructure

### Provider: Resend
- Why: Developer-first, great API, React email templates, affordable
- Alternative: SendGrid (if Resend has deliverability issues)

### What to Build
New directory: `content_engine/email/`

```
content_engine/email/
├── __init__.py
├── sender.py         # Resend API wrapper
├── templates/        # React email templates (or HTML)
│   ├── welcome.html
│   ├── lead_magnet.html
│   ├── nurture_day1.html
│   ├── nurture_day2.html
│   ├── nurture_day3.html
│   ├── nurture_day4.html
│   ├── nurture_day5.html
│   ├── nurture_day6.html
│   ├── nurture_day7.html
│   └── offer.html
├── sequences.py      # Nurture sequence engine
└── triggers.py       # Behavior-triggered email logic
```

### 7-Day Nurture Sequence

| Day | Subject Line Pattern | Content | CTA |
|-----|---------------------|---------|-----|
| 0 | "Your [lead magnet] is ready" | Deliver lead magnet + quick win | "Reply with your biggest challenge" |
| 1 | "[First name], did you try this?" | One actionable tip from lead magnet | "Here's a 2-min exercise" |
| 2 | "The #1 mistake [niche] businesses make" | ISF-style problem → solution | "Watch this 60-sec breakdown" (content link) |
| 3 | "How [Client 0 / case study] went from X to Y" | Social proof, real results | "See the full case study" |
| 4 | "3 things I'd do differently" | Vulnerability + expertise | "Reply — what would YOU change?" |
| 5 | "This is what separates [niche] winners" | Framework reveal (partial) | "Get the full framework" (product tease) |
| 6 | "Ready to stop doing it manually?" | Direct product pitch with value stack | "Start your free trial" / "Book a call" |

### Behavior Triggers
```python
BEHAVIOR_TRIGGERS = {
    "opened_3_emails": {"action": "tag_engaged", "score_boost": 10},
    "clicked_link": {"action": "tag_interested", "score_boost": 15},
    "replied_to_email": {"action": "tag_hot", "score_boost": 25, "route": "sales"},
    "visited_pricing_page": {"action": "send_offer_email", "score_boost": 20},
    "abandoned_checkout": {"action": "send_recovery_email", "delay": "1h"},
    "no_open_3_days": {"action": "send_reengagement", "score_penalty": -10},
}
```

---

## Component 5: Lead Scoring Engine

### What to Build
New file: `content_engine/lead_scoring.py`

### Scoring Model (BANT + Priestley)

**Intent Signals (50% of score):**
| Signal | Points |
|--------|--------|
| Commented keyword | +10 |
| DM'd keyword | +15 |
| Clicked landing page | +10 |
| Downloaded lead magnet | +15 |
| Opened 3+ emails | +10 |
| Clicked email link | +15 |
| Visited pricing page | +20 |
| Replied to email | +25 |
| Booked call | +30 |
| Abandoned checkout | +20 |

**Fit Signals (50% of score):**
| Signal | Points |
|--------|--------|
| Business owner (from qualifying question) | +20 |
| Revenue > $10k/mo (from qualifying answer) | +15 |
| Team size > 3 (from qualifying answer) | +10 |
| Niche match (tech/business/creative) | +15 |
| Has existing content (from audit) | +10 |
| Budget mentioned | +20 |

### Routing
```python
def route_lead(score: int) -> str:
    if score >= 80:
        return "HOT"    # → Sales Operator immediately, <60 sec response
    elif score >= 50:
        return "WARM"   # → Continue nurture sequence, check in at day 7
    else:
        return "COLD"   # → Content drip only, re-score in 30 days
```

---

## Component 6: Stripe Checkout

### What to Build
New file: `content_engine/payments/`

```
content_engine/payments/
├── __init__.py
├── checkout.py       # Create checkout sessions
├── webhooks.py       # Handle Stripe webhooks
└── subscriptions.py  # Manage active subscriptions
```

### Webhook Events to Handle
```python
WEBHOOK_HANDLERS = {
    "checkout.session.completed": handle_new_customer,      # → Onboarding email
    "customer.subscription.created": handle_subscription,    # → Activate account
    "customer.subscription.updated": handle_plan_change,     # → Update permissions
    "customer.subscription.deleted": handle_cancellation,    # → Retention sequence
    "invoice.payment_failed": handle_failed_payment,         # → Dunning email
    "invoice.paid": handle_successful_payment,               # → Receipt + confirmation
}
```

### Checkout Flow
```
User clicks "Start" on landing page
  → Stripe Checkout session created (server-side)
  → Redirect to Stripe hosted checkout
  → Payment processed
  → Webhook fires → handle_new_customer()
  → Welcome email sent
  → Account provisioned
  → Redirect to dashboard / onboarding
```

---

## Component 7: The Orchestrator

### What to Build
New file: `content_engine/orchestrator.py`

This is the BRAIN of the Marketing Machine. It ties everything together and runs the full autonomous loop.

### Main Loop
```python
async def orchestrator_loop():
    """The Marketing Machine main loop. Runs forever."""

    while True:
        # 1. GENERATE content for all influencers
        for influencer in load_all_influencers():
            for platform in influencer["platforms"]["primary"] + influencer["platforms"]["secondary"]:
                # Check if we need content for this slot
                if scheduler.needs_content(influencer["id"], platform):
                    # Pick funnel stage based on current balance
                    stage = funnel.get_needed_stage(influencer["id"])

                    # Generate content
                    content = await generate_content(influencer, platform, stage)

                    # Quality gate
                    score = eval_content(content)
                    if score < 75:
                        content = await regenerate_with_feedback(content, score)

                    # Format for platform
                    formatted = format_for_platform(content, platform)

                    # Queue for publishing
                    scheduler.add_to_queue(formatted)

        # 2. PUBLISH due posts
        results = await scheduler.publish_due()
        for result in results:
            if result.success:
                funnel.add(result.content)

        # 3. MONITOR comments and DMs
        await monitor_check()

        # 4. SCORE published content (48h+ old)
        await score_mature_content()

        # 5. LEARN from scores
        if enough_data_for_cycle():
            await run_autoresearch_cycle()

        # 6. SEND nurture emails
        await process_email_queue()

        # Sleep based on next scheduled action
        next_action = scheduler.get_next_due_time()
        sleep_duration = min((next_action - now()).seconds, 300)
        await asyncio.sleep(sleep_duration)
```

---

## Component 8: Anthony's Clone Profile

### What to Build
New file: `content_engine/influencers/influencer_0_anthony.yaml`

Follows same format as the other 3 YAML profiles but with:
- Face source: Anthony's actual reference video/photos
- Voice source: Anthony's Qwen3-TTS clone (already built)
- Brand voice: Anthony's actual voice (direct, real, technical + business hybrid)
- Can be overridden by real Anthony posts at any time
- Self-mode flag: `autonomous: true` with `human_override: true`

---

## File Ownership (Session Isolation)

### Build Session OWNS (can create/modify):
```
content_engine/publishers/        # NEW — all files
content_engine/monitor.py         # NEW
content_engine/email/             # NEW — all files
content_engine/lead_scoring.py    # NEW
content_engine/payments/          # NEW — all files
content_engine/orchestrator.py    # NEW
content_engine/influencers/influencer_0_anthony.yaml  # NEW
frontend/ pages for landing page  # NEW files only
```

### Build Session Can READ but NOT MODIFY:
```
content_engine/eval.py            # Working — don't touch
content_engine/scoring.py         # Working — don't touch
content_engine/autoresearch.py    # Working — don't touch
content_engine/pipeline/*         # Working — don't touch
content_engine/analytics/*        # Working — don't touch
content_engine/influencers/loader.py           # Working — don't touch
content_engine/influencers/influencer_1-3.yaml # Working — don't touch
operators/configs/*               # Working — don't touch
brain/*                           # OTHER SESSION — don't touch
mind/*                            # OTHER SESSION — don't touch
self_mode/*                       # OTHER SESSION — don't touch
```

---

## Wednesday Definition of Done

The system is "production-ready" when:

1. Anthony can say "post" and content goes live on 2+ platforms within 5 minutes
2. A stranger can comment a keyword and receive a DM within 60 seconds
3. A stranger can land on the page and capture their email in one click
4. A captured email receives Day 0 nurture email within 5 minutes
5. The whole loop runs without Anthony touching anything for 24 hours
6. No platform accounts get flagged, warned, or banned
7. Anthony can see what happened (logs, dashboard, or summary report)

That's SAR. That's Click to Client. That's the Marketing Machine.
