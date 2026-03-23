# AIOSCP — AI Operating System Connector Protocol

## Date: 2026-03-17
## Status: Concept / Pre-Spec
## Contributors: Anthony (vision), Champ (framework), Claude (reasoning)

---

## One-Sentence Definition

**AIOSCP is the protocol that turns a collection of AI tools into a functioning operating system — by standardizing how capabilities install, how operators use them, how permissions scope them, how channels route them, and how memory persists across all of it.**

---

## The Full Definition

**AIOSCP as the** ***standard that unifies all AI protocols into one operating system*** **to do** ***what no single protocol can do alone — give operators a complete environment to think, act, remember, communicate, and collaborate across any tool, any channel, and any other operator.***

**AIOSCP doesn't exist for the tools. It doesn't exist for the protocols. It exists for the operator.** The operator is the resident. AIOSCP is the building they live in.

---

## The Protocol Landscape (What Exists Today)

| Protocol | Creator | What It Does | What It DOESN'T Do |
|----------|---------|-------------|-------------------|
| **MCP** | Anthropic | AI connects to **tools** (functions, data, APIs). Universal plug for tool discovery + calling | No agent identity, no agent-to-agent, no memory, no channels, no permissions |
| **A2A** | Google | **Agent-to-agent** communication. Agents discover each other, exchange tasks, collaborate | No tool calling (that's MCP's job), no OS-level management, no channels |
| **REST API** | Industry standard | Any service talks to any service via HTTP | No AI-native features, no discovery, stateless |
| **OAuth 2.0** | Industry standard | Authentication + authorization | Only auth — no tools, no agents, no memory |
| **OpenAPI** | Industry standard | Describes what an API does (Swagger) | No AI-native features, just documentation |
| **GraphQL** | Meta | Flexible data querying | Query language only, no agent features |

### How They Fit Together

```
MCP   = AI ↔ Tools         (what can I use?)
A2A   = Agent ↔ Agent      (who can I work with?)
OAuth = User ↔ Service     (am I allowed in?)
API   = Service ↔ Service  (how do I call you?)
```

### What Each Protocol Gives the OPERATOR

| Protocol | What It Gives the OPERATOR |
|----------|--------------------------|
| MCP | Tools to **USE** |
| A2A | Other operators to **COLLABORATE** with |
| OAuth | Permission to **ACCESS** services |
| REST API | Services to **CALL** |
| **AIOSCP** | **The OS to LIVE in** |

### The Gap — What NOBODY Has

| Need | Who Covers It? |
|------|---------------|
| Tool discovery + calling | MCP |
| Agent-to-agent collaboration | A2A |
| Authentication | OAuth |
| API communication | REST/GraphQL |
| **OS-level operator management** | **NOBODY** |
| **Memory persistence across sessions** | **NOBODY** |
| **Channel routing (voice/text/email)** | **NOBODY** |
| **Permission scoping per operator** | **NOBODY** |
| **Connector installation + lifecycle** | **NOBODY** |
| **Service health + self-healing** | **NOBODY** |

---

## What AIOSCP Steals From Each Protocol

| Protocol | What AIOSCP Should Take |
|----------|------------------------|
| **MCP** | Tool manifest format (JSON), auto-discovery, "install once works everywhere" |
| **A2A** | Agent Cards (JSON capability advertisement), task lifecycle, async handoffs |
| **OAuth** | Scoped permissions, token vault, refresh flow |
| **REST** | HTTP-based, works with existing infrastructure |
| **OpenAPI** | Self-documenting specs that tools can read |

**AIOSCP = MCP's tool calling + A2A's agent collaboration + OAuth's auth + the OS layer nobody built.**

---

## Why It Needs to Exist

Without AIOSCP, an operator is just a persona file with no home. With AIOSCP, the operator has:

- **A brain** (AI models routed through LiteLLM)
- **Hands** (tools via MCP)
- **Teammates** (other operators via A2A)
- **Memory** (persistent state)
- **A voice** (channels — voice, text, email, SMS)
- **Keys to the building** (permissions via OAuth)
- **A desk that's always there** (the OS shell)

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

MCP sits INSIDE AIOSCP. A2A sits INSIDE AIOSCP. OAuth sits INSIDE AIOSCP.
AIOSCP is the house they all live in.

### The Dr. Frankenstein Play

```
AIOSCP (your layer)
├── Uses MCP for tool calling
├── Uses A2A for agent-to-agent handoffs
├── Uses OAuth for connector authentication
├── Uses REST APIs for service communication
└── ADDS what's missing:
    ├── Operator identity + permissions
    ├── Memory persistence
    ├── Channel routing
    ├── Connector lifecycle
    └── Service management
```

MCP is a piece. A2A is a piece. OAuth is a piece. API is a piece.
**AIOSCP is the OS that wires them all together into one functioning system.**

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
