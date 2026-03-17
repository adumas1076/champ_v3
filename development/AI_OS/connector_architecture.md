# CHAMP OS — Connector Architecture

## Date: 2026-03-16
## Contributors: Anthony (vision), Champ (framework), Claude (mapping)

---

## The Principle

**"The more meaningful connectors, the more valuable the OS."**

But value comes from outcomes, not raw count. Each connector should answer:
"What can the operator DO now that they couldn't before?"

---

## Connector Categories

### Layer 1 — Identity (Get In)
| Connector | Purpose |
|-----------|---------|
| Google Sign-In | Login, workspace identity, permissions base |
| Microsoft Sign-In | Enterprise identity |
| GitHub | Developer identity |

### Layer 2 — Communication (Talk to the World)
| Connector | Purpose |
|-----------|---------|
| Gmail | Read, send, search, draft emails |
| WhatsApp | Direct messaging, business messaging |
| Telegram | Messaging, bots, channels |
| Slack | Team communication |
| SMS/Twilio | Text messaging |

### Layer 3 — Social & Content (Be Seen)
| Connector | Purpose |
|-----------|---------|
| Facebook | Posts, pages, messenger |
| Instagram | Content, stories, DMs |
| X (Twitter) | Posts, engagement, DMs |
| TikTok | Content, analytics |
| YouTube | Upload, manage, analytics |
| LinkedIn | Professional content, networking |

### Layer 4 — Ads & Revenue (Make Money)
| Connector | Purpose |
|-----------|---------|
| Meta Ads Manager | Facebook/Instagram ad campaigns |
| Google Ads | Search/display campaigns |
| TikTok Ads | Video ad campaigns |
| Stripe | Payments, invoices, subscriptions |
| Shopify | E-commerce, products, orders |
| GoHighLevel | CRM, funnels, automation |

### Layer 5 — Creator Mode (Make Content)
| Connector | Purpose |
|-----------|---------|
| Text-to-Image | Generate images from prompts (DALL-E, Midjourney, Flux) |
| Image-to-Video | Animate images into video (Runway, Pika, Kling) |
| Text-to-Video | Generate video from text |
| Text-to-Speech | Custom voices (ElevenLabs) |
| Image Editor | Background removal, upscaling, editing |
| Thumbnail Generator | YouTube/social thumbnails |
| Caption Generator | Auto-captions for video |

### Layer 6 — Productivity (Get Organized)
| Connector | Purpose |
|-----------|---------|
| Google Calendar | Scheduling, events, reminders |
| Google Drive | Documents, sheets, storage |
| Notion | Internal docs, wikis, databases |
| Linear | Project/issue tracking |
| Dropbox | File storage |

### Layer 7 — Intelligence (Think Deeper)
| Connector | Purpose |
|-----------|---------|
| OpenAI | GPT models, DALL-E, Whisper |
| Anthropic | Claude models |
| Google AI | Gemini models |
| ElevenLabs | Voice generation/cloning |
| Firecrawl | Web scraping, search, retrieval |
| Vector DBs | Semantic search, RAG |

### Layer 8 — Action (Do Work)
| Connector | Purpose |
|-----------|---------|
| Browser Automation | Browse, click, fill forms, scrape |
| Desktop Automation | Control any app, keyboard, mouse |
| Webhook | Send/receive from any API |
| File System | Read, write, organize local files |
| Code Execution | Run Python, JavaScript, shell |

---

## Connector Framework Spec

Every connector must define:

```
name: "Gmail"
category: "communication"
auth_type: "oauth2" | "api_key" | "token"
scopes: ["read", "send", "search", "draft"]
actions:
  - gmail.read: "Read emails matching criteria"
  - gmail.send: "Send email to recipient"
  - gmail.search: "Search inbox"
  - gmail.draft: "Create draft"
triggers:
  - gmail.new_email: "When new email arrives"
status: "enabled" | "disabled" | "not_configured"
icon: "/connectors/gmail/icon.svg"
```

---

## Permission Layer (Per Operator)

| Operator | Allowed Connectors |
|----------|-------------------|
| Champ | All (personal creative partner) |
| Billy | Stripe, Gmail (billing), Shopify |
| Sadie | Calendar, Gmail, Slack (executive assistant) |
| Genesis | WhatsApp, SMS, GoHighLevel (sales) |

Operators get **capabilities**, not vague app access:
- Billy can `stripe.invoice.create` but NOT `stripe.refund`
- Sadie can `calendar.book` but NOT `gmail.send` to clients

---

## Build Priority (Champ's Phased Approach)

### Phase 1 — Foundation (MVP)
- Google Sign-In
- Gmail
- Google Calendar
- Google Drive

**Why:** Identity + communication + documents + scheduling. Enough to feel real.

### Phase 2 — Business Value
- Stripe
- Shopify
- Slack
- WhatsApp

**Why:** Money, commerce, team comms, direct messaging. Now it's useful for business.

### Phase 3 — Creator Mode
- Text-to-Image (DALL-E / Flux)
- Image-to-Video (Runway / Kling)
- ElevenLabs (custom voices)
- Thumbnail/caption generators

**Why:** This is where CHAMP becomes a creative operator system. Content creation from voice commands.

### Phase 4 — Social & Ads
- Facebook / Instagram
- X / TikTok / YouTube
- Meta Ads Manager
- Google Ads

**Why:** Distribution. Create content → post it → run ads → track performance. Full loop.

### Phase 5 — Execution & Scale
- Browser automation (already built)
- Desktop automation (already built)
- Webhook connector
- Custom connector builder (let users add their own)

---

## The Car Analogy (Extended)

| Part | What It Is |
|------|-----------|
| OS | The car platform |
| AI models | The engine |
| Operators | The drivers |
| Apps/UI | Dashboard and cabin |
| **Connectors** | **The wiring harness and ports that let the car talk to the outside world** |

Without connectors, the car is isolated.
With connectors, it becomes part of the driver's real environment.

---

## What CHAMP Already Has (V3)

| Category | Connector | Status |
|----------|-----------|--------|
| Action | Browser automation (stealth) | Working |
| Action | Desktop automation | Working |
| Action | Code execution | Working |
| Action | File creation | Working |
| Intelligence | OpenAI (Realtime) | Working |
| Intelligence | Claude (via LiteLLM) | Working |
| Intelligence | Gemini (via LiteLLM) | Working |
| Productivity | Supabase (memory) | Working |
| Communication | Voice (LiveKit) | Working |
| Communication | Text chat | Needs transcription fix |

**10 connectors already built.** The foundation is there.

---

## UI — Connector Settings Page

Based on Lovable's pattern:
- Grid of connector cards
- Each card: icon + name + description + "Enabled" badge
- Click to configure (API key, OAuth, permissions)
- Toggle on/off per operator
- "View all" to see full catalog

---

## The Positioning

Don't market: "We have 50 integrations"

Market: **"Your operators can plug into the tools your business already runs on."**

Value = outcomes, not count.
