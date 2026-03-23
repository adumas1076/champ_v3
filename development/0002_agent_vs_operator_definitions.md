# 0002 — Agent vs Multi-Agent vs Orchestrator vs Operator
**Date:** 2026-03-20
**Category:** Architecture Definition Document

---

## Why This Matters

The industry uses these words interchangeably. They are NOT the same thing. This document locks in the definitions for Cocreatiq OS.

---

## The Four Levels

### 1. Agent

**What it is:** A single AI that can use tools and make decisions.

**Analogy:** A freelancer. They can do work, use tools, make choices. But they work alone, have no boss, no system, no memory between gigs.

**Examples:** ChatGPT with plugins, a LangChain agent, Claude with MCP tools.

**What it has:**
- LLM (brain)
- Tools (hands)
- Instructions (prompt)

**What it DOESN'T have:**
- Identity / persona
- Memory across sessions
- Governance (nobody controls what it can do)
- Collaboration (can't talk to other agents)
- Lifecycle (no spawn / pause / heal / kill)
- Cost awareness

**Verdict:** The raw material. Table stakes. Everyone has this.

---

### 2. Multi-Agent

**What it is:** Multiple agents working on the same problem, usually coordinated by code (not by each other).

**Analogy:** A group of freelancers on a Fiverr project. The client (code) tells each one what to do. They don't talk to each other.

**Examples:** CrewAI crews, AutoGen groups, LangGraph multi-agent graphs.

**What it has:**
- Multiple agents
- A coordination pattern (usually hardcoded in Python)
- Sometimes shared state

**What it DOESN'T have:**
- An OS underneath
- Dynamic routing (usually predetermined who does what)
- Real-time collaboration (agents don't message each other mid-task)
- Identity / persona per agent
- Governance or cost control
- Channel support (voice, avatar, etc.)

**Verdict:** The pattern we borrowed from. But we went way beyond it.

---

### 3. Orchestrator

**What it is:** The coordinator that decides which agent does what, when.

**Analogy:** A project manager. Doesn't do the work. Assigns it, tracks it, makes sure it gets done, handles problems.

**Examples:** LangGraph's supervisor node, CrewAI's Process class, AutoGen's GroupChat manager.

**What it has:**
- Routing logic (who gets this task)
- Sequencing (what order)
- Error handling (what if it fails)
- Sometimes a planning step

**What it DOESN'T have:**
- Its own identity (it's infrastructure, not a personality)
- Memory management
- Channel management
- Governance / policy
- Cost tracking
- Self-healing

**Verdict:** ONE PART of the OS. The Orchestration pillar — one of six. Everyone else builds just this and calls it a platform.

---

### 4. Operator

**What it is:** A governed, identity-bearing, memory-equipped AI worker that runs ON an operating system.

**Analogy:** A full-time employee at a company. They have a name, a role, a desk, badge access, a file cabinet, a phone, relationships with coworkers, rules they follow, a manager they report to, and the company infrastructure underneath them.

**What it has:**
- **Identity** — Persona, voice, avatar, name, boundaries
- **Body** — Eyes, Ears, Hands, Brain, Mind, Voice, Avatar (8 body parts)
- **Loop** — INPUT → THINK → ACT → RESPOND (governed by OS)
- **Memory** — Persistent across sessions (Supabase + Letta)
- **Skills** — Domain-specific abilities on top of OS tools
- **Governance** — Permissions, trust levels, approval gates, cost limits
- **Collaboration** — A2A (swap, delegate, message, collaborate)
- **Lifecycle** — Spawn, pause, resume, heal, kill (managed by OS)
- **Channels** — Operates across voice, text, avatar, email simultaneously
- **Cost Awareness** — Estimates before acting, tracks spend

**Verdict:** This is what we build. This is the product.

---

## The Hierarchy

```
AGENT
  Just an LLM with tools. No identity. No memory. No governance.
  Everyone has this. It's table stakes.

    ↓ add coordination

MULTI-AGENT
  Multiple agents, coordinated by code.
  Still no identity. Still no real memory. Still no OS.
  CrewAI, AutoGen, LangGraph live here.

    ↓ add routing + task management

ORCHESTRATOR
  The coordinator. Assigns work, tracks completion.
  But it's just one component, not a whole system.
  Most "platforms" stop here and call it done.

    ↓ add identity + body + memory + governance + channels + lifecycle

OPERATOR
  A full digital worker. Identity. Memory. Body parts.
  Governed by an OS. Runs in a managed environment.
  Can collaborate with other operators through A2A.
  THIS IS WHAT WE BUILD.
```

---

## Competitive Landscape

| Product | What They Actually Are | What They Call Themselves |
|---------|----------------------|------------------------|
| ChatGPT | Agent | "AI assistant" |
| CrewAI | Multi-agent framework | "AI agents platform" |
| AutoGen | Multi-agent framework | "Multi-agent framework" |
| LangGraph | Orchestrator | "Agent framework" |
| Lindy | Orchestrator + basic agents | "AI employees" |
| Sintra | Orchestrator + personas | "AI helpers" |
| Manus | Agent + orchestrator | "AI agent" |
| **Cocreatiq OS** | **Full OS + Operators** | **"Operating system for AI operators"** |

Everyone else is building pieces. We're building the whole system.

---

## The One-Line Definitions

| Term | One Line |
|------|----------|
| **Agent** | An LLM that can use tools |
| **Multi-Agent** | Multiple agents coordinated by code |
| **Orchestrator** | The routing logic that assigns work to agents |
| **Operator** | A governed digital worker with identity, memory, and a body, running on an OS |
| **Cocreatiq OS** | The operating system that hosts, governs, and scales operators |
| **AIOSCP** | The protocol that governs how operators, capabilities, memory, channels, and tasks work together |

---

## The Key Distinction

When someone says "we built a multi-agent system":
```
agent1 = Agent(tools=[search])
agent2 = Agent(tools=[write])
result = agent1.run("research") → agent2.run("write report")
```

When WE say "we built an operator on Cocreatiq OS":
```
# Identity
champ = ChampOperator()          # persona, voice, avatar, boundaries

# OS governs the loop
loop = loop_selector.select(input) # Direct/Action/Verify/Autonomous/Handoff

# Cost estimation
cost = estimate_task("research")   # $0.08-0.15

# A2A delegation
task = champ.delegate("billy", "prepare quote")  # OS spawns, routes, tracks

# Persistent memory
context = context.read(scope="operator")  # survives across sessions

# Multi-modal channels
channel.send(type="voice", content="Done, champ...")  # voice + avatar + text

# OS tracks everything
# cost: $0.12 | duration: 67s | operators: 2 | capabilities: 3
```

That's not a multi-agent system. That's an operating system with digital workers.