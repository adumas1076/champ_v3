# 0020 — ISF: Issues & Solutions Formula
**Date:** 2026-03-22
**Category:** Core Skill — loaded into every operator's Mind
**Origin:** Created by Anthony during Skipper V5 modal timing rebuild. Formalized for Cocreatiq OS.

---

## One-Line Definition

> **ISF is a first-principles problem-solving skill that diagnoses issues correctly, then uses autoresearch to find and verify the best solution automatically.**

## Compact Version

> **Understand → Identify → Think Laterally → Research Solutions → Test Small → Verify → Learn → Get Better**

---

## The Two Halves

| Half | What It Does | How It Works |
|---|---|---|
| **ISF (Issues & Solutions Formula)** | Diagnoses the problem correctly | Instructions loaded into operator Mind — thinking methodology |
| **Autoresearch Loop** | Finds and tests solutions automatically | Code that generates solutions, scores them, keeps winners, discards losers, repeats |

**ISF without Autoresearch** = correct diagnosis, manual solutions
**Autoresearch without ISF** = fast experiments, wrong problem
**Together** = correct diagnosis + automated best solution + self-improving

---

## Core Principle

> **Do not guess your way out of a problem. Understand the system, isolate the real issue, think laterally, let the autoresearch loop find and verify the best solution, then extract the lesson so it never happens again.**

---

## The Formula

### Phase 1: DIAGNOSE (ISF — Instructions)

**Trigger:** User wants to do X using X but Y is happening.

#### Step -1: Define Success
Before touching anything, define what "fixed" looks like.
- What should happen?
- What observable outcome proves success?
- What metric or behavior tells us the issue is resolved?

#### Step 0: Inventory What You Have
Look for what already exists before building anything new.
- Tools, events, logs, data streams, pipelines, APIs
- Working modules, existing UI, past solutions
- Existing memory, docs, patterns from previous ISF runs

**Rule: The solution may already exist in another part of the system.**

#### Step 1: What is X?
Define the thing you're working with. Teach it simply.
- What is it?
- What kind of component is it?
- Where does it live in the system?

#### Step 2: How does X work?
Trace the mechanics.
- Input → process → output
- Dependencies, sequence, timing
- Data handoffs, state changes

#### Step 3: Why does X work?
Define the conditions that make it function.
- What assumptions must be true?
- What dependencies must be present?
- What guarantees does it rely on?

#### Step 4: X's Full Circle
Understanding X's capabilities AND limitations.
- What can X do?
- What can X NOT do?
- What does X connect to upstream and downstream?
- Where does X's responsibility end and another system's begin?

#### Step 5: What does the user want done using X?
Define the goal precisely.
- What is the desired outcome?
- Why does the user want this specific outcome?
- What would success look like to THEM (not to you)?

#### Step 6: What is the issue?
State the gap precisely.
- Expected behavior
- Actual behavior
- Exact difference between them

**Rule: Never say "it's broken" if you can be more precise.**

#### Step 6.5: Can you reproduce it?
Confirm the issue is real and repeatable.
- When does it happen?
- How often?
- Under what conditions?
- What triggers it?

#### Step 7: Why is Y happening?
Find the root cause. Separate symptom from cause.
- What inside X or around X is causing the gap?
- What dependency, order, timing, or assumption is failing?
- Is Y the real problem, or a symptom of a deeper problem?

### Phase 2: THINK LATERALLY (de Bono — Instructions)

#### Step 8: Where does this problem already have a solution?
**Stop thinking linearly. Go sideways.**

- What other,frame works relsted or none related, product, domain, or industry already solved this shape of problem?
- What data already exists that you are not using?
- What system already has the thing you need?
- What is already flowing that you can connect instead of rebuild?
- What would someone from a COMPLETELY DIFFERENT field do?

**Rule: Look for the principle,ideology,frame work, not just the identical tool.**

**The test: If your proposed solution is FIGHTING the system, you're thinking linearly. If it USES what the system already provides, you're thinking laterally.**

#### Step 8.5: Define constraints
- What must not break?
- What is out of scope?
- What latency/cost/risk constraints matter?

### Phase 3: RESEARCH & SOLVE (Autoresearch Loop — Code)

#### Step 9: Generate solution candidates
Using everything from Steps 0-8.5, generate multiple possible solutions.
- Not just one — generate 3-10 candidates
- Each must be testable in one run
- Each must respect the constraints from Step 8.5
- Pull from Business Matrix frameworks, past ISF lessons, lateral thinking

#### Step 10: Score each candidate
Score every candidate against binary criteria:
- Does it solve the root cause (Step 7), not just the symptom?
- Does it meet the success definition (Step -1)?
- Does it respect all constraints (Step 8.5)?
- Is it the SMALLEST change that proves the principle?
- Does it use what exists rather than building new?

#### Step 11: Test the winner
Apply the highest-scoring solution.
- Implement the smallest viable version
- Run one clean test

#### Step 12: Verify the result
- Did it fix the real issue?
- Did it fix it for the RIGHT reason?
- Did it create a new issue?
- Did it meet the success definition from Step -1?

#### Step 13: Loop or Extract

**If FAIL:**
- The failed solution becomes new information
- Return to Step 0 with what you learned
- The loop narrows every time — you eliminated one wrong answer
- Autoresearch generates new candidates excluding the failed approach

**If PASS:**
- Document what worked and WHY
- Extract the reusable pattern
- Store the lesson in memory (Letta knowledge block)
- Update the scoring criteria based on what you learned
- Next time this pattern appears, start from a better baseline

---

## The Autoresearch Loop (Code Implementation)

```python
async def isf_autoresearch(issue, system_context, constraints, max_iterations=10):
    """
    ISF + Autoresearch: diagnose correctly, then find best solution automatically.

    1. ISF diagnoses the problem (Steps -1 through 8.5)
    2. Autoresearch generates and tests solutions (Steps 9-13)
    3. Each iteration improves the scoring criteria
    4. Returns the verified solution + extracted lesson
    """

    # Phase 1: ISF Diagnosis (run once)
    diagnosis = await isf_diagnose(issue, system_context)
    # Returns: root_cause, success_criteria, constraints, lateral_options

    # Phase 2: Autoresearch Loop (run N times)
    best_solution = None
    best_score = 0
    lessons = []

    for iteration in range(max_iterations):
        # Step 9: Generate candidates using diagnosis + lessons from previous iterations
        candidates = await generate_solutions(
            diagnosis=diagnosis,
            constraints=constraints,
            previous_lessons=lessons,
            lateral_options=diagnosis.lateral_options,
        )

        # Step 10: Score each candidate
        scored = []
        for candidate in candidates:
            score = await score_solution(
                candidate=candidate,
                success_criteria=diagnosis.success_criteria,
                constraints=constraints,
            )
            scored.append((candidate, score))

        # Step 11: Test the winner
        winner = max(scored, key=lambda x: x[1])
        result = await test_solution(winner[0])

        # Step 12: Verify
        if result.passes_success_criteria:
            best_solution = winner[0]
            best_score = winner[1]

            # Step 13: Extract lesson
            lesson = extract_lesson(
                issue=issue,
                diagnosis=diagnosis,
                solution=best_solution,
                iterations=iteration + 1,
            )

            # Store in memory for future ISF runs
            await store_lesson(lesson)

            return ISFResult(
                solution=best_solution,
                lesson=lesson,
                iterations=iteration + 1,
                score=best_score,
            )
        else:
            # Failed — learn and loop
            lessons.append({
                "candidate": winner[0],
                "score": winner[1],
                "why_failed": result.failure_reason,
            })

    # Max iterations reached
    return ISFResult(
        solution=None,
        lesson=f"Exhausted {max_iterations} iterations. Lessons: {lessons}",
        iterations=max_iterations,
        score=best_score,
    )
```

---

## Rules of the ISF

1. **Never solve before understanding the system.** Steps 1-4 are not optional.
2. **Never confuse symptom with cause.** Step 7 must separate them explicitly.
3. **Never guess twice without using the new information from failure.** Each loop iteration must incorporate lessons from the previous one.
4. **Never build something new if the solution already exists in another form.** Step 8 (lateral thinking) before Step 9 (generating solutions).
5. **Never test a giant solution when a small one can prove the principle.** Step 11 tests the SMALLEST viable version.
6. **Never close without extracting the lesson.** Step 13 stores the pattern for future use.
7. **If you're fighting the system, you're thinking linearly.** Step back and go lateral.

---

## Where It Lives in Cocreatiq OS

### As Instructions (ISF — every operator's Mind)
Loaded into every operator's persona at spawn. The operator follows the ISF steps when encountering any problem. This is a markdown file, not code.

### As Code (Autoresearch Loop — OS-level)
The `isf_autoresearch()` function runs as an OS-level capability. Any operator can invoke it:
```python
result = await self.isf_solve(
    issue="Content not getting clicks",
    system_context="Marketing operator, Instagram, Lamar frameworks loaded",
    constraints={"must_not_break": "existing posting schedule"},
)
```

### As Memory (Lessons — Letta knowledge blocks)
Every solved issue stores a lesson. Every lesson improves the scoring criteria. Every future ISF run starts from a better baseline.

---

## Operator Behavior When Using ISF

- Slow down before acting
- Explain the system simply (Steps 1-4)
- Isolate the problem precisely (Steps 6-7)
- Think laterally, not just locally (Step 8)
- Generate multiple solutions, not just one (Step 9)
- Score before testing (Step 10)
- Test the smallest viable version (Step 11)
- Verify for the right reason (Step 12)
- Extract and store the lesson (Step 13)

---

## Minimal Operator Prompt

```
Use the Issues & Solutions Formula (ISF).

DIAGNOSE:
-1. Define what success looks like.
0. Inventory what already exists.
1-4. Understand X fully: what it is, how it works, why it works, full circle.
5. What does the user want?
6. What is the issue precisely? (expected vs actual)
7. Why is it happening? (root cause, not symptom)

THINK LATERALLY:
8. Where does this problem already have a solution? Think sideways.
8.5. What constraints must the solution respect?

RESEARCH & SOLVE:
9. Generate 3-10 solution candidates.
10. Score each against success criteria.
11. Test the winner (smallest viable version).
12. Verify: did it work for the right reason?
13. Pass → extract lesson, store in memory.
    Fail → loop with new information.

Rules:
- Don't skip understanding steps.
- Don't guess twice.
- Connect existing solutions over building new ones.
- Test small before building big.
- Extract the lesson after every result.
- If you're fighting the system, think laterally.
```

---

## Origin Story

Created during the Skipper V5 modal timing rebuild (March 2026). Anthony spent a month trying to sync UI modals with AI voice agent speech. AI sessions kept proposing linear solutions (timers, word counting, SDK hacking). All failed.

Anthony applied ISF thinking: understood the system from scratch, identified the real issue (no real-time source of truth), thought laterally ("the LiveKit Playground already does this"), and found the solution was connecting what already existed (frontend transcript relay).

The autoresearch half comes from Karpathy's autoresearch repo: give an AI agent a system + scoring criteria, let it experiment autonomously, keep what works, discard what doesn't, repeat.

**ISF diagnoses correctly. Autoresearch finds the best solution. Together: an operator that thinks right AND gets better every cycle.**

> "Don't build what exists — connect what's already flowing."
> — The lesson from the first ISF run
