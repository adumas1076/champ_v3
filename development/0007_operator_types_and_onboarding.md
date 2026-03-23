# 0007 — Pre-Built Operator Types & Persona Onboarding
**Date:** 2026-03-20
**Category:** Product Architecture

---

## Decision

Users do NOT build operators from scratch. Cocreatiq OS ships with pre-built operator TYPES. Users customize with their PERSONA on top.

**The analogy:** iPhone comes with Phone, Messages, Safari pre-installed. You don't build a phone app. You use it.

---

## The Three Layers

| Layer | Who Builds It | What It Defines |
|-------|--------------|-----------------|
| **BaseOperator** | OS team | Body parts, OS tools, loop engine, A2A, lifecycle |
| **Operator Type** | Product team | Role-specific skills, default permissions, domain knowledge, workflow templates |
| **Persona** | The user | Name, voice, personality, boundaries, connected apps, preferences |

---

## Pre-Built Operator Types (V1 Roster)

| Type | Role | Default Skills |
|------|------|---------------|
| Executive Assistant | Scheduling, email, calendar, task management | Calendar, email, reminders, meeting prep |
| Sales & Billing | Quotes, invoices, follow-ups, CRM | Pricing, invoicing, pipeline tracking |
| Research Analyst | Web research, data gathering, competitive analysis | Browse, analyze, summarize, compare |
| Creative Partner | Content, marketing, brainstorming, design briefs | Writing, ideation, brand voice, social media |
| Developer | Code, debug, deploy, technical docs | Code execution, file management, API calls |
| Onboarding Specialist | New client intake, setup, training | Forms, workflows, knowledge base |
| Customer Support | Ticket handling, FAQ, escalation | Knowledge base search, ticket tracking |

---

## Architecture

```
BaseOperator (OS layer — body parts, loop, tools)
    │
    ├── ExecutiveAssistantOperator (pre-built type)
    │       ├── "Friday" (user A's persona)
    │       └── "Jarvis" (user B's persona)
    │
    ├── SalesBillingOperator (pre-built type)
    │       ├── "Billy" (our persona)
    │       └── "Marcus" (client's persona)
    │
    ├── ResearchAnalystOperator (pre-built type)
    │       ├── "Genesis" (our persona)
    │       └── "Scout" (client's persona)
    │
    └── CustomOperator (advanced users / enterprise)
            └── "Champ" (Anthony's personal — all skills unlocked)
```

---

## Onboarding Flow

```
Step 1: "What do you need?"     → Pick operator type
Step 2: "Make it yours"         → Name, voice, personality, boundaries
Step 3: "Connect your world"    → Gmail, Slack, Calendar, CRM (connectors)
Step 4: "Meet your operator"    → Operator greets user by voice. Live.
```

No code. No YAML. No configuration files. Minutes, not hours.

---

## Config Stack

```yaml
# Layer 2: Operator Type (pre-built template)
type: executive_assistant
skills:
  - calendar_management
  - email_compose
  - meeting_prep
  - task_tracking
default_tools: [browse_url, google_search, create_file, ask_brain]
restricted_tools: [run_code, control_desktop]
default_voice: "coral"
trust_level: 2

# Layer 3: Persona (user customization)
persona:
  name: "Friday"
  voice: "coral"
  personality: "Professional but casual. Uses humor."
  boundaries:
    can_send_email: true
    can_schedule_meetings: true
    can_make_purchases: false
    requires_approval_above: "$50"
  connected_apps: [gmail, google_calendar, slack, notion]
```

---

## Business Model

| Tier | Operators | Types | Price |
|------|-----------|-------|-------|
| Free | 1 | 1 type, limited tasks | $0 |
| Pro | 3 | All types, connectors, Self Mode | $29-49/mo |
| Business | Unlimited | Custom types, A2A, admin panel | $99-199/mo |
| Enterprise | Unlimited | Custom skills, dedicated, white-label | Custom |

---

## Build Priority

1. Operator type template system (YAML + defaults + permissions)
2. ONE pre-built type (Executive Assistant — most universal)
3. Persona onboarding wizard
4. Rinse and repeat for each new type

---

## Marketing

> **Cocreatiq — changing the way businesses interact with technology.**