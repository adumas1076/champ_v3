# Build Log: Multi-Operator Architecture

> Turning CHAMP from one hardcoded agent into an OS that spins up any operator.
> Design is in. Champ is the only operator. Master one, then rinse and repeat.

*Started: March 19, 2026*

---

## The Problem

CHAMP V3 had one monolithic agent class (`Friday`) with everything hardcoded:
- Instructions, voice, tools — all in one class
- No way to add a second operator without copy-pasting everything
- No separation between OS infrastructure and operator identity
- Didn't match the OS vs Operators architecture we designed

## What Was Built

### Core Loop: INPUT → THINK → ACT → RESPOND

Every operator follows the same 4-step loop:

| Step | What | Body Parts | AIOSCP Primitive |
|------|------|-----------|-----------------|
| INPUT | Operator receives something | Ears + Eyes | channel.receive |
| THINK | Operator processes it | Brain + Mind | context.read + capability.estimate |
| ACT | Operator does something | Hands | capability.invoke + task.delegate |
| RESPOND | Operator answers | Voice + Avatar | channel.send |

### Architecture: USER → OPERATOR → OS

```
USER talks to OPERATOR
OPERATOR runs ON the OS
OS is invisible underneath
```

The OS is the phone. Operators are the apps. Users interact through apps, not the phone's kernel.

### Files Created

| File | Purpose |
|------|---------|
| `operators/__init__.py` | Package init |
| `operators/base.py` | **BaseOperator** — the OS layer as a class. Every operator inherits this. |
| `operators/champ.py` | **ChampOperator** — Anthony's personal agent. First operator on the OS. |
| `operators/registry.py` | **OperatorRegistry** — how the OS looks up and spawns operators. |
| `operators/configs/champ.yaml` | **Champ config** — reference config template for all future operators. |

### Files Modified

| File | Change |
|------|--------|
| `agent.py` | Refactored from monolithic `Friday` class → uses `ChampOperator` from registry. Same behavior, new architecture. |

### BaseOperator (operators/base.py)

The OS layer. Every operator inherits this and gets for free:

**OS Tools organized by loop step:**
- INPUT (2): `analyze_screen`, `read_screen`
- THINK (1): `ask_brain`
- ACT (11): `browse_url`, `take_screenshot`, `fill_web_form`, `google_search`, `control_desktop`, `run_code`, `create_file`, `go_do`, `check_task`, `approve_task`, `resume_task`
- UTILITY (1): `get_weather`
- Total: 15 OS tools + `end_conversation` (built into base)

**Key features:**
- `on_enter()` — auto-greet when operator enters session
- `end_conversation()` — clean exit with room cleanup
- `from_config(name)` — factory method to create operators from YAML configs
- `tool_permissions` — None = full access, set = filtered (restricted operators)

### OperatorRegistry (operators/registry.py)

Two ways to register operators:
1. **By class:** `registry.register("champ", ChampOperator)` — code-defined
2. **By config:** `registry.register_config("billy")` — YAML-defined, no code needed

Spawn: `operator = registry.spawn("champ")` → OS creates the instance.

### Config Format (operators/configs/champ.yaml)

```yaml
name: champ
voice:
  provider: openai
  voice: ash
  temperature: 0.8
persona_file: persona/champ_persona_v1.6.1.md
tool_permissions: null  # null = all, list = filtered
channels:
  voice: true
  text: true
  video: true
boundaries: []
escalation: []
```

New operators just copy this template and change the values. No Python code needed.

### agent.py (OS Entrypoint)

Before:
```python
class Friday(Agent):  # Everything hardcoded
    tools=[get_weather, ask_brain, browse_url, ...]
```

After:
```python
registry.register("champ", ChampOperator)
operator = registry.spawn(DEFAULT_OPERATOR)
await session.start(room=ctx.room, agent=operator, ...)
```

Same behavior. Ready for multi-operator.

---

## What This Enables (Future — Not Built Yet)

```python
# Adding a new operator is just:
# 1. Write billy.yaml (config)
# 2. Register: registry.register_config("billy")
# 3. Done — OS can spawn Billy

# Or for code-defined operators:
# 1. Write operators/billy.py (inherits BaseOperator)
# 2. Register: registry.register("billy", BillyOperator)

# Agent routing (multiagent_vid pattern):
# @function_tool
# async def call_billy(self, topic: str):
#     billy = registry.spawn("billy", chat_ctx=self.chat_ctx)
#     return billy, f"Connecting you to Billy for {topic}."
```

## Design Decision: Master One First

We chose to scaffold the architecture but keep Champ as the only operator.
Reason: master the base pattern with one operator before scaling to many.
When Champ is solid, adding Billy/Sadie/Genesis is just config files.

---

## Test Results

```
[OK] BaseOperator imported (15 OS tools: 2 INPUT, 1 THINK, 11 ACT, 1 UTILITY)
[OK] ChampOperator imported
[OK] OperatorRegistry imported
[OK] Champ registered | available: ['champ']
[OK] Champ spawned | type: ChampOperator (inherits BaseOperator)
[OK] Champ greeting present
[OK] Unknown operator raises KeyError
[OK] champ.yaml config: voice=ash, tools=all
[OK] BaseOperator.from_config("champ") works
[OK] agent.py parses cleanly
[OK] agent.py top-level executes
[OK] Operator tool count: 16 (15 OS + end_conversation)
[OK] Restricted operator created (tool permissions filtering works)
[OK] Registry lists: ['champ']
=== ALL 14 TESTS PASSED ===
```

---

## Reference

Pattern stitched from: `reference/multiagent_vid-main/`
- `generic_agent.py` → inspired BaseOperator (on_enter, end_conversation)
- `agent.py` → inspired registry pattern, function_tool routing, chat context handoff
- Each agent carries own voice/instructions → each operator carries own config