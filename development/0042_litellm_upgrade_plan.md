# 0042 — LiteLLM Upgrade Plan: Cortex Routing + Cost Optimization
**Date:** 2026-04-16
**Category:** Infrastructure — LiteLLM Brain Router
**Status:** IN PROGRESS
**Owner:** Current session
**Inspiration:** Claude Code (prompt caching, 3-layer prompts), Nemoclaw (single endpoint, credential separation, blueprints), Hermes-Agent (per-turn smart routing, iteration budgets, models.dev registry)

---

## Current State (Before)

- 3 models only: Claude Sonnet 4.5, Gemini Flash, GPT-4o
- `simple-shuffle` routing (no intelligence)
- Port mismatch: config.py defaults to `:4000`, launcher uses `:4001`
- Stale model ID: `claude-sonnet-4-5-20250929`
- Same `max_tokens: 4096` for everything
- No cost tracking, no rate limits, no spend caps
- Content engine bypasses proxy with direct `litellm.acompletion()` calls
- No prompt caching
- Single config for all environments (local/railway/hetzner)

---

## Upgrade Tasks

### P0 — Bugs & Foundation (Do First)

#### P0.1: Fix Port Mismatch + Stale Model IDs
- **File:** `brain/config.py` — change default from `4000` to `4001`
- **File:** `litellm_config.yaml` — update `claude-sonnet-4-5-20250929` → `claude-sonnet-4-6-20250514`
- **Time:** 10 min

#### P0.2: Add All Cortex Routing Models to Config
Add every model from the Cortex Routing spec + Marketing Machine spec:

| Model Name | Provider | Role | Use Case |
|------------|----------|------|----------|
| claude-sonnet | Anthropic | Reasoning Cortex | BOFU posts, architecture, deep analysis |
| claude-haiku | Anthropic | QA Cortex | Eval scoring, structured analysis |
| gpt-4o | OpenAI | Action Cortex | Tool execution, structured output, fallback |
| gemini-flash | Google | Vision Cortex | Screenshots, screen reading, image analysis |
| grok-3-mini | xAI | Voice Cortex | Voice scripts, conversation, casual chat |
| llama-3.1-8b | Groq | Hook Generator | Generate 20 hook variants, pick best |
| gemini-2.5-flash | Google | Volume Writer | TOFU text posts (60% of content) |

- **File:** `litellm_config.yaml`
- **Env vars needed:** `XAI_API_KEY`, `GROQ_API_KEY` (add to `.env.example`)
- **Time:** 30 min

---

### P1 — Smart Routing (Core Improvement)

#### P1.1: Build `cortex_router.py` (Per-Turn Smart Routing)
**Inspired by:** Hermes-Agent `smart_model_routing.py`

Create a routing module that selects the right model per-request based on:
- **Task type** (voice script, content generation, eval, research, tool call)
- **Funnel stage** (TOFU → cheap, MOFU → mid, BOFU → expensive)
- **Message complexity** (length, keywords, code blocks)
- **Cost constraint** (operator budget remaining)

```python
# cortex_router.py — sits between Brain and LiteLLM
def select_model(task_type, funnel_stage=None, message=None, operator=None):
    """Returns the model_name string for LiteLLM"""
    ...
```

**Routing table:**
| Signal | Model | Why |
|--------|-------|-----|
| Voice script | grok-3-mini | Natural conversational tone, cheap |
| TOFU content | gemini-2.5-flash | Fast, cheap, good enough for volume |
| MOFU content | gpt-4o or claude-haiku | Better persuasion |
| BOFU content | claude-sonnet | Best brand voice, highest conversion |
| Hook A/B gen | llama-3.1-8b (Groq) | Generate 20, pick best, dirt cheap |
| QA eval | claude-haiku | Structured analysis |
| Research | claude-sonnet | Deep pattern extraction |
| Vision/screen | gemini-flash | Fast multimodal |
| Tool execution | gpt-4o | Best function calling |
| Default conversation | claude-sonnet | All-around best |

- **File:** NEW `brain/cortex_router.py`
- **Wire into:** `brain/pipeline.py` (replaces hardcoded model selection)
- **Time:** 2 hrs

#### P1.2: Kill Direct LiteLLM Calls — Single Endpoint Enforcement
**Inspired by:** Nemoclaw's `inference.local/v1` pattern

- **File:** `content_engine/llm_adapter.py` — remove `_call_litellm_direct()` fallback
- Everything must go through the LiteLLM proxy (single endpoint)
- If proxy is down, fail loudly — don't silently bypass
- **Time:** 30 min

---

### P2 — Cost Optimization

#### P2.1: Prompt Caching (DYNAMIC_BOUNDARY)
**Inspired by:** Claude Code's 3-layer cache split

Split every LLM call into cached vs fresh layers:
- **Layer 1 (cached 1hr):** Persona + operator config (changes rarely)
- **Layer 2 (cached 5min):** Tool definitions + knowledge blocks
- **Layer 3 (fresh):** User input + live context

Add `cache_control` to system prompt construction in `brain/pipeline.py`.

Target: >60% cache hit rate on repeated conversations.
Cost impact: 90% reduction on cached tokens.

- **File:** `brain/pipeline.py`, `brain/context_builder.py`
- **Time:** 2 hrs

#### P2.2: Iteration Budget + Spend Caps
**Inspired by:** Hermes-Agent `IterationBudget` + LiteLLM native budgets

- Per-operator iteration limits in YAML configs (default: 90 parent, 50 subagent)
- Per-session spend cap via LiteLLM `max_budget` router setting
- Alert at 80% budget consumed
- Self Mode gets its own budget (prevents runaway autonomous loops)

Add to `litellm_config.yaml`:
```yaml
router_settings:
  max_budget: 10.0  # $10/day default
  budget_duration: 24h
```

Add to operator configs:
```yaml
limits:
  max_iterations: 90
  max_spend_per_session: 2.00
```

- **Files:** `litellm_config.yaml`, `operators/configs/*.yaml`, `brain/pipeline.py`
- **Time:** 1 hr

---

### P3 — Polish & Future-Proofing

#### P3.1: Profile-Based Config (local/railway/hetzner)
**Inspired by:** Nemoclaw blueprint profiles

- `CHAMP_PROFILE=local|railway|hetzner` env var
- Local profile: includes Ollama for free local inference during dev
- Railway profile: cloud providers only, spend tracking enabled
- Hetzner profile: agent-optimized (voice models prioritized)

- **Files:** `litellm_config.yaml` split or profile sections, `start_litellm.py`
- **Time:** 1 hr

#### P3.2: Dynamic Model Metadata from models.dev
**Inspired by:** Hermes-Agent `models_dev.py`

- Fetch model metadata (context lengths, costs, capabilities) from models.dev API
- In-memory cache (1hr) + disk cache
- No more hardcoded `max_tokens: 4096` for everything
- Context length detection per provider

- **Files:** NEW `brain/model_registry.py`
- **Time:** 1 hr

---

## Files Created/Modified

| File | Action | Owner |
|------|--------|-------|
| `litellm_config.yaml` | MODIFY — add models, fix IDs, add budgets | This session |
| `brain/config.py` | MODIFY — fix port default | This session |
| `brain/cortex_router.py` | CREATE — smart routing module | This session |
| `brain/pipeline.py` | MODIFY — wire router + caching | This session |
| `brain/context_builder.py` | MODIFY — add cache_control blocks | This session |
| `brain/model_registry.py` | CREATE — models.dev integration | This session |
| `content_engine/llm_adapter.py` | MODIFY — remove direct LiteLLM calls | This session |
| `operators/configs/*.yaml` | MODIFY — add iteration limits | This session |
| `start_litellm.py` | MODIFY — profile support | This session |
| `.env.example` | MODIFY — add XAI_API_KEY, GROQ_API_KEY | This session |

## Files NOT Touched
```
brain/main.py (routes stay the same)
brain/llm_client.py (HTTP client stays the same — it talks to proxy)
frontend/* (no frontend changes)
operators/base.py (operator loop unchanged)
self_mode/* (reads from operator config limits)
```

---

## Success Metrics

| Metric | Before | After |
|--------|--------|-------|
| Models available | 3 | 7+ |
| Routing intelligence | None (shuffle) | Per-turn task-aware |
| Cache hit rate | 0% | >60% target |
| Cost per content piece | ~$0.013 | ~$0.004 (70% reduction) |
| Runaway loop protection | None | Iteration + spend caps |
| Environment profiles | 1 | 3 (local/railway/hetzner) |
| Direct provider calls | Yes (llm_adapter) | No (proxy only) |

---

## Key References

| Source | What We Harvested |
|--------|-------------------|
| Claude Code | 3-layer prompts, DYNAMIC_BOUNDARY caching, auto-compaction, quota fallback |
| Nemoclaw | Single routing endpoint, credential separation, blueprint profiles, policy tiers |
| Hermes-Agent | Per-turn smart routing, models.dev registry, iteration budgets, skill-as-user-message |
| Doc 0041 | TOFU/MOFU/BOFU routing table, blended cost targets |
| Cortex Routing (memory) | Grok/Claude/GPT-4o/Gemini role assignments |
