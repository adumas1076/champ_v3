# Dr. Frankenstein Parts Registry
> Proven parts harvested from open-source repos. Clone → Rip → Stitch → Ship.

## Status: Reference repos cloned, integration TODO

---

## Part 1: Autoresearch (Karpathy)
**Source**: `reference/karpathy-autoresearch/`
**Stars**: 45.5K
**What it is**: AI agents that autonomously conduct research on any topic
**What to rip**:
- Research agent loop (question decomposition → web search → source evaluation → synthesis → citations)
- Source ranking/credibility scoring
- Report generation with provenance

**Where it lands in Cocreatiq**:
- `operators/configs/genesis.yaml` — Genesis operator config
- `operators/research_pipeline.py` — NEW: research capability
- Maps to AIOSP: `task.create` → `task.progress` → `task.complete` with deliverable

**Priority**: HIGH — makes Genesis a real research operator, not just an LLM wrapper

---

## Part 2: LLM Council (Karpathy)
**Source**: `reference/karpathy-llm-council/`
**Stars**: 16K
**What it is**: Multiple LLMs collaborating to answer complex questions via debate + consensus
**What to rip**:
- Multi-model debate pattern
- Consensus/voting algorithm
- Perspective weighting by domain expertise

**Where it lands in Cocreatiq**:
- `brain/council.py` — NEW: council mode for complex decisions
- Maps to AIOSP: `message.send` (operator ↔ operator) + `task.delegate`

**Priority**: HIGH — enables multi-operator collaboration (what Sintra CAN'T do)

---

## Part 3: Nanochat (Karpathy)
**Source**: `reference/karpathy-nanochat/`
**Stars**: 49.7K
**What it is**: Full ChatGPT clone on single GPU for ~$100
**What to rip**:
- Self-hosted inference setup (OpenAI-compatible API)
- Model serving pattern

**Where it lands in Cocreatiq**:
- `litellm_config.yaml` — add as cheapest fallback provider
- `brain/llm_client.py` — fallback routing logic
- Auto-routing: Low complexity → nanochat (free) | Medium → Gemini Flash ($0.30/M) | High → Claude ($3-5/M)

**Priority**: MEDIUM — cost safety net, not urgent until billing becomes a concern

---

## Part 4: Resonance / Chatterbox TTS
**Source**: https://github.com/code-with-antonio/resonance (NOT cloned yet)
**Stars**: N/A
**What it is**: Open-source ElevenLabs clone with zero-shot voice cloning
**What to rip**:
- `chatterbox_tts.py` — self-hosted TTS engine (MIT license)
- Modal GPU deployment pattern — solves 24GB avatar GPU requirement
- Polar billing/metering — usage-based pricing infrastructure

**Where it lands in Cocreatiq**:
- Voice provider dropdown (alongside OpenAI Realtime, ElevenLabs, Deepgram)
- `litellm_config.yaml` or separate voice router
- Billing: maps to AIOSP `capability.estimate`

**Latency reality**: ~1.5-3.5s warm (NOT real-time). Use for batch/offline. OpenAI Realtime stays for live conversation.
**Smart play**: Use Chatterbox for voice CLONING (unique operator voices), serve via OpenAI Realtime for speed.

**Priority**: LOW — revisit when adding voice provider dropdown

---

## Part 5: OCR Provenance MCP
**Source**: https://www.npmjs.com/package/ocr-provenance-mcp
**What to rip**: Provenance tracking pattern ONLY (not the full 150+ tool package)
**Pattern**: When file_processor extracts text, tag it: `{source: filename, page: N, timestamp: ISO}`
**Where it lands**: `brain/memory.py` — provenance metadata on context.write

**Priority**: LOW — nice-to-have for enterprise trust signals

---

## Part 6: Letta/MemGPT
**Source**: https://github.com/letta-ai/letta
**What it is**: Self-editing memory blocks + context compaction for stateful agents
**What to rip**:
- Memory block architecture (persona, human, knowledge, episodic, working)
- Context compaction (summarize at 80% window)
- Self-editing (agent writes its own memory in real-time)

**Where it lands in Cocreatiq**:
- `mind/letta_client.py` — Letta server integration
- `brain/memory.py` — hybrid Letta + Supabase
- Maps to AIOSP: `context.read`, `context.write`, `context.compact`

**Priority**: HIGH — already in progress (see build_log_10)

---

## Integration Order

```
NOW:        Letta/MemGPT (memory foundation)
NEXT:       Autoresearch (Genesis pipeline)
THEN:       LLM Council (multi-operator collaboration)
LATER:      Nanochat (cost fallback)
FUTURE:     Chatterbox TTS (voice cloning) + OCR Provenance (tracking)
```
