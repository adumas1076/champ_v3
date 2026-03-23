# Operator Anatomy — The 8 Body Parts

## Core Loop: INPUT → THINK → ACT → RESPOND

Every interaction follows 4 steps:

1. **INPUT** — The operator receives something (voice, vision, text)
2. **THINK** — The operator processes it (reasoning, memory, persona)
3. **ACT** — The operator does something if needed (browse, click, code)
4. **RESPOND** — The operator answers (voice, text, avatar)

This loop applies at every scale:

| Level | INPUT | THINK | ACT | RESPOND |
|---|---|---|---|---|
| Operator | Ears + Eyes | Brain + Mind | Hands | Voice + Avatar |
| OS (AIOSCP) | channel.receive | context.read + capability.estimate | capability.invoke + task.delegate | channel.send |
| Multi-Operator | User request | Host picks operator | Operator executes, A2A handoff | Result delivered |
| Self Mode | Task instruction | Plan + break into steps | Execute each step | Deliver artifact |

## The 8 Body Parts

### Communication (Blue)
| Part | Function | Tech |
|---|---|---|
| 1. Ears | Voice input + wake word detection | openwakeword + sounddevice + LiveKit |
| 2. Voice | Speech output + TTS | OpenAI Realtime TTS + LiveKit WebRTC (provider dropdown planned) |

### Perception + Action (Green)
| Part | Function | Tech |
|---|---|---|
| 3. Eyes | Vision + screen reading + camera | OpenAI Realtime (video_enabled) + pyautogui + nodriver |
| 4. Hands | Browser + desktop + files | nodriver v0.48 + pyautogui + pygetwindow + file_processor |

### Intelligence (Orange)
| Part | Function | Tech |
|---|---|---|
| 5. Brain | Reasoning + model routing + mode detection | FastAPI + LiteLLM (Claude Sonnet 4.5 + Gemini 2.0 Flash + GPT-4o) |
| 6. Mind | Memory + learning + self-healing | Supabase 5 tables + Letta memory blocks + context compaction |

### Identity (Purple)
| Part | Function | Tech |
|---|---|---|
| 7. Avatar | Visual face + lip sync + expressions | LiveAvatar (current) → FlashHead (custom, next) |
| 8. Persona | Identity + character + speech patterns | Markdown 18KB (current) → manifest.yaml + self-editing blocks (next) |

## Framework Rule

Every operator — Champ, Billy, Sadie, or any marketplace operator — gets the same 8 body parts. The framework is standardized. What changes per operator is the configuration (wake word, voice ID, persona, model preferences, trust level, enabled tools).

Same skeleton. Different soul.

## The 13 Tools

### Hands Tools (8)
browse_url, take_screenshot, fill_web_form, google_search, run_code, create_file, control_desktop, read_screen

### Brain Tools (5)
ask_brain, get_weather, go_do (Self Mode), check_task, approve_task/resume_task

## Startup Stack (5 processes)
1. LiteLLM (port 4000) — model proxy
2. FastAPI Brain (port 8100) — persona, memory, mode detection
3. Vite Frontend (port 3000) — React UI
4. LiveKit Agent — operator runtime
5. Ears Listener — always-on wake word

## Data Flow

```
EARS ──audio stream──→ BRAIN ──response text──→ VOICE ──lip sync──→ AVATAR
EYES ──vision frames──→ BRAIN ──tool calls──→ HANDS
                         ↕
                        MIND (read + write memory)
                         ↑
                      PERSONA (shapes all output)
```
