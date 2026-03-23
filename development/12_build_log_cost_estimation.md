# Build Log 12 — Cost Estimation (The Differentiator)

**Date**: 2026-03-19
**Session**: Operator Build Session
**Status**: COMPLETE — No competitor does this

---

## The Problem

Every AI agent platform runs tasks blind — you don't know what it'll cost until after it's done. Manus burns through credits. Sintra charges per-helper. CrewAI gives zero visibility. Nobody tells you upfront.

## What Was Built

### New Tool: `estimate_task`

A voice-agent tool that estimates cost and time BEFORE executing a task.

**How it works:**
1. Analyzes the task description for keywords
2. Maps keywords → AIOSCP capabilities needed
3. Looks up cost/latency per capability
4. Returns a breakdown to the user

**Examples:**

| User says | Estimated cost | Time | Capabilities |
|-----------|---------------|------|-------------|
| "open Spotify" | $0.00 (free) | 1s | 1 (desktop) |
| "what's on my screen?" | $0.01-0.05 | 4s | 1 (vision) |
| "research competitor pricing" | $0.01-0.15 | 15s | 4 (search, browse, vision, brain) |
| "build me a web scraper" | $0.11-2.10 | 5min | 4 (brain, code, file, self mode) |

### Upgraded: `go_do` (Self Mode)

Now auto-estimates cost before submitting and includes it in the response:
> "Got it — I'm on it. Self Mode run started: RUN-2026-03-19-a1b2c3. Estimated cost: $0.11-2.10. I'll plan, build, test, and deliver this autonomously."

### Agent Instructions Updated

BaseOperator's OS tool instructions now tell every operator:
> "estimate_task: Estimate cost and time BEFORE doing expensive tasks. ALWAYS call this before go_do. No competitor does this — it's your differentiator."

---

## How Cost Mapping Works

Every OS capability has structured cost data (mirrors AIOSCP bridge):

```python
_CAPABILITY_COSTS = {
    "browse_url":      ($0.00, $0.00, 3000ms),
    "analyze_screen":  ($0.005, $0.05, 3000ms),
    "ask_brain":       ($0.01, $0.10, 5000ms),
    "go_do":           ($0.10, $2.00, 300000ms),
    ...
}
```

Task keywords map to likely capabilities:
- "research" → google_search + browse_url + ask_brain + analyze_screen
- "build" → ask_brain + run_code + create_file
- "scraper" → go_do (Self Mode)

---

## Files Modified
- `tools.py` — Added `_CAPABILITY_COSTS`, `_TASK_CAPABILITY_MAP`, `_estimate_from_task()`, `estimate_task` tool, upgraded `go_do` with auto-estimation
- `operators/base.py` — Added `estimate_task` to imports + THINK_TOOLS + OS tool instructions
- `operators/aioscp_bridge.py` — Added `estimate_task` AIOSCP capability

## Files NOT Modified
- `agent.py` — Unchanged (operators handle tools)
- `brain/main.py` — `/v1/aioscp/estimate` endpoint already existed
- `operators/champ.py` — Unchanged (inherits from BaseOperator)

---

## Test Results

```
Cost estimation: 12/12 passed
Existing tests: 61/61 passed
Total: 73/73
```

---

*"Before you run, you know what it costs. That's not a feature — that's respect for the user's money."*