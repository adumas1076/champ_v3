# Build Log 09 — Persona Split + Memory Architecture

**Date**: 2026-03-19
**Session**: Market Research → Operator Anatomy → Memory Strategy
**Status**: Phase 1 COMPLETE, Phase 2 PLANNED

---

## What Was Done

### Phase 1: Persona Split (COMPLETE)

**Problem**: 18KB monolithic persona file (`champ_persona_v1.6.1.md`) injected into every request. Wasting ~4,500 tokens per turn on instructions that aren't always needed.

**Solution**: Split architecture already implemented by prior session:

| File | Purpose | Size | Loaded |
|------|---------|------|--------|
| `persona/champ_core.md` | Identity, tone, mindset, working style | ~4KB | Always (system prompt) |
| `persona/memory_anthony.md` | User context — business, stack, preferences | ~1KB | Always (memory block) |
| `persona/champ_persona_v1.6.1.md` | Original monolith (ARCHIVED, not loaded) | 18KB | Never |

**Architecture**:
- `PersonaLoader` loads `champ_core.md` + all `memory_*.md` files
- `ContextBuilder` appends mode instructions (VIBE/BUILD/SPEC) per-request
- `champ.yaml` config points to `persona/champ_core.md`
- Hardcoded fallback exists if persona file missing
- Hot-reload supported without restart

**Token savings**: ~2,000-3,000 tokens per request (from ~4,500 down to ~1,500-2,500).

### Test Fix

Fixed `test_fallback_when_file_missing` — test was checking exact equality with `FALLBACK_PERSONA` but the loader now also appends `memory_*.md` blocks. Changed to `startswith()` check.

**Test results**: 36/36 passed (persona_loader, context_builder, mode_detector, healing).

---

## Phase 2: Letta/MemGPT Integration (PLANNED)

### The Problem
- Memory is one-directional: Brain reads from Supabase, but operator can't self-edit memory in real-time
- No context compaction: long conversations lose early context
- Learning loop runs at session END, not during conversation
- No cross-operator memory sharing

### The Plan

**Hybrid architecture**: Letta (intelligence) + Supabase (persistence) + AIOSCP (protocol)

```
AIOSCP Protocol Layer
  context.read / context.write / context.compact / context.search
          │                    │
   ┌──────┴──────┐    ┌───────┴──────┐
   │ Letta Server │    │   Supabase   │
   │              │    │              │
   │ memory.persona│   │ conversations│
   │ memory.human │    │ messages     │
   │ memory.knowl │    │ mem_profile  │
   │ memory.episod│    │ mem_lessons  │
   │ memory.working│   │ mem_healing  │
   │ + compaction │    │              │
   └──────────────┘    └──────────────┘
```

### 5 Letta Memory Blocks (from AIOSCP spec Section 5.5.1.1)

| Block | What | Editable By | Maps To |
|-------|------|-------------|---------|
| `memory.persona` | Operator self-edits personality over time | Operator + Host | New |
| `memory.human` | What operator knows about user | Operator | Replaces `memory_anthony.md` |
| `memory.knowledge` | Domain expertise | Operator | Extends `mem_lessons` |
| `memory.episodic` | Compressed session summaries | Host (auto) | New |
| `memory.working` | Current task scratchpad | Operator | New |

### Implementation Steps (TODO)
1. [ ] Install + configure Letta server (Docker or pip)
2. [ ] Create Letta agent with 5 memory blocks
3. [ ] Bridge: Letta reads/writes to Supabase for persistence
4. [ ] Update `PersonaLoader` to pull `memory.human` from Letta at startup
5. [ ] Update `ContextBuilder` to include Letta blocks in system prompt
6. [ ] Implement `context.compact` — trigger at 80% window
7. [ ] Wire real-time memory updates (mid-conversation, not just EOD)
8. [ ] Test end-to-end: spawn operator → talk → verify memory persists

### References
- Letta repo: https://github.com/letta-ai/letta
- AIOSCP spec: `aioscp/spec/AIOSCP-1.0.md` (Section 5.5)
- Operator anatomy: `development/0003_operator_anatomy.md`

---

## Files Changed
- `tests/test_persona_loader.py` — Fixed fallback test to account for memory blocks

## Files Verified (no changes needed)
- `brain/config.py` — Already points to `champ_core.md` (line 32)
- `brain/persona_loader.py` — Already loads core + memory_*.md blocks
- `brain/context_builder.py` — Already appends mode instructions per-request
- `operators/configs/champ.yaml` — Already references `persona/champ_core.md`
- `persona/champ_core.md` — Core persona (~4KB, well-structured)
- `persona/memory_anthony.md` — User memory block (~1KB)

---

*"The persona split is the foundation. Letta is the upgrade. AIOSCP is the protocol that makes it universal."*
