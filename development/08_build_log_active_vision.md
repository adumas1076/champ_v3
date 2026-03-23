# Build Log: Active Vision — Screen Analysis via LLM

> Giving CHAMP actual eyes. Before: screenshots saved but never understood.
> After: screenshot → base64 → vision model → natural language analysis.

*Started: March 19, 2026*

---

## The Gap

CHAMP had two vision modes, both incomplete:

1. **Passive Vision** (LiveKit webcam/screen share → OpenAI Realtime) — works for live camera, but the Realtime model can't do deep image analysis.
2. **Screenshot Capture** (`take_screenshot`) — saves PNGs to disk but returns only a file path. The voice agent is *blind* to the content.

No way to say "look at my screen and tell me what you see" and get back an actual answer.

---

## What Was Built

### New Tool: `analyze_screen`

**File:** `tools.py` (inserted after `take_screenshot`)

**Flow:**
1. Capture screenshot (desktop via pyautogui OR browser via nodriver if URL given)
2. Read PNG → base64 encode
3. Send to Brain `/v1/chat/completions` as `image_url` multimodal message
4. Brain routes through LiteLLM to the chosen vision model
5. Return analysis text to voice agent

**Parameters:**
| Param | Purpose | Default |
|-------|---------|---------|
| `question` | What to analyze | "Describe what you see on screen in detail." |
| `url` | Optional URL to screenshot | "" (desktop) |
| `model` | Vision model choice | "gemini-flash" |

**Available vision models (all via LiteLLM):**
- `gemini-flash` — Gemini 2.0 Flash. Fast + cheap. Default for quick screen reads.
- `gpt-4o` — GPT-4o. Detailed analysis, strong at UI understanding.
- `claude-sonnet` — Claude Sonnet 4.5. Best for code-heavy screenshots.

### Key Design Decision: Model as Parameter

The operator chooses the vision model per-call, not hardcoded. This matters because:
- Quick glance at what app is open → `gemini-flash` (cheap, <1s)
- Detailed UI audit → `gpt-4o` (thorough, ~3s)
- Read code on screen → `claude-sonnet` (best code understanding)

In production, AIOSCP operators can select the model based on task context. The `VISION_MODELS` set in `tools.py` is the single source of truth — add a model there when you add one to `litellm_config.yaml`.

---

## Files Modified

| File | Change |
|------|--------|
| `tools.py` | Added `import base64`, `VISION_MODELS` constant, `DEFAULT_VISION_MODEL`, `analyze_screen` tool |
| `agent.py` | Added `analyze_screen` import, registered in `Friday.tools[]`, updated agent instructions + session greeting |

## Files NOT Modified

- `brain/pipeline.py` — Already handles `image_url` routing, no changes needed
- `brain/main.py` — Already accepts multimodal messages, no changes needed
- `litellm_config.yaml` — All 3 models already registered
- `hands/desktop.py` — Screenshot capture unchanged
- `hands/stealth_browser.py` — Screenshot capture unchanged

---

## Test Results

```
[OK] All 18 tools import cleanly
[OK] VISION_MODELS = {'gemini-flash', 'gpt-4o', 'claude-sonnet'}
[OK] DEFAULT_VISION_MODEL = gemini-flash
[OK] analyze_screen type: FunctionTool
[OK] agent.py imports resolve
[OK] Model validation logic correct
[OK] base64 encoding works
[OK] Vision payload serializes correctly for Brain API
=== ALL TESTS PASSED ===
```

---

## What This Enables

Before: "Take a screenshot" → `Screenshot saved: C:\...\screenshot.png` (blind)
After: "What's on my screen?" → `"You have VS Code open with agent.py. Line 103 shows the Friday class constructor..."` (sees + understands)

The distinction in agent instructions:
- `take_screenshot` = save a file (Hands)
- `analyze_screen` = see and understand (Eyes)