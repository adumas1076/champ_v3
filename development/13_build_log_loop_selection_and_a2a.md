# Build Log 13 — Loop Selection + A2A Communication
**Date:** 2026-03-19
**Session:** Operator Build (continued)

## What Was Built

### 1. Loop Selector (`brain/loop_selector.py`)
OS-level classifier that selects the execution loop BEFORE the LLM call.
Runs alongside ModeDetector — Mode = HOW to respond, Loop = WHAT pattern to follow.

**8 Loop Types:**
| Loop | Pattern | When |
|------|---------|------|
| Direct | INPUT → THINK → RESPOND | Simple Q&A, no tools |
| Action | INPUT → THINK → ACT → RESPOND | Single tool call |
| Verify | INPUT → THINK → ACT → VERIFY → RESPOND | Tool + check result |
| Autonomous | INPUT → (THINK → ACT → VERIFY)ⁿ → RESPOND | Multi-step Self Mode |
| Handoff | INPUT → THINK → DELEGATE → WAIT → RESPOND | Route to another operator |
| Healing | ERROR → THINK → ACT → VERIFY → RETRY | Internal self-correction |
| Memory | INTERACTION → THINK → STORE | Internal learning |
| Watch | OBSERVE → THINK → ACT IF NEEDED | Internal monitoring |

**Wired into:** `pipeline.py` (both `handle_request` and `handle_stream`).
Loop instruction injected into context so LLM follows the right pattern.

### 2. A2A Communication (`operators/registry.py` + `operators/base.py`)
Three levels of agent-to-agent communication, all routed through the OS:

**Level 1 — Swap:** `registry.swap("champ", "billy")`
- One operator replaces another
- Chat context passes through
- Old operator goes dormant

**Level 2 — Delegate:** `registry.delegate("champ", "genesis", "research pricing")`
- Source operator keeps running
- OS spawns target if not active
- Task tracked with status, result, errors, timeout
- `A2ATask` dataclass with full lifecycle

**Level 3 — Collaborate:** `registry.message("champ", to_operator="billy", body="data")`
- Direct messages between operators
- Broadcast on channels (pub/sub)
- `registry.subscribe("research", callback)` / `registry.unsubscribe()`
- Multiple operators active simultaneously

**BaseOperator methods:**
- `self.delegate("genesis", "research pricing")` — routes through registry
- `self.message("billy", body="invoice ready")` — routes through registry
- `self.handle_task(description, context)` — override to handle delegated tasks
- `self.on_message(message)` — override to handle incoming messages

## Tests
- Loop Selector: 29 tests (all loop types, priorities, instructions)
- A2A: 15 tests (swap, delegate, timeout, messages, broadcast, subscribe)
- Full suite: 209/209 passing

## Files Changed
- `brain/loop_selector.py` — NEW (Loop Selector)
- `brain/pipeline.py` — MODIFIED (wired loop selection into both request paths)
- `operators/registry.py` — MODIFIED (added A2A: swap, delegate, message bus)
- `operators/base.py` — MODIFIED (added delegate, message, handle_task, on_message)
- `tests/test_loop_selector.py` — NEW (29 tests)
- `tests/test_a2a.py` — NEW (15 tests)

## FigJam
Updated Operator Blueprint V3 with loop selection (green) and A2A levels 1-3 (green).