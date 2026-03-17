# CHAMP OS — License Registry

## Date: 2026-03-17
## Purpose: Track every open source dependency and its license for commercial use compliance

---

## Status Key
- **SAFE** = Free for commercial use, no code-sharing requirement
- **CHECK** = Need to verify specific terms before shipping
- **DANGER** = Would require open-sourcing CHAMP (avoid)

---

## Backend (Python)

| Package | License | Status | What It Does |
|---------|---------|--------|-------------|
| livekit-agents | Apache 2.0 | SAFE | Voice agent framework |
| livekit-plugins-openai | Apache 2.0 | SAFE | OpenAI Realtime integration |
| livekit-plugins-silero | Apache 2.0 | SAFE | Voice Activity Detection |
| livekit-plugins-noise-cancellation | LiveKit ToS | CHECK | Noise cancellation (cloud feature) |
| fastapi | MIT | SAFE | Brain API server |
| uvicorn | BSD-3 | SAFE | ASGI server |
| httpx | BSD-3 | SAFE | HTTP client |
| pydantic | MIT | SAFE | Data validation |
| pydantic-settings | MIT | SAFE | Settings management |
| supabase | MIT | SAFE | Memory/database client |
| openai | Apache 2.0 | SAFE | OpenAI API client |
| requests | Apache 2.0 | SAFE | HTTP requests |
| python-dotenv | BSD-3 | SAFE | Env file loading |
| numpy | BSD-3 | SAFE | Numerical computing |
| sounddevice | MIT | SAFE | Audio device access |
| openwakeword | — | CHECK | Wake word detection (verify license) |
| pyautogui | BSD | SAFE | Desktop automation |
| pygetwindow | BSD | SAFE | Window management |

## Frontend (JavaScript/TypeScript)

| Package | License | Status | What It Does |
|---------|---------|--------|-------------|
| react | MIT | SAFE | UI framework |
| react-dom | MIT | SAFE | React DOM renderer |
| react-router-dom | MIT | SAFE | Page routing |
| @livekit/components-react | Apache 2.0 | SAFE | LiveKit React components |
| @livekit/components-styles | Apache 2.0 | SAFE | LiveKit component styles |
| livekit-client | Apache 2.0 | SAFE | LiveKit browser SDK |
| lucide-react | ISC | SAFE | Icons |
| motion | MIT | SAFE | Animations |
| tailwindcss | MIT | SAFE | CSS framework |
| vite | MIT | SAFE | Build tool |
| typescript | Apache 2.0 | SAFE | Type system |
| postcss | MIT | SAFE | CSS processing |
| autoprefixer | MIT | SAFE | CSS vendor prefixes |

## Reference Projects

| Project | License | Status | What We Took |
|---------|---------|--------|-------------|
| friday_jarvis-main | — | CHECK | Entrypoint pattern (agent.py structure) |
| skipper_app_v5-main | — | CHECK | UI patterns (FaceTimeCall, AgentWidget) |
| SoulX-FlashHead | Apache 2.0 | SAFE | Avatar model (future) |

## External Services (APIs, not code)

| Service | Type | What It Does |
|---------|------|-------------|
| OpenAI | Paid API | Realtime voice + GPT models |
| Anthropic | Paid API | Claude models via LiteLLM |
| Google AI | Paid API | Gemini models via LiteLLM |
| LiveKit Cloud | Freemium | Voice/video transport |
| Supabase | Freemium | Database + auth + storage |

## Packages Under Evaluation

| Package | License | Status | What It Would Do |
|---------|---------|--------|-----------------|
| ocr-provenance-mcp | UNKNOWN | CHECK | 150+ document tools via MCP |

---

## Rules

1. **MIT, Apache 2.0, BSD** = safe to use commercially
2. **GPL, AGPL** = NEVER use — would force CHAMP to be open source
3. **"SEE LICENSE"** = always check the actual file before using
4. **No license listed** = treat as CHECK until verified
5. **Update this doc** every time we add a new dependency

---

## How to Check a New Package

```bash
# Python
pip show <package-name> | grep License

# npm
cat node_modules/<package>/LICENSE | head -5

# GitHub
# Look for LICENSE file in repo root
```
