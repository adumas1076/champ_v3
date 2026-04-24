---
name: skillify
description: Capture a repeatable process from this session into a reusable operator skill. The meta skill — the skill that makes skills.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(mkdir:*)
  - Bash(python:*)
when_to_use: "Use when the user says 'make this a skill', 'capture this', 'skillify', or at the end of any repeatable workflow. Also auto-triggers when a process has been done 3+ times without a skill."
argument-hint: "[description of the process to capture]"
arguments:
  - description
context: inline
---

# Skillify — The Skill That Makes Skills

Analyze the current session, identify the repeatable process, interview the user, and create a new SKILL.md that any operator can execute.

## Inputs
- `$description`: Optional — user's description of what the process is

## Goal
A validated SKILL.md file saved to `.claude/skills/{name}/SKILL.md` AND registered in the `operator_skills` Supabase table with status "draft".

## Steps

### 1. Analyze the Session
Read session context. Identify:
- What repeatable process was performed
- What inputs/parameters were used
- The distinct steps (in order)
- Success artifacts per step (not just "do X" but "X is done when Y exists")
- Where the user corrected or steered the process
- What tools and permissions were needed
- What operators/agents were involved

**Success criteria**: Clear list of steps, inputs, outputs, and corrections identified
**Rules**: Pay special attention to corrections — those become hard rules in the skill

### 2. Interview Round 1 — High Level Confirmation
Ask user via AskUserQuestion:
- Suggest a name and description. Confirm or rename.
- Suggest high-level goal + success criteria.

**Success criteria**: Name, description, and goal confirmed by user
**Rules**: Use AskUserQuestion for ALL questions. Never ask via plain text. User always has freeform "Other" option.

### 3. Interview Round 2 — Structure
Present numbered steps. Ask:
- Confirm step order is correct
- What arguments does someone need to provide? Suggest based on what you observed.
- Should this run inline (user steers mid-process) or forked (self-contained, no input needed)?
- Save to repo (`.claude/skills/`) or personal (`~/.claude/skills/`)?

**Success criteria**: Execution mode, arguments, save location confirmed

### 4. Interview Round 3 — Step Breakdown
For each major step, ask (if not obvious):
- What does this step produce that later steps need? (artifacts)
- What proves this step succeeded? (success criteria)
- Should the user confirm before proceeding? (human checkpoint — especially for irreversible actions)
- Can any steps run in parallel? (use 3a, 3b numbering)
- Hard constraints or preferences? (rules)

**Success criteria**: Every step has success criteria defined
**Rules**: Don't over-ask for simple processes. 2-step skill doesn't need 10 questions. Stop interviewing once you have enough.

### 5. Interview Round 4 — Triggers + Context
Confirm:
- When should this skill be invoked? (when_to_use)
- Trigger phrases with examples
- Which operator should own this skill?
- Any gotchas, edge cases, or things to watch out for?

**Success criteria**: when_to_use is specific with 3+ example trigger phrases

### 6. Write SKILL.md
Create directory and file at chosen location.

Use this format:
```
---
name: {name}
description: {one-line}
allowed-tools:
  {list of tools observed during session}
when_to_use: "{detailed trigger description with examples}"
argument-hint: "{placeholder showing arguments}"
arguments:
  {list of argument names}
context: {inline or fork}
---

# {Title}
Description

## Inputs
- `$arg`: Description

## Goal
Clear goal with success artifacts.

## Steps

### 1. Step Name
What to do. Specific. Actionable.

**Success criteria**: REQUIRED on every step.
**Artifacts**: Data this step produces (if later steps need it).
**Human checkpoint**: When to pause (if irreversible).
**Rules**: Hard constraints (especially from user corrections).
```

**Success criteria**: File written, valid markdown, frontmatter parses correctly
**Human checkpoint**: Show complete SKILL.md to user for review BEFORE saving

### 7. Register in Supabase
Insert into `operator_skills` table:
```sql
INSERT INTO operator_skills (name, description, steps, trigger_patterns, operator_name, status, effectiveness)
VALUES ('{name}', '{description}', '{steps_json}', '{triggers_json}', '{operator}', 'draft', 0.5);
```

**Success criteria**: Row exists in operator_skills table with status "draft"
**Artifacts**: skill_id (UUID) for tracking

### 8. Confirm to User
Tell them:
- Where the skill was saved
- How to invoke it: `/{skill-name} [arguments]`
- That the skill self-improves from corrections during usage
- That DDO tracks effectiveness and flags underperformers
- That after 10 successful runs, status auto-promotes to "proven"

**Success criteria**: User acknowledges and understands how to use the skill

## Skill Self-Improvement (Automatic — No Step Needed)

Once a skill exists, the skill improvement engine (`content_engine/skills/skill_improvement.py`) runs in the background:
- Every 5 user messages during skill execution, analyzes for corrections
- Detects: "do X instead", "always use Y", "don't do Z", "also ask about..."
- Auto-updates SKILL.md with corrections baked in
- Logs changes to DDO for tracking

## Skill Auto-Detection (Future — Level 3)

When the system detects a process done 3+ times without a skill:
- Suggests: "I noticed you've done {process} 3 times. Want me to skillify it?"
- If user says yes → runs this meta skill automatically
- Links to `mem_lessons` table (times_seen >= 3 → auto-promote)