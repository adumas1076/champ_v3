# AIOSCP Operator Loop Taxonomy

## Framing

AIOSCP is the governance layer. Loops are the execution behaviors operators run inside that layer.

- The OS sets: identity, permissions, memory, channels, runs, handoffs
- The operator moves through one of 8 loop patterns depending on the job

## Core Loops (5)

| # | Loop Name | Pattern | When It Fires | Example |
|---|-----------|---------|---------------|---------|
| 1 | **Direct Loop** | INPUT → THINK → RESPOND | Simple question, no tool needed | "What's 2+2?" → "4" |
| 2 | **Action Loop** | INPUT → THINK → ACT → RESPOND | One action needed, then answer | "Open Google" → opens → "Done" |
| 3 | **Verify Loop** | INPUT → THINK → ACT → VERIFY → RESPOND | Check result before replying | "Take a screenshot" → capture → confirm → "Here it is" |
| 4 | **Autonomous Loop (ITAR)** | INPUT → (THINK → ACT → VERIFY)ⁿ → RESPOND | Multi-step, keep working until done | "Build me a weather app" → plan → code → test → fix → deliver |
| 5 | **Handoff Loop** | INPUT → THINK → DELEGATE → WAIT → RECEIVE → RESPOND | Another operator is better suited | Champ delegates research to Genesis |

## Support Loops (3)

| # | Loop Name | Pattern | When It Fires | Example |
|---|-----------|---------|---------------|---------|
| 6 | **Healing Loop** | ERROR → THINK → ACT → VERIFY → RETRY/ESCALATE | Tool fails, task stalls, operator stuck | Browser fails → try alternate → continue |
| 7 | **Memory Loop** | INTERACTION → THINK → STORE | New durable info should persist | Learns user prefers short answers → writes to memory |
| 8 | **Watch Loop** | OBSERVE → THINK → ACT IF NEEDED | Continuous monitoring, trigger-based | Wake word, deploy monitor, inbox watch |

## OS Control Layer (6)

| Control | Question It Answers |
|---------|-------------------|
| **Policy** | What is allowed? What needs approval? |
| **Memory** | What should this operator remember right now? |
| **Channels** | Where is this interaction happening? (voice, text, email, SMS, video, webhook) |
| **Runs** | What job is currently in progress? (start, checkpoint, complete, fail, recover) |
| **Handoffs** | Should this operator keep the work or pass it? |
| **Connectors** | What capabilities can the OS expose safely? (MCP servers, APIs, webhooks) |

## Key Relationships

- The user triggers the request
- The operator runs the loop
- The OS governs the loop

## Important Distinction

- Loops are operator behaviors
- AIOSCP is the governance layer around those behaviors
- Without the OS, you have smart agents. With the OS, you have governed operators.

## How Loops Map to Codebase

| Loop | CHAMP V3 Code |
|------|--------------|
| Direct Loop | agent.py — simple Q&A, no tool calls |
| Action Loop | agent.py — single tool call (browse_url, control_desktop) |
| Verify Loop | agent.py — take_screenshot + confirm result |
| Autonomous Loop | go_do → Self Mode 9-step pipeline |
| Handoff Loop | AIOSCP task.delegate + message.send |
| Healing Loop | AIOSCP operator.heal + healing tables in Supabase |
| Memory Loop | context.write to Supabase mem_profile + Letta blocks |
| Watch Loop | ears/listener.py — wake word state machine |
