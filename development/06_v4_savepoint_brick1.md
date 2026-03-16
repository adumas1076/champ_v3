# CHAMP V3 — Savepoint: Brick 1 Complete (2026-03-16)

## What's Working RIGHT NOW (DO NOT TOUCH)
- **Voice pipeline** — Champ talks via OpenAI Realtime + LiveKit (Friday pattern)
- **Agent** — `agent.py` with Friday entrypoint order, 14 tools registered, agent_name="champ"
- **Brain** — FastAPI on port 8100, token + dispatch + full pipeline
- **LiteLLM** — 3-model router on port 4001 (Claude/Gemini/GPT)
- **Frontend** — V3 Figma UI at localhost:3000/call, LiveKit connected, chat panel works
- **Memory** — Supabase connected, 628 conversations seeded
- **Ears** — Wake word detection on port 8101
- **File Processing** — 119/119 gate tests passed (30+ formats)
- **Self Mode** — Autonomous task engine with heartbeat
- **All gate tests** — 29/29 + 119/119 + 6/6 seeder

## What We Fixed Today

### Fix 1: OpenAI Billing (ROOT CAUSE of Champ not talking)
- **Problem:** Champ stopped talking in V3. Spent hours debugging code.
- **Real cause:** OpenAI credit balance was -$0.53
- **Fix:** Added $20 at platform.openai.com/settings/organization/billing
- **Lesson:** ALWAYS check API billing FIRST before debugging code. Check LiveKit Playground Events tab for `realtime_model_error` with `insufficient_quota`.

### Fix 2: Friday Entrypoint Pattern
- **Problem:** V3 used `ctx.connect()` before `session.start()`
- **Fix:** Switched to Friday's proven order: `session.start()` → `ctx.connect()` → `generate_reply()`
- **Source:** `reference/friday_jarvis-main/agent.py` + GUIDE.md Section 12

### Fix 3: RoomInputOptions
- **Problem:** V3 used `RoomOptions` (newer API) which may conflict
- **Fix:** Added `RoomInputOptions(video_enabled=True)` from Friday pattern
- **Also added:** `RoomOptions` with `text_input=True, text_output=True` for chat

### Fix 4: agent_name in WorkerOptions
- **Problem:** Brain dispatches `agent_name: "champ"` but worker didn't register with that name
- **Fix:** Added `agent_name="champ"` to `WorkerOptions`
- **Lesson:** Dispatch agent_name MUST match WorkerOptions agent_name

### Fix 5: noise_cancellation removed
- **Problem:** `noise_cancellation.BVC()` import was blocking on some LiveKit plans
- **Fix:** Removed the import and the option from RoomInputOptions

## What We Tried That Didn't Work
- Moving `RoomAudioRenderer` position in React tree — not the issue
- Swapping `ctx.connect()` order in V3 — partially helped but wasn't root cause
- Creating V4 from scratch — proved the agent works but the issue was billing
- Copying V3 frontend to V4 — `motion/react` package resolution failed until we used V3's exact `package-lock.json`

## Key Learnings

### Dr. Frankenstein Method (USE THIS)
1. Start with a PROVEN working reference (Friday)
2. Stitch YOUR parts onto it (persona, tools, brain)
3. Test after EVERY stitch
4. Never guess — read the reference code first

### Debugging Order
1. Check API billing (OpenAI, Anthropic, Google)
2. Check LiveKit Playground — does agent talk there?
3. If playground works but UI doesn't → frontend issue
4. If playground doesn't work → agent/API issue
5. Check terminal logs for errors
6. Only then debug code

### Session Isolation Rule (STILL CRITICAL)
- Multiple sessions editing same files broke V3 before
- One session owns agent.py, brain/, tools.py
- UI session owns frontend/src/ ONLY
- NEVER modify files you don't own

## Files Changed Today
- `champ_v3/agent.py` — Rewritten with Friday pattern (entrypoint order, RoomInputOptions, agent_name)
- `champ_v3/frontend/src/pages/VoiceCall.tsx` — `video={true}`, improved transcription handler, PIP camera
- `champ_v3/development/05_v4_lessons_and_fixes.md` — Created (multimodality reference)
- `champ_v3/development/06_v4_savepoint_brick1.md` — This file

## 5 Terminal Startup
```
Terminal 1: cd champ_v3 && venv/Scripts/activate && litellm --config litellm_config.yaml --port 4001
Terminal 2: cd champ_v3 && venv/Scripts/activate && python -m brain.main
Terminal 3: cd champ_v3/frontend && npm run dev
Terminal 4: cd champ_v3 && venv/Scripts/activate && python agent.py dev
Terminal 5: cd champ_v3 && venv/Scripts/activate && python -m ears
```
