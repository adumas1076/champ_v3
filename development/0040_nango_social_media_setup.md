# 0040 — Nango Social Media OAuth Setup (Step by Step)
**Date:** 2026-04-15
**Category:** Marketing Machine — OAuth Infrastructure
**Status:** In progress
**Mode:** Nango Cloud (NOT self-hosted Docker)

---

## Why Cloud, Not Docker

Tried `docker compose up -d` from `reference/nango/` — Docker Desktop wouldn't start on Windows. Switched to Nango Cloud (https://app.nango.dev) instead. Free tier covers our volume. No Docker maintenance, no callback URL tunneling needed (cloud has public HTTPS by default).

---

## Configuration in `.env`

```bash
# --- Nango Cloud (https://app.nango.dev) ---
NANGO_BASE_URL=https://api.nango.dev
NANGO_SECRET_KEY=4388fe4e-77c5-4f66-88f1-997003d6410b
```

**Universal OAuth callback URL (paste into every social media app):**
```
https://api.nango.dev/oauth/callback
```

---

## Connection ID Naming Convention

Every OAuth connection follows this pattern:
```
{provider}-{influencer_id}
```

Examples:
- `twitter-anthony`
- `instagram-influencer_1`
- `linkedin-anthony`
- `tiktok-influencer_2`

The publishers' `nango_adapter.py` builds these IDs automatically.

---

## Setup Order (4 platforms × 4 faces = 16 connections)

### Phase 1: Anthony Only (Wednesday MVP)
Get Anthony's clone connected to all 4 platforms first. Prove the loop works. Then add the 3 AI faces.

| Step | Platform | Connection ID |
|------|----------|--------------|
| 1 | Facebook (Anthony's FB Page) | `facebook-anthony` |
| 2 | Instagram (Anthony's IG Business) | `instagram-anthony` |
| 3 | Twitter/X (Anthony's @) | `twitter-anthony` |
| 4 | LinkedIn (Anthony's profile) | `linkedin-anthony` |
| 5 | TikTok (Anthony's TikTok) | `tiktok-anthony` |

### Phase 2: AI Faces (Week 2)
Repeat Steps 1-5 for `influencer_1`, `influencer_2`, `influencer_3`. **Skip LinkedIn for AI faces** (LinkedIn bans synthetic profiles).

---

## The Universal 5-Step Process Per Platform

### Step 1: Create OAuth App in Platform's Developer Portal
Each platform has its own dev portal. Fill in:
- **App Name:** Cocreatiq OS (or per-influencer like "Cocreatiq — Anthony")
- **Website:** https://cocreatiq.com
- **Redirect URI:** `https://api.nango.dev/oauth/callback`

Get back: **Client ID** + **Client Secret**

### Step 2: Add Integration in Nango Dashboard
1. Go to https://app.nango.dev
2. Left sidebar → **Integrations** → **Configure New Integration**
3. Pick provider from dropdown (twitter, facebook, instagram, linkedin, tiktok)
4. Paste **Client ID** + **Client Secret**
5. Set **Scopes** (Nango shows defaults — usually fine)
6. Save

### Step 3: Connect the Account
1. In Nango Dashboard → **Connections** → **Add Connection**
2. Pick the integration you just made
3. Set **Connection ID** = `{provider}-{influencer_id}` (e.g., `twitter-anthony`)
4. Click **Authorize**
5. Login as that influencer's account on the platform
6. Approve permissions
7. Connection saved → token auto-refreshes forever

### Step 4: Verify in Code
```python
from content_engine.publishers.nango_adapter import check_connection
import asyncio

result = asyncio.run(check_connection("twitter", "anthony"))
print(f"Twitter connected: {result}")
```

### Step 5: Test Post
Once verified, the publisher can post immediately. No code changes needed.

---

## Platform-Specific Notes

### Facebook + Instagram (Same Meta App)
- ONE Meta app handles both
- IG account MUST be Business or Creator type
- IG MUST be linked to a Facebook Page
- Page Token serves both FB and IG endpoints
- Manual fallback already in `.env` (FACEBOOK_PAGE_ACCESS_TOKEN, INSTAGRAM_ACCESS_TOKEN) — works without Nango but needs 60-day refresh

### Twitter/X
- OAuth 1.0a (not OAuth 2.0)
- Free tier: 17 tweets/24hr — fine for our 3/day limit
- Need Twitter Developer account (apply at developer.x.com)

### LinkedIn
- OAuth 2.0 with member permissions
- Bans AI-generated personas — Anthony only, NOT for AI faces
- Need LinkedIn Developer account + app approval for `w_member_social` scope

### TikTok
- OAuth 2.0
- **Unaudited apps post PRIVATE only** — must submit for audit (~7 days review)
- Needs TikTok for Developers account

---

## Status Tracking

| Platform | Anthony | Inf 1 | Inf 2 | Inf 3 |
|----------|---------|-------|-------|-------|
| Facebook | ⏳ in progress | — | — | — |
| Instagram | ⏳ in progress | — | — | — |
| Twitter | ⬜ | — | — | — |
| LinkedIn | ⬜ | ❌ skip | ❌ skip | ❌ skip |
| TikTok | ⬜ | — | — | — |

Update this as we go.

---

## Lessons (Updated as We Hit Issues)

1. **Docker Desktop on Windows is unreliable** — went straight to Nango Cloud, saved hours
2. **PowerShell doesn't use `&&`** — use `;` or run commands separately
3. **Nango Cloud secret key is UUID format** (e.g., `4388fe4e-...`)
4. **One callback URL works for all platforms** — `https://api.nango.dev/oauth/callback`
5. **Connection ID convention matters** — must match what `nango_adapter.py` expects: `{provider}-{influencer_id}`