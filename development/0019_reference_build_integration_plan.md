# 0019 — Reference Build Integration Plan (Dr. Frankenstein)
**Date:** 2026-03-29
**Goal:** Harvest working parts from reference builds to enhance Champ as the meta operator

---

## Priority 1: Immediate (This Sprint)

### Karpathy Autoresearch → Content Engine
**Source:** `reference/karpathy-autoresearch/`
**Harvest:**
- Autonomous research loop (search → read → synthesize → repeat)
- Multi-source aggregation pattern
- Quality scoring / relevance filtering
**Wire into:** Marketing operator's autoresearch loop, Self Mode research tasks
**Files to study:** Look for the main research loop, scoring logic, source management

### Karpathy LLM Council → Self Mode Decision Making
**Source:** `reference/karpathy-llm-council/`
**Harvest:**
- Multi-LLM voting/debate pattern
- Consensus scoring
- Disagreement detection
**Wire into:** Self Mode review step (step 5), critical decisions in Brain pipeline
**How:** When Self Mode reviews its own work, run it through 2-3 models and take consensus

### CUA (Computer Use Agent) → Enhanced Desktop Control
**Source:** `reference/cua-main/`
**Harvest:**
- Structured computer use patterns (click, type, scroll, wait)
- Screen understanding (element detection, layout parsing)
- Action planning (break complex UI tasks into steps)
**Wire into:** `hands/desktop.py`, `tools.py` (control_desktop, analyze_screen)
**How:** Replace simple pyautogui calls with structured action planning

### pywinassistant → Better Windows Automation
**Source:** `reference/pywinassistant-main/`
**Harvest:**
- Windows UI element tree parsing
- Smart element finding (by name, type, state)
- Accessibility API integration
**Wire into:** `hands/desktop.py` (enhance `get_ui_elements`, `desktop_action`)
**Note:** This IS partially wired — desktop.py uses pyautogui. Upgrade to use UI Automation APIs.

### Stealth Browser MCP → Browser Upgrade
**Source:** `reference/stealth-browser-mcp-main/`
**Harvest:**
- MCP protocol for browser control
- Better anti-detection patterns
- Session persistence
**Wire into:** `hands/stealth_browser.py`
**How:** Upgrade existing stealth browser with MCP patterns if useful

---

## Priority 2: Next Sprint

### OpenClaw → Multi-Operator Orchestration
**Source:** `reference/openclaw-main/`
**Harvest:**
- Agent orchestration patterns
- Task delegation between agents
- Shared context management
**Wire into:** `operators/registry.py`, A2A messaging
**How:** Enable Champ to delegate tasks to specialized operators

### Chatwoot → Channel Adapters
**Source:** `reference/chatwoot/`
**Harvest:**
- Webhook-based channel integration
- Multi-channel inbox pattern
- Message normalization (different platforms → unified format)
**Wire into:** `channels/adapters/` (build Telegram, WhatsApp, Slack adapters)
**How:** Each adapter implements the ChannelAdapter base class

### Typebot → Embeddable Chat Widget
**Source:** `reference/typebot/`
**Harvest:**
- Embeddable chat widget (JavaScript snippet)
- Conversation flow state machine
- Theme customization
**Wire into:** Frontend (embeddable version), marketing site
**How:** Build a lightweight chat widget that can be embedded anywhere via `<script>` tag

### Twenty CRM → Sales/Lead Gen Data
**Source:** `reference/twenty-crm/`
**Harvest:**
- Contact/company data models
- Pipeline stages
- Activity tracking
**Wire into:** Sales operator, Lead Gen operator, Supabase tables
**How:** Add CRM tables to Supabase, wire into Sales/Lead Gen operator tools

### Postiz → Social Media Scheduling
**Source:** `reference/postiz/`
**Harvest:**
- Multi-platform posting (YouTube, Instagram, LinkedIn, Twitter, TikTok)
- Scheduling queue
- Analytics pull
**Wire into:** Content Engine (Phase 3), Marketing operator
**How:** Build a `post_content` tool that schedules posts

---

## Priority 3: Later

### Resonance → Self-Hosted TTS
**Source:** `reference/resonance/` + `reference/resonance-fresh/`
**Harvest:**
- Chatterbox TTS model
- Voice cloning pipeline
- Modal GPU deployment pattern
**Wire into:** Replace ElevenLabs with self-hosted TTS
**When:** After ElevenLabs subscription expires
**Needs:** GPU server (Hetzner GPU or Modal)

### LiveKit LiveAvatar → Real-Time Avatar
**Source:** `reference/livekit-liveavatar/`
**Harvest:**
- Real-time lip sync from audio
- Avatar rendering pipeline
- LiveKit video track integration
**Wire into:** Voice call page (replace static image)
**When:** After GPU server is available
**Needs:** GPU server

### Friday Jarvis → Wake Word
**Source:** `reference/friday_jarvis-main/`
**Harvest:**
- Custom wake word training pipeline
- OpenWakeWord integration
- Always-listening architecture
**Wire into:** Ears system (Phase 4)
**Target:** Custom "yo champ" wake word

### Mem0 → Memory Optimization
**Source:** `reference/mem0/`
**Harvest:**
- Advanced memory retrieval patterns
- Memory consolidation
- Cross-session context
**Wire into:** `mind/mem0_memory.py` (already integrated, optimize)

### Hermes Agent → Agent Patterns
**Source:** `reference/hermes-agent/`
**Harvest:**
- Agent tool use patterns
- Structured output handling
**Wire into:** General operator patterns

### Puppeteer → Browser Automation
**Source:** `reference/puppeteer-main/`
**Harvest:**
- Headless browser patterns (if needed beyond stealth browser)
**Wire into:** Backup browser option

### N8NClaw → Workflow Automation
**Source:** `reference/n8nclaw-main/`
**Harvest:**
- Visual workflow patterns
- Trigger-based automation
**Wire into:** Self Mode templates, operator workflows

### GStack → Google Workspace
**Source:** `reference/gstack/`
**Harvest:**
- Google Workspace API patterns
- Gmail, Calendar, Drive integration
**Wire into:** Connectors (Phase 2.3)

### Antonio → Agent Patterns
**Source:** `reference/antonio/`
**Harvest:**
- Agent conversation patterns
**Wire into:** General operator improvement

---

## Integration Rules (AST/Dr. Frankenstein)

1. **Never build from scratch** — find the working part in the reference build first
2. **Copy the pattern, not the code** — adapt to CHAMP's architecture
3. **Test each integration independently** — don't wire 5 things at once
4. **Session isolation** — each integration gets its own session/branch
5. **Extract the lesson** — document what worked and what didn't

---

## The Line

**Sprint 1 (now):** Autoresearch + LLM Council + CUA + pywinassistant + stealth browser
**Sprint 2 (next):** OpenClaw + Chatwoot + Typebot + Twenty CRM + Postiz
**Sprint 3 (later):** Resonance TTS + LiveAvatar + Wake Word + everything else
