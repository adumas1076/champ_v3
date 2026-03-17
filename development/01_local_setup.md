# Building CHAMP in Minutes

> 5 terminals. That's all it takes to bring CHAMP to life.
> Each one is a brick in the system — cut one and the others still stand,
> but run all 5 and you've got a full AI teammate with voice, vision, memory, and autonomy.

---

## Prerequisites

Before you open a single terminal:

- **Python 3.12+** with `venv`
- **Node.js 18+** (for Hands browser engine + Frontend)
- **A microphone** (for Ears wake word detection)
- **API keys** filled in `.env` at the project root

### One-Time Install

```bash
# 1. Python backend (from champ_v3/)
python -m venv venv
venv\Scripts\activate
pip install -r requirements-brain.txt
pip install -r requirements-agent.txt

# 2. Browser engine (from champ_v3/hands/)
cd hands && npm install

# 3. Frontend UI (from champ_v3/frontend/)
cd frontend && npm install
```

That's it. Now open 5 terminals.

---

## Terminal 1 — The Router (LiteLLM)

### What it does
CHAMP doesn't talk to one AI model — it talks to three. LiteLLM sits in front of Claude, GPT-4o, and Gemini and routes every request to the right brain. Claude handles deep reasoning and code. Gemini handles vision (screenshots, screen reading). GPT-4o is the fallback if Claude goes down.

### Why it matters
Without the router, the Brain has no upstream to think with. This is the first thing that needs to be alive.

### Command (PowerShell — run each line separately)
```powershell
cd c:/Users/libby/OneDrive/Desktop/tool_shed/CHAMP/champ_v3
venv/Scripts/activate
python start_litellm.py
```

### What you'll see
```
  ANTHROPIC_API_KEY: sk-ant-a...wAA
  LITELLM_MASTER_KEY: sk-ch...key
Starting LiteLLM on port 4001...
LiteLLM: Proxy initialized with Config. Set models:
    claude-sonnet
    gemini-flash
    gpt-4o
```

### Details
| Setting        | Value                              |
|----------------|------------------------------------|
| **Port**       | 4001                               |
| **Config**     | `litellm_config.yaml`              |
| **Primary**    | Claude Sonnet 4.5 (reasoning, code)|
| **Vision**     | Gemini 2.0 Flash (images, screens) |
| **Fallback**   | GPT-4o (creative, backup)          |
| **Failover**   | Claude down? Auto-routes to GPT-4o |
| **Auth**       | `LITELLM_MASTER_KEY` from `.env`   |

---

## Terminal 2 — The Brain

### What it does
The Brain is CHAMP's central nervous system. Every message — whether typed or spoken — flows through here. It loads the persona ("who is Champ?"), detects what output mode to use (Vibe for quick chat, Build for structured work, Spec for deliverables), pulls memory from Supabase so Champ remembers who you are, then routes the enriched request up to LiteLLM for a response. It also runs the self-healing loop (catches friction mid-conversation) and exposes the Self Mode API for autonomous task execution.

### Why it matters
Without the Brain, there's no persona, no memory, no intelligence. It's the single API that the frontend, the voice agent, and all gate tests talk to.

### Command (PowerShell — run each line separately)
```powershell
cd c:/Users/libby/OneDrive/Desktop/tool_shed/CHAMP/champ_v3
venv/Scripts/activate
python -m uvicorn brain.main:app --host 0.0.0.0 --port 8100 --reload
```

### What you'll see
```
INFO:     Uvicorn running on http://0.0.0.0:8100
INFO:     Persona loaded: champ_persona_v1.6.1
INFO:     Memory connected to Supabase
INFO:     Self Mode heartbeat started (30 min poll)
```

### Details
| Setting        | Value                                    |
|----------------|------------------------------------------|
| **Port**       | 8100                                     |
| **Upstream**   | LiteLLM at `http://127.0.0.1:4001/v1`   |
| **Memory**     | Supabase (conversations, profile, lessons, healing) |
| **Health**     | `http://localhost:8100/health`           |

### Key Endpoints
| Endpoint                      | What It Does                                |
|-------------------------------|---------------------------------------------|
| `GET  /health`                | Is the Brain alive?                         |
| `POST /v1/chat/completions`   | Send a message, get a Champ response        |
| `POST /v1/session/start`      | Open a conversation (creates session in DB) |
| `POST /v1/session/end`        | Close session + trigger learning extraction |
| `POST /v1/upload`             | Upload any file — extracts content, returns file_id |
| `GET  /v1/files/{file_id}`    | Retrieve processed file content by ID       |
| `POST /v1/self_mode/submit`   | Hand Champ an autonomous task               |
| `GET  /v1/self_mode/status`   | Check how an autonomous task is going       |
| `POST /v1/self_mode/approve`  | Approve a task waiting at the gate          |
| `POST /v1/token`              | Get a LiveKit room token                    |
| `POST /v1/dispatch`           | Dispatch the voice agent to a room          |

---

## Terminal 3 — The Frontend

### What it does
The web UI you actually interact with. It has two pages: a **Dashboard** that shows task status, memory state, and system health — and a **Voice Call** page that connects you to a LiveKit room where you can talk to Champ in real time. It's built with React, Vite, TypeScript, and Tailwind.

### Why it matters
This is the face of CHAMP. Without it you'd be hitting raw API endpoints with curl. The dashboard gives you visibility into what Champ knows (memory), what he's working on (self mode runs), and whether the system is healthy. The voice call page is where you actually talk to him.

### Command (PowerShell — run each line separately)
```powershell
cd c:/Users/libby/OneDrive/Desktop/tool_shed/CHAMP/champ_v3/frontend
npm run dev
```

### What you'll see
```
  VITE v5.x.x  ready in 300 ms

  -> Local:   http://localhost:3000/
  -> Network: http://192.168.x.x:3000/
```

### Details
| Setting        | Value                                  |
|----------------|----------------------------------------|
| **Port**       | 3000                                   |
| **Framework**  | React 18 + Vite + TypeScript + Tailwind|
| **Brain URL**  | `http://127.0.0.1:8100` (via `VITE_BRAIN_URL`) |

### Pages
| Route    | Page       | What You See                               |
|----------|------------|--------------------------------------------|
| `/`      | Dashboard  | Tasks, memory entries, system health        |
| `/call`  | Voice Call | Join a LiveKit room, talk to Champ live     |

---

## Terminal 4 — The Voice Agent

### What it does
This is Champ's voice. It connects to LiveKit Cloud, listens to your microphone in real time using OpenAI's Realtime API (voice model "ash"), and streams audio back so Champ literally talks to you. But it's not just a voice pipe — it has real tools wired in: it can browse the web, take screenshots, fill forms, run code, create files, and kick off autonomous tasks via Self Mode. When you say "go build me a scraper," this is the process that hears it, calls the Brain, and executes it.

### Why it matters
Without the agent, CHAMP is text-only. With it, you've got a voice-powered AI that can hear you, think through the Brain, act with Hands, and talk back — all in real time. This is the "Jarvis" experience.

### Command (PowerShell — run each line separately)
```powershell
cd c:/Users/libby/OneDrive/Desktop/tool_shed/CHAMP/champ_v3
venv/Scripts/activate
python agent.py start
```

### What you'll see
```
INFO:     LiveKit agent worker started
INFO:     Connected to wss://champ-ifc6b5uj.livekit.cloud
INFO:     Waiting for room participants...
```

### Details
| Setting          | Value                                     |
|------------------|-------------------------------------------|
| **Platform**     | LiveKit Cloud (WebRTC)                    |
| **Voice Model**  | OpenAI Realtime — voice "ash"             |
| **Noise Cancel** | LiveKit noise cancellation plugin          |
| **Brain**        | Calls `http://127.0.0.1:8100` via `ask_brain` tool |

### Tools Available to the Agent
| Tool              | What It Does                                    |
|-------------------|-------------------------------------------------|
| `ask_brain`       | Route a question through the full Brain pipeline|
| `browse_url`      | Open a URL, return page text                    |
| `take_screenshot` | Capture a webpage as an image                   |
| `fill_web_form`   | Human-like form filling with stealth browser    |
| `run_code`        | Execute shell commands / Python scripts         |
| `create_file`     | Write files to disk                             |
| `go_do`           | Submit an autonomous task to Self Mode          |
| `check_task`      | Check status of a Self Mode run                 |
| `approve_task`    | Approve a task at the approval gate             |
| `search_web`      | Web search                                      |
| `get_weather`     | Weather lookup                                  |

---

## Terminal 5 — The Ears

### What it does
Ears is CHAMP's always-on wake word detector. It sits on your local microphone, running the openWakeWord model, waiting to hear "Hey Jarvis." When it detects the wake phrase, it flips into conversation mode — creating a LiveKit room, streaming your audio to the Voice Agent, and starting a session. When you go silent, it times out and drops back to listening. Think of it as the trigger that wakes CHAMP up without you touching the keyboard.

### Why it matters
Without Ears, you have to manually open the Voice Call page and click "Join." With Ears running, CHAMP is always listening — just say the word and it activates. This is the ambient intelligence layer that makes CHAMP feel like it lives in the room with you.

### Command (PowerShell — run each line separately)
```powershell
cd c:/Users/libby/OneDrive/Desktop/tool_shed/CHAMP/champ_v3
venv/Scripts/activate
python -m ears
```

### What you'll see
```
INFO:     Wake word detector ready: model=hey_jarvis, threshold=0.5
INFO:     Ears listening... say "Hey Jarvis"
```

### Details
| Setting            | Value                                |
|--------------------|--------------------------------------|
| **Port**           | 8101 (health check only)             |
| **Wake Word**      | "Hey Jarvis" (configurable)          |
| **Detection**      | openWakeWord + Silero VAD            |
| **Threshold**      | 0.5 (adjustable in `.env`)           |
| **Silence Timeout**| 30 seconds (drops back to listening) |
| **Cooldown**       | 2 seconds between activations        |
| **Audio**          | Local microphone via sounddevice     |
| **Streams to**     | LiveKit room (same as Voice Agent)   |

### State Machine
```
LISTENING  -->  "Hey Jarvis" detected  -->  ACTIVATING
ACTIVATING -->  LiveKit room joined    -->  CONVERSATION
CONVERSATION -> 30s silence            -->  COOLDOWN
COOLDOWN   -->  2s pause               -->  LISTENING
```

---

## The Full Picture

When all 5 terminals are running, this is what's happening:

```
  YOU (microphone)
   |
   v
[Terminal 5: EARS]  ----  "Hey Jarvis" detected
   |
   v
[Terminal 4: AGENT]  ----  Hears you, thinks, talks back
   |                            |
   | ask_brain()                | browse_url / run_code / create_file
   v                            v
[Terminal 2: BRAIN]         [HANDS - Puppeteer]
   |       |
   |       +---> Supabase (memory, sessions, self mode)
   v
[Terminal 1: LITELLM]
   |       |       |
   v       v       v
Claude   Gemini   GPT-4o


[Terminal 3: FRONTEND]  ----  Dashboard + Voice Call UI
   |
   v
[Terminal 2: BRAIN]  (same Brain, different client)
```

**The flow:**
1. **Ears** hears "Hey Jarvis" and activates
2. **Agent** picks up your voice, streams it through OpenAI Realtime
3. **Brain** enriches the request with persona + memory + mode detection
4. **LiteLLM** routes to the right model (Claude / Gemini / GPT)
5. Response flows back: LiteLLM -> Brain -> Agent -> your speakers
6. **Frontend** lets you see everything happening in real time

---

## Startup Order

Always start in this order — each brick depends on the one before it:

```
1. LiteLLM   (port 4001)  — the models need to be reachable first
2. Brain     (port 8100)  — needs LiteLLM upstream
3. Frontend  (port 3000)  — needs Brain API
4. Agent     (LiveKit)    — needs Brain + LiveKit cloud
5. Ears      (port 8101)  — needs LiveKit for streaming
```

---

## Gate Tests (Validation)

Before going live, run gate tests to validate each brick. Terminals 1 + 2 must be running.

```bash
# From champ_v3/ with venv active

python gate_test.py              # Brain pipeline — chat + mode detection
python gate_test_seeder.py       # Memory seeder — loads 628 ChatGPT sessions
python gate_test_hands.py        # Hands — browser automation + screenshots
python gate_test_mind.py         # Mind — self-learning + self-healing
python gate_test_self_mode.py    # Self Mode — autonomous task execution
python gate_test_ears.py         # Ears — wake word detection (needs mic)
```

---

## Port Map

| Terminal | Service   | Port  | Depends On         |
|----------|-----------|-------|--------------------|
| 1        | LiteLLM   | 4001  | API keys in `.env` |
| 2        | Brain     | 8100  | LiteLLM (4001)     |
| 3        | Frontend  | 3000  | Brain (8100)       |
| 4        | Agent     | cloud | Brain + LiveKit    |
| 5        | Ears      | 8101  | LiveKit            |

---

## Troubleshooting

| Symptom                             | Fix                                              |
|-------------------------------------|--------------------------------------------------|
| `&&` errors in terminal             | You're in PowerShell — run each line separately   |
| `npm.ps1 cannot be loaded`          | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `vite is not recognized`            | Run `npm install` in the frontend folder first    |
| Brain says "connection refused"     | Terminal 1 (LiteLLM) isn't running               |
| Frontend shows blank / error        | Terminal 2 (Brain) isn't running                  |
| Chat returns empty or times out     | Check API keys in `.env` — are they valid?        |
| Memory not saving / loading         | Check `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`|
| Voice agent won't connect           | Check `LIVEKIT_URL`, `API_KEY`, `API_SECRET`      |
| Browser tests fail                  | Run `cd hands && npm install`                     |
| Ears doesn't detect wake word       | Check mic permissions + `WAKE_THRESHOLD` in `.env`|
| Self Mode task stuck at "queued"    | Brain heartbeat polls every 30 min — or restart   |

---

## Environment Variables Quick Reference

All set in `champ_v3/.env`:

| Variable                  | Used By          | What It Is                        |
|---------------------------|------------------|-----------------------------------|
| `ANTHROPIC_API_KEY`       | LiteLLM          | Claude API key                    |
| `OPENAI_API_KEY`          | LiteLLM + Agent  | GPT-4o + Realtime voice           |
| `GOOGLE_API_KEY`          | LiteLLM          | Gemini Flash vision               |
| `LITELLM_MASTER_KEY`      | LiteLLM + Brain  | Auth key for the proxy            |
| `LIVEKIT_URL`             | Agent + Ears     | LiveKit cloud WebSocket URL       |
| `LIVEKIT_API_KEY`         | Agent + Ears     | LiveKit auth                      |
| `LIVEKIT_API_SECRET`      | Agent + Ears     | LiveKit auth                      |
| `DEEPGRAM_API_KEY`        | Agent            | Speech-to-text                    |
| `ELEVENLABS_API_KEY`      | Agent            | Text-to-speech                    |
| `SUPABASE_URL`            | Brain            | Supabase project URL              |
| `SUPABASE_SERVICE_ROLE_KEY`| Brain           | Supabase admin access             |
