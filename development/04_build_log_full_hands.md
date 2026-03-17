# Build Log: Full Hands — Desktop Control + Stealth Browser

> Upgrading CHAMP's Hands from sandboxed headless Puppeteer to full desktop
> control + undetectable real browser automation.

*Started: March 15, 2026*

---

## Why This Upgrade

Current Hands (Puppeteer) can only control a hidden browser. It can't:
- Use the user's real browser (with saved logins, cookies, sessions)
- Control desktop apps (Excel, Slack, Spotify, File Explorer)
- Pass anti-bot detection on protected sites
- Sign up / log into services without getting flagged

Full Hands solves all of this. No secondary browser. No bot fingerprint.
CHAMP uses the computer exactly like the user does.

---

## What Changes

| Before (Puppeteer) | After (Full Hands) |
|---|---|
| Hidden headless browser | User's real Chrome/Edge |
| Gets flagged as bot | Undetectable — 98.7% bypass |
| Web pages only | Any app on the computer |
| Needs API integrations per service | Zero integrations — if it's on screen, CHAMP uses it |
| Separate browser sessions | User's real logged-in sessions |
| Can't touch desktop | Full mouse, keyboard, any window |

---

## The Three Reference Builds

### 1. Cua (Computer-Use Agents)
- **Repo:** `reference/cua-main/`
- **Source:** https://github.com/trycua/cua
- **What:** Full infrastructure for AI agents that control computers
- **How:** Agent receives screenshots → decides action → executes mouse/keyboard → loops
- **Key:** Multi-platform SDK, sandboxed + native modes, benchmarking tools
- **Use for CHAMP:** Architecture patterns, SDK design, agent loop structure
- **Stack:** Python 3.12+, Node.js (CLI)
- **License:** Open source

### 2. Stealth Browser MCP
- **Repo:** `reference/stealth-browser-mcp-main/`
- **Source:** https://github.com/vibheksoni/stealth-browser-mcp
- **What:** MCP server for undetectable browser automation
- **How:** Uses `nodriver` + Chrome DevTools Protocol to control real installed browser
- **Key:** 90 tools, 98.7% bypass rate, MCP compatible, human-like typing
- **Use for CHAMP:** Replace Puppeteer for all browser tasks. Plugs into OS via MCP.
- **Stack:** Python, FastMCP, Chrome DevTools Protocol
- **License:** Open source
- **Critical feature:** Connects to YOUR installed Chrome/Edge — not a secondary browser

### 3. PyWinAssistant
- **Repo:** `reference/pywinassistant-main/`
- **Source:** https://github.com/a-real-ai/pywinassistant
- **What:** Windows-native AI desktop control via natural language
- **How:** Uses Windows UI Automation APIs to read/control any GUI element
- **Key:** No screenshots needed — reads UI tree directly. Self-healing workflows.
- **Use for CHAMP:** Desktop app control (Excel, Slack, Spotify, File Explorer, etc.)
- **Stack:** Python, Windows Win32 API, OpenAI (swap to LiteLLM)
- **License:** MIT
- **Critical feature:** Controls actual apps on actual screen — not a sandbox

---

## How They Stitch Together

```
User says: "Research competitors and make me a spreadsheet"

CHAMP Brain receives command
  |
  v
Stealth Browser MCP
  → Opens user's real Chrome
  → Searches Google (user's account, no bot flag)
  → Visits 10 competitor sites
  → Extracts data
  → Returns to Brain
  |
  v
PyWinAssistant
  → Opens Excel on desktop
  → Creates spreadsheet
  → Pastes organized data
  → Formats columns
  → Saves to Desktop
  |
  v
Brain responds via Voice:
  "Done. Spreadsheet is on your Desktop."
```

---

## Architecture (OS Level)

These are OS-level capabilities, not operator-level:

```
OS Layer: Hands (upgraded)
├── Stealth Browser MCP     → Web (real browser, undetectable)
├── PyWinAssistant           → Desktop apps (Windows native)
├── Puppeteer (legacy)       → Fallback / headless tasks
└── Cua patterns             → Agent loop, sandboxing, benchmarks

Every operator (Champ, Billy, Sadie, Genesis) uses the same Hands.
Operators decide WHAT to do. The OS decides HOW.
```

---

## Security Considerations

Full desktop control is powerful but risky. Before deployment:

1. **Confirmation gates** — Sensitive actions (purchases, sending messages,
   deleting files) require user approval before execution
2. **Action logging** — Every mouse click, keystroke, and navigation is logged
3. **Domain whitelist** — Optional: restrict which sites/apps the agent can touch
4. **Undo buffer** — Track recent actions so mistakes can be reversed
5. **Kill switch** — Instant stop via hotkey or voice command ("Stop everything")

---

## Integration Steps (When Ready)

### Step 1: Stealth Browser MCP (replace Puppeteer)
- [ ] Install stealth-browser-mcp as MCP server
- [ ] Configure to use user's installed Chrome
- [ ] Update Brain's tool calls to use MCP instead of Puppeteer
- [ ] Test: Google search, login to a protected site, fill a form
- [ ] Gate test: bypass rate on Cloudflare-protected site

### Step 2: PyWinAssistant (add desktop control)
- [ ] Install PyWinAssistant
- [ ] Swap OpenAI dependency to LiteLLM (port 4001)
- [ ] Wire as Brain tool: `desktop_action(instruction)`
- [ ] Test: open Notepad, type text, save file
- [ ] Test: open Excel, create spreadsheet, format, save
- [ ] Gate test: 10 desktop tasks end-to-end

### Step 3: Combined workflows
- [ ] Test: browser research → desktop app output
- [ ] Test: voice command → browser + desktop → voice confirmation
- [ ] Add confirmation gates for sensitive actions
- [ ] Add action logging

### Step 4: Cua patterns (architecture hardening)
- [ ] Study Cua's agent loop for error recovery
- [ ] Implement sandbox mode toggle (safe mode vs full control)
- [ ] Add benchmarking from cua-bench

---

## What This Enables

When complete, CHAMP can do anything a human can do on a computer:

- Browse any website undetected, using real logged-in sessions
- Control any desktop application
- Chain web + desktop tasks in a single workflow
- Sign up, log in, purchase, message — all without bot detection
- Zero integrations needed — the screen IS the integration layer

**No API keys per service. No OAuth flows. No "supported integrations" list.
If it's on your screen, CHAMP can use it.**

---

*Build status: RESEARCH PHASE — reference repos cloned, architecture documented*
*Next: UI wiring (in progress), then Step 1 when ready*
