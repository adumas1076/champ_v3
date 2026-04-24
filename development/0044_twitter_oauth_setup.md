# 0044 — Twitter/X OAuth Setup (Tech Session Handoff)

**Created:** 2026-04-23
**Owner:** Tech session after Meta tests pass
**Prerequisite:** 0040 Nango setup, 0043 Meta test plan executed successfully
**Reference:** `memory/reference_meta_graph_api_gotchas.md` (pattern reuse)

---

## Why Twitter Is Second

| Platform | Setup Complexity | Post Complexity | Why Second |
|----------|-----------------|-----------------|------------|
| Meta (FB+IG) | Complex (Page Token swap, 2-step IG publish) | Complex | Proving ground for hard patterns |
| **Twitter** | **Simple (OAuth 2.0 PKCE, no token swap)** | **Simple (direct tweet)** | **Apply proven patterns to easier platform** |
| TikTok | Complex (app audit needed) | Async (poll-and-wait) | Later |
| LinkedIn | Medium (OAuth 2.0, content approval) | Medium | Anthony only, lower priority |

Meta taught us the hard way. Twitter is where we prove the orchestrator works with a second platform.

---

## Goal

Get Anthony's Twitter/X account posting autonomously via Cocreatiq OS:
- OAuth 2.0 with PKCE via Nango (single-user scope)
- `tweet.read`, `tweet.write`, `users.read` scopes
- DM reads/writes (`dm.read`, `dm.write`) if Basic tier
- Post text, thread, image, video
- Read mentions + replies for keyword detection

---

## Phase 1: Twitter Developer Account

### Step 1: Apply for Developer Access
- Go to: https://developer.x.com/en/portal/petition/essential/basic-info
- Use the Cocreatiq business email (or Anthony's personal if unified)
- **Purpose description copy-paste:**
  ```
  Building an AI-powered content operator that posts on behalf of the account owner
  across multiple platforms. Use cases: scheduled posting, engagement monitoring,
  auto-reply to keyword triggers, DM-based lead capture for small businesses.
  Read-only analytics to measure content performance.
  ```
- Wait for approval (usually < 24hrs for Essential tier)

### Step 2: Create App In Dev Portal
- Navigate: Projects & Apps → Create App
- **App name:** `Cocreatiq Marketing Machine`
- **App description:** "AI content operator for Abundant Creators LLC — autonomous posting, engagement tracking, lead capture"
- **Website URL:** `https://cocreatiq.com` (placeholder — any domain works)
- **App icon:** Upload Cocreatiq logo (use logo from brand_assets once exported)

### Step 3: Configure OAuth 2.0
In app settings:
- **Type of App:** `Web App, Automated App, or Bot` (Confidential client)
- **OAuth 2.0 Settings → Client Type:** `Confidential client`
- **Callback URL:** `https://api.nango.dev/oauth/callback`
- **Website URL:** `https://cocreatiq.com`
- Save → get back `Client ID` + `Client Secret`

### Step 4: Request Scopes
Mark these as needed scopes:
- `tweet.read` — read tweets (ours + mentions)
- `tweet.write` — post tweets, reply, delete
- `users.read` — profile info
- `offline.access` — refresh token (required for long-lived access)
- `dm.read` — read DMs (for lead capture)
- `dm.write` — send DMs (Click to Client)
- `like.read` + `like.write` — engagement tracking
- `follows.read` — audience insights

Some scopes require Basic tier ($100/mo). Start with Essential (free) + `tweet.read`, `tweet.write`, `users.read`, `offline.access`. Add DM scopes when upgrading.

---

## Phase 2: Nango Integration

### Step 1: Create Nango Integration
- Go to: https://app.nango.dev
- Integrations → New Integration → **Twitter** (search "twitter")
- Provider: `twitter-v2`
- **Unique Key:** `twitter` (lowercase, no version — matches our naming pattern)
- Fill in:
  - `Client ID` (from Twitter Dev Portal)
  - `Client Secret` (from Twitter Dev Portal)
  - `Scopes`: comma-separated from Phase 1 Step 4 above
- Save

### Step 2: Create Connect Link For Anthony
Same pattern as Meta OAuth (proven flow):

```python
import os
from nango import Nango
nango = Nango(secret_key=os.getenv("NANGO_SECRET_KEY"))

# Generate a connect session token
session = nango.create_connect_session(
    end_user={"id": "anthony", "email": "anthony@abundantcreators.com"},
    allowed_integrations=["twitter"]
)
connect_url = f"https://api.nango.dev/oauth/connect/twitter?connect_session_token={session.token}"
print(f"Send Anthony this URL: {connect_url}")
```

Anthony clicks link → authorizes on Twitter → Nango stores tokens → returns `connection_id`.

### Step 3: Save Connection ID
Log the returned `connection_id` in:
- `.env` as `TWITTER_CONNECTION_ID=...`
- `influencer_0_anthony.yaml` under `platforms.twitter.nango_connection_id`

---

## Phase 3: Test Plan (Apply 0043 Pattern)

Follow same structure as FB/IG test plan:

| Group | Tests | What's Validated |
|-------|-------|------------------|
| A. Auth | T001-T002 | Nango → User token (no Page Token swap needed!) |
| B. Reads | T003-T006 | Profile, timeline, mentions, DMs |
| C. Writes | T007-T010 | Tweet text, thread, image, delete |
| D. Engagement | T011-T013 | Like, retweet, reply |
| E. DMs | T014-T015 | Send DM, read DMs |
| F. E2E | T016-T017 | Mention trigger → auto-reply → DM |

### T001 — Fetch Twitter Token From Nango

```python
from nango import Nango
nango = Nango(secret_key=os.getenv("NANGO_SECRET_KEY"))
conn = nango.get_connection(
    provider_config_key="twitter",
    connection_id=TWITTER_CONNECTION_ID
)
access_token = conn.credentials.raw["access_token"]
assert access_token is not None
```

**Expected:** Valid bearer token.
**Gotcha:** Nango auto-refreshes expired tokens — if request fails with 401, refetch connection and retry.

### T007 — Post Text Tweet

```python
import requests
r = requests.post(
    "https://api.twitter.com/2/tweets",
    headers={"Authorization": f"Bearer {access_token}"},
    json={"text": "Scope test T007 — automated via Cocreatiq [DELETE ME]"}
)
assert r.status_code == 201
tweet_id = r.json()["data"]["id"]
TWITTER_TEST_TWEET_ID = tweet_id
```

**Expected:** `201` + `{data: {id: ..., text: ...}}`.
**Gotcha:** Free tier has 17 tweets/24h limit. Stay under.

### T010 — Delete Tweet

```python
r = requests.delete(
    f"https://api.twitter.com/2/tweets/{TWITTER_TEST_TWEET_ID}",
    headers={"Authorization": f"Bearer {access_token}"}
)
assert r.json()["data"]["deleted"] is True
```

---

## Free Tier Limits (Essential Tier)

| Endpoint | Limit |
|----------|-------|
| POST /tweets | 17 / 24 hrs per user |
| POST /tweets (app-level) | 50 / 24 hrs |
| GET /tweets/:id | 1,500,000 / month app-level |
| POST /users/:id/following | 5 / 15 min |
| POST /users/:id/retweets | 5 / 15 min |
| GET /users/:id/mentions | 300 / 15 min |
| DM send | Basic tier required ($100/mo) |

**Our daily budget: 3 tweets × 4 platforms = 3 Twitter/day** → well under 17 limit. No upgrade needed for V1 text posting.

**For DMs:** Basic tier required ($100/mo). Wait until lead capture proves value OR auto-DM is business-critical.

---

## Known Gotchas (Twitter-Specific)

### 1. OAuth 2.0 PKCE Required
Twitter doesn't allow OAuth 2.0 without PKCE (code verifier). Nango handles this automatically — we don't need to generate code verifiers ourselves.

### 2. Refresh Tokens Expire After 6 Months Of Inactivity
Unlike Meta Page Tokens (can last forever with pages_show_list refresh), Twitter tokens need active use. Mitigate: daily auto-post keeps the token fresh.

### 3. Rate Limit Errors Don't Always 429
Twitter sometimes returns 503 or 500 under rate pressure. Treat any 5xx from Twitter as potential rate limit — back off + retry with exponential delay.

### 4. Media Upload Is A 2-Step Flow (Like IG)
For images/videos:
- Step 1: POST `/1.1/media/upload.json` (note: v1.1 endpoint, not v2) → get `media_id_string`
- Step 2: POST `/2/tweets` with `media: {media_ids: [media_id_string]}`

Caveat: `/1.1/media/upload.json` requires OAuth 1.0a for some video types. For images, OAuth 2.0 bearer works.

### 5. Thread Posting = Reply Chain
No native "thread" API. Post tweet 1, then post tweet 2 with `reply: {in_reply_to_tweet_id: <tweet_1_id>}`. Repeat for tweet 3, 4, etc.

### 6. `from` Field On Mentions Requires User Lookup
Mention response gives `author_id` (not full user info). Separate call to `/2/users/:id` for username/profile.

---

## Integration Points Into Existing Code

### Follows Meta Pattern Exactly
Tech session just wrote `facebook_publisher.py`. Twitter follows the SAME structure:

```python
content_engine/publishers/
├── twitter_publisher.py       # NEW — this doc's output
│   class TwitterPublisher(BasePublisher):
│     def post_tweet(text: str) -> dict
│     def post_thread(tweets: list[str]) -> list[dict]
│     def post_with_image(text: str, image_url: str) -> dict
│     def reply_to_tweet(tweet_id: str, text: str) -> dict
│     def delete_tweet(tweet_id: str) -> bool
│     def get_mentions(since_id: str = None) -> list[dict]
│     def send_dm(user_id: str, text: str) -> dict  # Basic tier only
└── tests/
    └── test_twitter_publisher.py
```

Base class from Meta work gets reused. New subclass implements Twitter-specific endpoints.

---

## Success Criteria

**Pass:** 14+/17 tests pass (82% threshold).

### Why 82% (Twitter) vs 90% (Meta)
The lower threshold is intentional, not sloppy. Three tests are **tier-gated or deferred by design**, not code bugs:

- **T014 + T015 (DM send/read):** Require Twitter Basic tier ($100/mo). Not purchased yet — wait until lead capture proves business value.
- **T009 (video upload):** Requires OAuth 1.0a complexity (`/1.1/media/upload.json` for some video types). Deferred to V2 — image-only video content works for V1.

If those 3 fail on tier-gating grounds → **expected, documented, not a pass blocker**. Failures beyond those = real issues.

**Critical paths that MUST work (no excuses):**
- T007 (text tweet) — core Marketing Machine
- T010 (delete) — required for cleanup + mistakes
- T013 (reply) — required for Click to Client
- T016/T017 (E2E) — required for autonomous loop

**Acceptable failures (logged as gaps, not bugs):**
- T014/T015 (DM) if Basic tier not purchased yet — document gap
- T009 (video upload) if OAuth 1.0a complexity not yet tackled — defer to V2

---

## Next Actions After Twitter Tests Pass

1. Mark Twitter integration as production-ready
2. Post Anthony's first real tweet via Marketing Machine
3. Monitor for rate limits over first 72 hours
4. Start TikTok integration (next doc: `0045_tiktok_oauth_setup.md`)
5. Add Twitter to the content scheduler rotation

---

## Timeline Estimate

| Phase | Effort |
|-------|--------|
| Twitter Dev Account approval | < 24 hrs |
| App creation + OAuth config | 30 min |
| Nango integration setup | 15 min |
| Anthony OAuth flow | 5 min |
| Write publisher + tests | 3-4 hrs |
| Execute test suite | 30 min |
| **Total active work** | **~5 hrs** |

Compare to Meta: 2 days of debugging scopes, Page Token swaps, IG 2-step flow. Twitter = the same infrastructure with a simpler API.

---

## Handoff Prompt For Tech Session (When Ready)

Copy into fresh session AFTER Meta tests pass:

```
## Session: Twitter/X OAuth + Publisher Build

### Read First (In Order)
1. `champ_v3/development/0044_twitter_oauth_setup.md` (this doc)
2. `champ_v3/development/0043_fb_ig_scope_test_plan.md` (pattern reference)
3. `champ_v3/development/test_reports/test_report_20260423.md` (what the Meta tests taught us)

### Prerequisites (Must Be Done Before Start)
- [ ] Twitter Developer account approved
- [ ] Cocreatiq Marketing Machine app created in Dev Portal
- [ ] Client ID + Secret saved to Nango integration
- [ ] Anthony OAuth flow completed → Connection ID captured

### What To Build
Follow the pattern from `facebook_publisher.py`:
- `content_engine/publishers/twitter_publisher.py`
- `content_engine/publishers/tests/test_twitter_publisher.py`

### Success Criteria
14+/17 tests pass. T007, T010, T013, T016/T017 MUST pass.

### Produce
`development/test_reports/test_report_twitter_YYYYMMDD.md`
```
