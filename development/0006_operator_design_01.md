# Operator Blueprint V2 — Full Body Map

**Date**: 2026-03-19
**FigJam**: https://www.figma.com/online-whiteboard/create-diagram/cee42127-5072-4ef5-9b2c-8755edb690bf
**Status**: 28 done / 5 needs activation / 7 TODO

---

## The Operator — "Master one, rinse and repeat"

Every operator ships with 8 body parts + Persona + Skills + A2A.
The OS provides the body. The operator defines how to use it.
Core loop: INPUT → THINK → ACT → RESPOND.

---

## 1. Persona — WHO the operator IS ✅

| Subtask | Status |
|---------|--------|
| Core Identity (`champ_core.md` — tone, speech, mindset, motto) | ✅ |
| Voice Config (provider + voice ID + temp in `champ.yaml`) | ✅ |
| Self-Editing (Letta `memory.persona` block refines over time) | 🟡 needs Docker |
| Boundaries + Escalation (what operator will/won't do) | ✅ |

## 2. Eyes — How it SEES ✅

| Subtask | Status |
|---------|--------|
| Active Vision (`analyze_screen` — any LiteLLM vision model) | ✅ |
| Passive Vision (LiveKit camera + screen share) | ✅ |
| UI Reading (`read_screen` — UI elements on screen) | ✅ |

## 3. Ears — How it LISTENS ✅

| Subtask | Status |
|---------|--------|
| Wake Word (`openwakeword` + Silero VAD) | ✅ |
| Voice Input (OpenAI Realtime STT) | ✅ |
| Text Input (LiveKit text channel) | ✅ |

## 4. Hands — How it ACTS ✅

| Subtask | Status |
|---------|--------|
| Browser (`nodriver` stealth Chrome — undetectable) | ✅ |
| Desktop (`pyautogui` + `pygetwindow` — any app) | ✅ |
| Code (`run_code` Python/JS) | ✅ |
| Files (`create_file`) | ✅ |
| Self Mode (`go_do` — autonomous 9-step pipeline) | ✅ |
| Google Search (real browser, personalized results) | ✅ |

## 5. Brain — How it THINKS 🟡

| Subtask | Status |
|---------|--------|
| LLM Routing (LiteLLM — Claude/GPT/Gemini) | ✅ |
| Mode Detection (Vibe/Build/Spec) | ✅ |
| Pipeline (persona + memory + mode → LLM) | ✅ |
| Cost Estimation (`estimate_task` before acting) | ✅ |
| Loop Selection (8 patterns designed — wiring TODO) | ❌ |
| Intent Understanding (beyond mode detection) | ❌ |

### The 8 Loops (designed in 0004_loop_taxonomy.md)

| # | Loop | Pattern | Status |
|---|------|---------|--------|
| 1 | Direct | INPUT → THINK → RESPOND | ✅ implicit |
| 2 | Action | INPUT → THINK → ACT → RESPOND | ✅ implicit |
| 3 | Verify | INPUT → THINK → ACT → VERIFY → RESPOND | 🟡 only Self Mode |
| 4 | Autonomous | INPUT → (THINK → ACT → VERIFY)ⁿ → RESPOND | ✅ Self Mode |
| 5 | Handoff | INPUT → THINK → DELEGATE → WAIT → RECEIVE → RESPOND | ❌ needs A2A |
| 6 | Healing | ERROR → THINK → ACT → VERIFY → RETRY/ESCALATE | ✅ |
| 7 | Memory | INTERACTION → THINK → STORE | ✅ |
| 8 | Watch | OBSERVE → THINK → ACT IF NEEDED | ✅ wake word |

## 6. Mind — How it REMEMBERS + IMPROVES 🟡

| Subtask | Status |
|---------|--------|
| Supabase (conversations, profile, lessons, healing — 5 tables) | ✅ |
| Letta Blocks (persona, human, knowledge, episodic, working) | ✅ |
| Learning Loop (extract lessons at session end) | ✅ |
| Healing Loop (real-time friction + self-correction) | ✅ |
| Context Compaction (auto-compress at 80% window) | ✅ |
| memory.human Sync (Supabase → Letta at startup) | ✅ |
| Provenance Chains (link facts to source conversation) | ❌ |
| Hybrid Search (BM25 + semantic vectors over memory) | ❌ |

## 7. Voice — How it SPEAKS ✅

| Subtask | Status |
|---------|--------|
| TTS Output (OpenAI Realtime, per operator) | ✅ |
| Voice Identity (each operator owns its voice) | ✅ |

## 8. Avatar — How it LOOKS ❌

| Subtask | Status |
|---------|--------|
| LiveAvatar (temporary solution) | 🟡 needs integration |
| FlashHead (custom pipeline) | ❌ |

## 9. Skills — What makes THIS operator UNIQUE 🟡

| Subtask | Status |
|---------|--------|
| Domain Tools (operator-specific on top of OS) | 🟡 architecture ready |
| Domain Knowledge (specialization context) | 🟡 architecture ready |
| Workflow Templates (pre-built task flows) | ❌ |

## 10. A2A — How operators TALK to each other ❌

| Subtask | Status |
|---------|--------|
| Swap (one replaces another with chat context) | ✅ |
| Delegate (`registry.delegate(from, to, task)`) | ❌ |
| Collaborate (multiple active simultaneously) | ❌ |
| Message Bus (pub/sub in Registry) | ❌ |
| Context Sharing (AIOSCP scopes: task/conv/operator/global) | ❌ |

---

## Summary

| Category | Done | Needs Activation | TODO |
|----------|------|-----------------|------|
| Persona | 3 | 1 | 0 |
| Eyes | 3 | 0 | 0 |
| Ears | 3 | 0 | 0 |
| Hands | 6 | 0 | 0 |
| Brain | 4 | 0 | 2 |
| Mind | 6 | 0 | 2 |
| Voice | 2 | 0 | 0 |
| Avatar | 0 | 1 | 1 |
| Skills | 0 | 2 | 1 |
| A2A | 1 | 0 | 4 |
| **Total** | **28** | **5** | **7** |

---

*"The operator IS the product. The OS is invisible. Master one body, every operator gets it for free."*