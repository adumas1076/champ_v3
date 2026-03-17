# CHAMP OS — Installation Experience Architecture

## Date: 2026-03-16
## Contributors: Anthony (vision), Champ (framework), Claude (mapping)

---

## The One-Sentence Vision

**"You are not trying to make people run an AI stack. You are trying to make them feel like: I installed my operator system."**

---

## The Pattern: How Windows Installs

Windows installs as a **bootstrapped system takeover**:

1. Boot into small installer environment
2. Check hardware/compatibility
3. Copy core system files
4. Install drivers and services
5. Configure (language, account, WiFi, privacy)
6. Reboot into the real OS
7. First-run background setup (indexing, sync, optimization)

**User experience:** Download → Run → Answer 5 questions → Wait → You're in.

---

## CHAMP OS Install Flow

```
Bootstrap → Environment Check → Service Install → Account Connect → Operator Select → Launch
```

### Stage 1: Bootstrap Installer
A small installer package that:
- Installs the platform
- Checks machine readiness
- Sets up folders/services
- Installs runtime dependencies silently

### Stage 2: Environment Check
Before install continues, verify:
- Python/runtime present or bundled
- Node/runtime present or bundled
- Microphone permissions
- Browser availability
- Ports available
- API keys or account login complete
- Local folders and memory storage ready

Status display: "Mic ready" / "Voice runtime ready" / "Memory store ready"

### Stage 3: Service Install (Core System Files)
Install the platform components:
- Core platform runtime
- Model routing layer (LiteLLM)
- Voice layer (LiveKit)
- Browser/control layer (Hands)
- Memory layer (Supabase)
- UI shell (Frontend)
- Operator framework

### Stage 4: First-Run Onboarding (OOBE)
Setup wizard asks:
- What is this system for? (personal / business / team)
- Who is the primary operator? (Champ / Billy / Sadie / custom)
- What channels should be enabled? (voice / text / browser / desktop)
- Connect your workspace (Google, Slack, CRM, calendar)
- Where should memory live? (local / cloud / hybrid)
- Microphone/camera permissions
- Launch on startup?

**User-facing language (NOT developer language):**
- "Connect your workspace" NOT "Connect OpenAI API key"
- "Allow voice access" NOT "Configure LiveKit credentials"
- "Choose where memory lives" NOT "Set SUPABASE_URL"

### Stage 5: Operator Activation
- Downloads or activates selected operator
- Loads voice/persona
- Initializes memory
- Opens the main UI

### Stage 6: Daily Use
From then on, user just:
- Opens app
- Speaks/types
- Works

---

## Two Install Modes

### Builder Install (Anthony / power users)
- Advanced setup
- Custom model keys
- Local/cloud toggles
- Debug visibility
- Terminal access
- 5-terminal manual mode available

### User Install (customers)
- Sign in
- Choose operator
- Grant permissions
- Connect Google/Microsoft
- Done

---

## Three Products Inside One Vision

### A. The OS Core
The runtime, services, channels, memory, tools, orchestration.
This is the **engine bay**.

### B. The Installer
The thing that turns complexity into a guided setup.
This is the **ignition experience**.

### C. The Shell
The experience they land in after setup — operator alive on screen.
This is the **dashboard and cabin**.

---

## Folder Structure (Champ's Proposal)

```
/core         — agent runtime, brain, orchestration
/operators    — persona files, operator configs
/runtime      — model routing, dependencies
/memory       — Supabase connection, local cache
/logs         — output, telemetry
/profiles     — user identity, operator preferences
/config       — environment, settings
```

Maps to current V3:
| Proposed | V3 Equivalent |
|----------|--------------|
| /core | agent.py, brain/ |
| /operators | persona/ |
| /runtime | litellm_config.yaml, venv |
| /memory | Supabase connection |
| /logs | output/ |
| /profiles | .env, operator configs |
| /config | .env, brain/config.py |

---

## Services (Champ's "Drivers" Equivalent)

| Windows Driver | CHAMP Service |
|---------------|--------------|
| Audio driver | Voice service (LiveKit + OpenAI Realtime) |
| Network driver | Model routing service (LiteLLM) |
| Graphics driver | UI shell (React frontend) |
| Input devices | Wake word listener (Ears) |
| Storage controller | Memory service (Supabase) |
| — | Browser control service (Hands) |
| — | Operator runtime (persona + tools) |
| — | Permissions service |
| — | Update service |
| — | Logging/telemetry service |

---

## The Car Analogy (Anthony's Framework, Champ-Refined)

| Role | What It Is | Example |
|------|-----------|---------|
| OS | The car (platform/chassis) | CHAMP platform |
| AI models | The engine + onboard computer | Claude, GPT, Gemini |
| Operator | The trained driver | Champ, Billy, Sadie |
| Apps/UI | Dashboard, controls, cabin experience | Frontend, voice, chat |
| User | The owner directing where to go | Anthony |

**Key insight:** AI is not Jarvis. The operator is Jarvis. AI is the engine powering Jarvis.

---

## The Bar

**"No 5 terminals. No pip install. No npm run dev. One installer. One click. Operator is alive."**

That's Windows-level simplicity. That's the target.

---

## Current State vs Target

| Now (Builder Mode) | Target (Product Mode) |
|--------------------|-----------------------|
| 5 terminals manually started | One-click launcher |
| pip install -r requirements.txt | Bundled dependencies |
| .env with raw API keys | "Connect your workspace" wizard |
| npm run dev | Auto-start UI shell |
| python agent.py dev | Service manager handles startup |
| Manual restart on crash | Self-healing recovery |

---

## What People Buy

People don't buy "architecture." They buy:
- "I installed it"
- "It opened"
- "It knew my name"
- "It started helping"

**The first-run experience is part of the product, not an extra.**
