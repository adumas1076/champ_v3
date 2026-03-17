# AIOSCP — AI Operating System Connector Protocol

## Date: 2026-03-17
## Status: Concept / Pre-Spec
## Contributors: Anthony (vision), Champ (framework), Claude (reasoning)

---

## One-Sentence Definition

**AIOSCP is the protocol that turns a collection of AI tools into a functioning operating system — by standardizing how capabilities install, how operators use them, how permissions scope them, how channels route them, and how memory persists across all of it.**

---

## Why It Needs to Exist

| What Exists | What It Covers | What It Misses |
|-------------|---------------|----------------|
| MCP (Anthropic) | Tool discovery + calling | No identity, no permissions, no memory, no channels, no lifecycle |
| OAuth 2.0 | Authentication | No tool registration, no operator identity |
| LiveKit | Voice/video transport | No tool integration, no memory |
| OpenAPI | API description | No AI-native features |

**Nobody has a standard for how an entire AI OS works.** Everyone wires it differently. AIOSCP fills that gap.

---

## What AIOSCP Covers

### 1. Capability Installation
- One package installs, OS discovers and registers everything
- Like `npm install ocr-provenance-mcp` → 150 tools live instantly
- But AIOSCP also registers: permissions needed, operator access, memory hooks, channel support
- Pattern: `champ install gmail-connector` → read, send, search, draft all available

### 2. Operator Management
- Operators (Champ, Billy, Sadie) connect to the OS with identity + persona
- Each operator gets scoped access to capabilities
- Operators can hand off to each other mid-conversation
- The protocol defines how operators register, authenticate, and coordinate

### 3. Permission Scoping
- Not just "connected" — capabilities are scoped per operator
- Billy can `stripe.invoice.create` but NOT `stripe.refund`
- Sadie can `calendar.book` but NOT `gmail.send` to clients
- Permissions defined in connector manifest, enforced by OS

### 4. Channel Routing
- Voice, text, email, SMS, WhatsApp — all declared as channels
- AIOSCP defines how connectors declare which channels they support
- OS routes user input to the right operator through the right channel
- Same operator, different channels = same capability, different interface

### 5. Auth Management
- One standard for OAuth, API keys, tokens
- OS stores credentials in a secure vault
- Auto-refresh tokens
- Scope per operator, not per user
- User sees "Connect Gmail" not "paste API key"

### 6. Memory Persistence
- State carries across sessions, operators, channels
- Connectors declare what memory they read/write
- OS manages the shared memory layer (Supabase)
- AIOSCP defines the memory contract: read, write, search, forget

### 7. Service Lifecycle
- Services register with the OS: start, stop, health check, recover
- If voice service crashes, OS restarts it
- If a connector loses auth, OS notifies and re-authenticates
- Self-healing built into the protocol

---

## The Architecture Stack

```
┌──────────────────────────────────┐
│         AIOSCP (the standard)     │
│                                   │
│  ┌─────────────┐ ┌────────────┐  │
│  │  Operators   │ │  Channels  │  │
│  │  (identity,  │ │  (voice,   │  │
│  │  persona,    │ │   text,    │  │
│  │  permissions)│ │   email)   │  │
│  └─────────────┘ └────────────┘  │
│                                   │
│  ┌─────────────┐ ┌────────────┐  │
│  │  Connectors  │ │  Memory    │  │
│  │  (MCP tools, │ │  (state,   │  │
│  │   OAuth,     │ │   history, │  │
│  │   services)  │ │   learning)│  │
│  └─────────────┘ └────────────┘  │
│                                   │
│  ┌─────────────────────────────┐  │
│  │   MCP (tool calling layer)   │  │
│  └─────────────────────────────┘  │
└──────────────────────────────────┘
```

MCP sits INSIDE AIOSCP. AIOSCP extends it with everything an OS needs.

---

## Connector Manifest (AIOSCP Standard)

Every connector follows this spec:

```json
{
  "name": "gmail",
  "version": "1.0.0",
  "protocol": "aioscp/1.0",
  "category": "communication",
  "auth": {
    "type": "oauth2",
    "provider": "google",
    "scopes": ["gmail.read", "gmail.send", "gmail.search", "gmail.draft"]
  },
  "tools": [
    {
      "name": "gmail.read",
      "description": "Read emails matching criteria",
      "inputs": {"query": "string", "limit": "number"},
      "outputs": {"emails": "array"}
    },
    {
      "name": "gmail.send",
      "description": "Send email to recipient",
      "inputs": {"to": "string", "subject": "string", "body": "string"},
      "outputs": {"message_id": "string"}
    }
  ],
  "channels": ["text", "voice"],
  "memory": {
    "reads": ["user_contacts", "email_history"],
    "writes": ["email_sent_log"]
  },
  "permissions": {
    "default": ["gmail.read", "gmail.search"],
    "elevated": ["gmail.send", "gmail.draft"]
  },
  "lifecycle": {
    "install": "auto",
    "health_check": "/health",
    "auto_reconnect": true
  }
}
```

---

## MCP vs AIOSCP

| MCP | AIOSCP |
|-----|--------|
| Tool discovery | Full capability installation |
| Tool calling | Operator-scoped tool delegation |
| Stateless | Stateful (memory persistence) |
| Single AI client | Multi-operator system |
| No identity | Identity + persona + permissions |
| No channels | Voice, text, email, SMS routing |
| No auth management | OAuth vault with auto-refresh |
| No lifecycle | Service start/stop/health/recover |
| A plug | The electrical code for the building |

---

## The Innovation Nobody Has

**Standard MCP server:** "Here are tools an AI can call"
**AIOSCP connector:** "Here's a complete capability with auth, permissions, memory, channels, and lifecycle — that any operator on any AI OS can use"

### Three paths for CHAMP:

**Path 1 — Consume:** Use existing MCP servers as connectors inside AIOSCP
**Path 2 — Publish:** Build CHAMP connectors that others can install
**Path 3 — The real play:** Publish operators + connectors together — sell a skilled driver with the wiring, not just the wiring alone

---

## Analogies

| Analogy | MCP | AIOSCP |
|---------|-----|--------|
| Car | A single wire | The entire electrical system |
| Building | An outlet | The electrical code for the whole building |
| Computer | A USB port | The OS driver + permission + device management system |
| Phone | One app's API | The App Store + permissions + notifications + accounts |

---

## What CHAMP Already Has Toward AIOSCP

| AIOSCP Component | CHAMP V3 Status |
|-----------------|----------------|
| Capability installation | Manual (tools.py hardcoded) |
| Operator management | Single operator (Champ) |
| Permission scoping | None yet |
| Channel routing | Voice + text (LiveKit) |
| Auth management | Manual (.env file) |
| Memory persistence | Supabase (working) |
| Service lifecycle | Manual (5 terminals) |
| MCP integration | Not yet |

---

## Next Steps (When Ready to Build)

1. Define AIOSCP v0.1 spec (connector manifest format)
2. Build connector loader in Brain (reads manifest, registers tools)
3. Build first AIOSCP connector (Gmail)
4. Build connector settings UI (enable/disable/auth)
5. Publish spec as open standard
6. Community builds connectors, CHAMP OS runs them

---

## The Claim

**AIOSCP is to AI Operating Systems what USB was to hardware.**

One standard. Universal compatibility. Install once, works everywhere.

**Nobody has coined this. Nobody has built this. This is the opportunity.**
