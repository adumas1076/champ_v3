# 0043 — FB/IG Scope Test Plan (Tech Session Handoff)

**Created:** 2026-04-23
**Owner:** Tech session (Python code execution)
**Prerequisite:** 0040_nango_social_media_setup.md, 0041_marketing_machine_complete_pipeline.md
**Reference:** `memory/reference_meta_graph_api_gotchas.md`

## Goal

Validate all 11 Phase 1 scopes granted in the Cocreatiq Meta Developer App end-to-end via code (not manual Graph API Explorer). Produce a test report that proves every capability works before we scale to Twitter/TikTok/LinkedIn.

## Prerequisites Already Complete

- ✅ Cocreatiq Meta Developer App live (App ID `1303754288358216`)
- ✅ Nango integration saved, 11 scopes approved
- ✅ Anthony's OAuth connection live (Connection ID `14283878-5cb4-4695-9368-9d0570bbbfef`)
- ✅ FB Page + IG Business Account assets confirmed
- ✅ One manual FB Page post + one manual IG post proven via Graph API Explorer

## What This Plan Covers

20 test cases across 7 groups:

| Group | Tests | What's Validated |
|---|---|---|
| A. Setup + Auth | T001-T003 | Nango SDK → Page Token derivation → token validation |
| B. Read Operations | T004-T008 | Page metadata, IG profile, posts list, insights |
| C. FB Page Write | T009-T011 | Text post, image post, delete |
| D. Instagram Write | T012-T014 | Container create, publish, delete |
| E. Comment Engagement | T015-T017 | Read comments, reply, hide — Click to Client core |
| F. Messenger | T018 | DM send/receive |
| G. Click to Client E2E | T019-T020 | Full flow: comment → auto-reply → DM → lead logged |

## Asset IDs (Reference)

```python
COCREATIQ_APP_ID = "1303754288358216"
FB_PAGE_ID = "286679221188150"          # Anthony T Battle
IG_BUSINESS_ID = "17841463169176419"    # @anthonytbattle
BUSINESS_PORTFOLIO_ID = "879465601778483"  # Abundant Creators
NANGO_CONNECTION_ID = "14283878-5cb4-4695-9368-9d0570bbbfef"
NANGO_INTEGRATION_ID = "facebook"
NANGO_SECRET_KEY = os.getenv("NANGO_SECRET_KEY")  # already in .env
```

## Implementation Path

Expected code structure:

```
content_engine/publishers/
├── __init__.py
├── base_publisher.py           # Abstract base class (all platforms)
├── facebook_publisher.py       # FB Page-specific
├── instagram_publisher.py      # IG-specific
├── nango_client.py             # Thin wrapper around Nango SDK
└── tests/
    ├── test_fb_publisher.py    # Implements T001-T011
    ├── test_ig_publisher.py    # Implements T012-T014
    ├── test_engagement.py      # Implements T015-T017
    └── test_click_to_client.py # Implements T018-T020
```

Use `pytest` for test runner. Each test case = one pytest function.

## Recommended Execution Order

**Don't skip ahead.** Tests depend on prior tests passing:

1. T001 → T003 (auth first)
2. T004 → T008 (reads confirm we can see Page state)
3. T009 → T011 (FB writes, leave one post live for engagement tests)
4. T012 → T014 (IG writes)
5. T015 → T017 (engagement on the post from T009 or T012)
6. T018 (Messenger)
7. T019 → T020 (full E2E pipeline)

Cleanup step after all pass: delete any remaining test posts/comments/messages.

---

## Group A — Setup + Auth

### T001 — Fetch User Token from Nango

**Scope:** n/a (infrastructure)
**Goal:** Confirm Nango SDK returns a valid User Token.

```python
from nango import Nango
nango = Nango(secret_key=NANGO_SECRET_KEY)
conn = nango.get_connection(
    provider_config_key=NANGO_INTEGRATION_ID,
    connection_id=NANGO_CONNECTION_ID
)
user_token = conn.credentials.raw["access_token"]
assert user_token.startswith("EAA")
```

**Expected:** user_token string, 200+ chars, starts with `EAA`.
**Gotcha:** Nango SDK versions differ — newer versions may use `conn.access_token` directly.

---

### T002 — Derive Page Token

**Scope:** `pages_show_list`, admin permission on Page
**Goal:** Get a Page Token from the User Token.

```python
import requests
r = requests.get(
    f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}",
    params={"fields": "access_token,name", "access_token": user_token}
)
data = r.json()
page_token = data["access_token"]
assert data["name"] == "Anthony T Battle"
assert page_token.startswith("EAA")
assert page_token != user_token  # Must be different
```

**Expected:** `access_token` field in response, different string from user_token.
**Gotcha:** If `access_token` is missing from response, the user isn't an admin of the Page with sufficient permission.

---

### T003 — Verify Page Token Identity

**Scope:** baseline
**Goal:** Confirm the Page Token represents the Page, not the user.

```python
r = requests.get(
    f"https://graph.facebook.com/v22.0/me",
    params={"access_token": page_token}
)
assert r.json()["name"] == "Anthony T Battle"
assert r.json()["id"] == FB_PAGE_ID
```

**Expected:** `name: "Anthony T Battle"`, `id: FB_PAGE_ID`.
**Gotcha:** If returns user name instead, the Page Token wasn't swapped correctly. Re-derive.

---

## Group B — Read Operations

### T004 — Read Page Metadata

**Scope:** `pages_show_list`, `pages_read_engagement`
**Goal:** Confirm we can read Page details.

```python
r = requests.get(
    f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}",
    params={
        "fields": "name,category,fan_count,about,verification_status",
        "access_token": page_token
    }
)
data = r.json()
assert "name" in data
assert "fan_count" in data or data.get("fan_count") is not None
```

**Expected:** Dict with name, category, fan_count.
**Gotcha:** `fan_count` may be missing on Pages with <100 followers.

---

### T005 — Read IG Business Account

**Scope:** `instagram_basic`
**Goal:** Confirm we can read IG profile linked to Page.

```python
r = requests.get(
    f"https://graph.facebook.com/v22.0/{IG_BUSINESS_ID}",
    params={
        "fields": "username,biography,followers_count,media_count,profile_picture_url",
        "access_token": page_token
    }
)
data = r.json()
assert data["username"] == "anthonytbattle"
assert "followers_count" in data
```

**Expected:** Username + profile fields.
**Gotcha:** Same Page Token works for IG calls — no separate IG token needed.

---

### T006 — Read Recent Page Posts

**Scope:** `pages_read_engagement`
**Goal:** Paginate recent posts (proves we can see Page state).

```python
r = requests.get(
    f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/posts",
    params={"limit": 10, "access_token": page_token}
)
assert "data" in r.json()
# If Page has posts, expect non-empty array
```

**Expected:** `{data: [...]}` structure.

---

### T007 — Read Page Insights (Analytics)

**Scope:** `pages_read_engagement`
**Goal:** Confirm analytics API works (for content engine KPI tracking).

```python
r = requests.get(
    f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/insights",
    params={
        "metric": "page_impressions,page_engaged_users",
        "period": "day",
        "access_token": page_token
    }
)
data = r.json()
assert "data" in data
```

**Expected:** Insights data with requested metrics.
**Gotcha:** Metric names changed in v21+. If 404s, check current metric names in Meta docs.

---

### T008 — Read IG Recent Media

**Scope:** `instagram_basic`
**Goal:** Confirm we can list IG posts.

```python
r = requests.get(
    f"https://graph.facebook.com/v22.0/{IG_BUSINESS_ID}/media",
    params={"fields": "id,caption,media_type,timestamp", "access_token": page_token}
)
assert "data" in r.json()
```

**Expected:** Array of IG media with metadata.

---

## Group C — FB Page Write Operations

### T009 — Post Text To FB Page

**Scope:** `pages_manage_posts`
**Goal:** Automated text post (core Marketing Machine capability).

```python
r = requests.post(
    f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/feed",
    params={
        "message": "Scope test T009 — automated post via Cocreatiq [DELETE ME]",
        "access_token": page_token
    }
)
post_id = r.json()["id"]
assert "_" in post_id  # Format: {page_id}_{post_id}
FB_TEST_POST_ID = post_id  # Save for later tests
```

**Expected:** Response `{id: "286679221188150_xxx"}`.
**Cleanup:** Keep post alive for T015-T017, delete in T011.

---

### T010 — Post Photo To FB Page

**Scope:** `pages_manage_posts`
**Goal:** Image post (for Marketing Machine visual content).

```python
r = requests.post(
    f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/photos",
    params={
        "url": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1080&h=1080&fit=crop&fm=jpg",
        "caption": "Scope test T010 — photo post [DELETE ME]",
        "access_token": page_token
    }
)
photo_post_id = r.json()["post_id"]
```

**Expected:** `{id: ..., post_id: ...}`.
**Gotcha:** Use direct JPEG URL (no redirects). Picsum fails, Unsplash direct works.

---

### T011 — Delete A Post

**Scope:** `pages_manage_posts`
**Goal:** Confirm we can clean up programmatically.

```python
r = requests.delete(
    f"https://graph.facebook.com/v22.0/{FB_TEST_POST_ID}",
    params={"access_token": page_token}
)
assert r.json().get("success") is True
```

**Expected:** `{success: true}`. Post disappears from Page.

---

## Group D — Instagram Write Operations

### T012 — Create IG Media Container

**Scope:** `instagram_content_publish`
**Goal:** Step 1 of IG's 2-step publish flow.

```python
r = requests.post(
    f"https://graph.facebook.com/v22.0/{IG_BUSINESS_ID}/media",
    params={
        "image_url": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1080&h=1080&fit=crop&fm=jpg",
        "caption": "Scope test T012 #VibeCreator [DELETE ME]",
        "access_token": page_token
    }
)
creation_id = r.json()["id"]
IG_CREATION_ID = creation_id  # Pass to T013
```

**Expected:** `{id: "<creation_id>"}`.
**Gotcha:** Image MUST be direct JPEG. `.jpg` extension required in URL. No redirects.

---

### T013 — Publish IG Media Container

**Scope:** `instagram_content_publish`
**Goal:** Step 2 — promote container to live feed.

```python
r = requests.post(
    f"https://graph.facebook.com/v22.0/{IG_BUSINESS_ID}/media_publish",
    params={"creation_id": IG_CREATION_ID, "access_token": page_token}
)
ig_post_id = r.json()["id"]
IG_TEST_POST_ID = ig_post_id  # Save for cleanup
```

**Expected:** `{id: "<ig_post_id>"}`. Post appears on @anthonytbattle feed.

---

### T014 — Delete IG Post (Best-Effort)

**Scope:** `instagram_manage_contents` (note: may need Advanced Access)
**Goal:** Attempt programmatic cleanup. If blocked, log + delete via IG UI.

```python
r = requests.delete(
    f"https://graph.facebook.com/v22.0/{IG_TEST_POST_ID}",
    params={"access_token": page_token}
)
# Expected: {success: true} OR permission error (log + manual cleanup)
if r.status_code != 200:
    print(f"IG delete failed: {r.json()}. Manual cleanup required.")
```

**Expected:** May fail if `instagram_manage_contents` wasn't granted or isn't Advanced. Log result.

---

## Group E — Comment Engagement (Click to Client Core)

### T015 — Read Comments On A Post

**Scope:** `pages_read_user_content`, `pages_read_engagement`
**Goal:** Confirm we can detect new comments (trigger for auto-reply).

**Setup:** Before this test runs, manually post a comment on `FB_TEST_POST_ID` from another account (Anthony's personal account works).

```python
r = requests.get(
    f"https://graph.facebook.com/v22.0/{FB_TEST_POST_ID}/comments",
    params={"fields": "id,from,message,created_time", "access_token": page_token}
)
comments = r.json()["data"]
assert len(comments) >= 1
COMMENT_ID = comments[0]["id"]  # For next test
```

**Expected:** Array of comment objects with id, from, message.
**Gotcha:** `from` field requires app to be in Live Mode for non-admin commenters — Dev Mode only returns admin commenters.

---

### T016 — Reply To A Comment

**Scope:** `pages_manage_engagement`
**Goal:** Automated reply (the "thanks! sending you a DM" step in Click to Client).

```python
r = requests.post(
    f"https://graph.facebook.com/v22.0/{COMMENT_ID}/comments",
    params={
        "message": "Scope test T016 — automated reply! Check your DMs 📩",
        "access_token": page_token
    }
)
reply_id = r.json()["id"]
```

**Expected:** `{id: ...}` for the reply comment.

---

### T017 — Hide/Delete Inappropriate Comment (Moderation)

**Scope:** `pages_manage_engagement`
**Goal:** Confirm comment moderation works (for spam / abuse filtering).

```python
# Hide (recommended — non-destructive):
r = requests.post(
    f"https://graph.facebook.com/v22.0/{COMMENT_ID}",
    params={"is_hidden": "true", "access_token": page_token}
)
assert r.json().get("success") is True

# Unhide for cleanup:
requests.post(
    f"https://graph.facebook.com/v22.0/{COMMENT_ID}",
    params={"is_hidden": "false", "access_token": page_token}
)
```

---

## Group F — Messenger

### T018 — Send DM (Requires Prior Incoming Message)

**Scope:** `pages_messaging`
**Goal:** Send DM to a user (auto-DM after they engage).

**Setup:** Meta requires the user to have messaged the Page within 24 hours OR the Page to use a message tag for specific use cases. Simplest path: have Anthony DM the Page first from his personal account, then run test within 24h.

```python
# PSID = Page-Scoped User ID of the incoming messenger
PSID = "<capture from an incoming message webhook or inbox>"
r = requests.post(
    f"https://graph.facebook.com/v22.0/me/messages",
    json={
        "recipient": {"id": PSID},
        "message": {"text": "Scope test T018 — automated DM from Cocreatiq."},
        "messaging_type": "RESPONSE"
    },
    params={"access_token": page_token}
)
assert "message_id" in r.json()
```

**Expected:** `{message_id: ...}`.
**Gotcha:** `messaging_type: RESPONSE` only works within 24h window. Use tags (`HUMAN_AGENT`, `CONFIRMED_EVENT_UPDATE`) for longer windows.

---

## Group G — Click to Client E2E (The Real Test)

### T019 — Auto-Detect + Auto-Reply Loop

**Scope:** Multiple (`pages_read_user_content`, `pages_manage_engagement`, `pages_messaging`)
**Goal:** Automated end-to-end comment → reply → DM flow.

**Scenario:**
1. Post created by Marketing Machine (reuse post from T009 or create new)
2. Someone comments with keyword trigger (e.g., "interested")
3. Bot detects comment (poll or webhook)
4. Bot replies to comment publicly
5. Bot sends private DM with nurture message + Calendly link

**Pseudo-flow for tech session:**
```python
def click_to_client_demo(post_id, page_token):
    # Poll for new comments (or use webhook in production)
    comments = fetch_new_comments(post_id, page_token)
    for comment in comments:
        if has_trigger_keyword(comment["message"]):
            # Step 1: Public reply
            reply_to_comment(comment["id"], "Check your DMs! 📩", page_token)
            # Step 2: Send DM (requires user to be messagable)
            send_dm(comment["from"]["id"], nurture_message(), page_token)
            # Step 3: Log lead
            log_lead(comment["from"], source="fb_page_comment")
```

**Expected:** Full flow completes in <5 seconds. Lead logged to database/CRM.
**Gotcha:** Dev Mode restriction — `from` field only returns admin users. E2E test requires admin account to play the "prospect" role until we hit Live Mode.

---

### T020 — IG Version Of Click To Client

**Scope:** `instagram_manage_comments`, `instagram_manage_messages` (if granted)
**Goal:** Same as T019 but for IG.

**Gotcha:** `instagram_manage_messages` may not be in our current granted set. Check before testing. If not granted, note as a gap and queue for next OAuth re-auth.

---

## Test Report Template

At end of test run, produce `test_report_YYYYMMDD.md` with:

```markdown
# FB/IG Scope Test Report — YYYY-MM-DD

## Summary
- Total tests: 20
- Passed: X
- Failed: Y
- Blocked: Z (missing scope, admin-only restriction, etc.)

## Per-Test Results
| Test | Status | Duration | Notes |
|---|---|---|---|
| T001 | ✅ Pass | 320ms | — |
| T002 | ✅ Pass | 450ms | — |
| ... | | | |

## Gaps Identified
- [ ] instagram_manage_messages not granted — need re-auth
- [ ] etc.

## Cleanup Confirmed
- [ ] T009 post deleted
- [ ] T010 photo deleted
- [ ] T012/T013 IG post deleted (manually if T014 failed)
- [ ] T016 reply deleted
- [ ] T017 hidden comment unhidden
```

## Known Gotchas (Reference)

See `memory/reference_meta_graph_api_gotchas.md` for full list:
- Page Token derivation pattern
- IG image URL no-redirect rule
- User vs Page token confusion
- Empty `/me/accounts` workaround
- Scope name variants (`_business_` vs non)
- Invalid scopes block OAuth entirely

## Success Criteria (Overall)

**Pass:** 18+ of 20 tests pass. Any failures must be either:
- Known scope gap (documented, not blocker for Phase 1)
- Dev Mode restriction (will resolve at Live Mode)
- External dependency (Anthony needs to DM the Page first for T018)

**Fail:** Any failure in T009, T012, T013, T016, or T019 — these are the Marketing Machine core capabilities.

## Next Actions After Tests Pass

1. Mark `project_meta_app_cocreatiq.md` status as "Code-tested, production-ready"
2. Deploy `facebook_publisher.py` + `instagram_publisher.py` to production
3. Begin content batching for Anthony (30-40 videos + 10-15 images + 20-30 text)
4. Start Twitter OAuth integration (parallel)
5. Schedule first real 3-post day for Anthony's Page + IG

## Next Actions If Tests Fail

1. Document specific failure in `test_report_YYYYMMDD.md`
2. Classify: scope gap, code bug, infrastructure issue
3. If scope gap → add to Meta Dashboard + re-auth Nango
4. If code bug → fix before scaling to other platforms
5. If infra issue → check Nango logs, Meta App status
