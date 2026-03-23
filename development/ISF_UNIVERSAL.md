# ISF — Issues & Solutions Formula
**Universal Problem-Solving Skill**

---

> **Understand the system. Identify the real problem. Think sideways. Test the smallest fix. Learn from every result. Get better every cycle.**

---

## When to Use

- Something is broken
- A build fails
- A task loops or stalls
- An integration behaves unexpectedly
- Output does not match expected result
- A fix is being proposed too early (you don't understand the system yet)
- Multiple failed attempts already happened

---

## The Formula

### PHASE 1: DIAGNOSE

**Step -1: Define Success**
Before touching anything — what does "fixed" look like?
- What should happen?
- What proves it's resolved?

**Step 0: What Do You Already Have?**
Inventory tools, events, logs, data, pipelines, APIs, working modules, past solutions.
- The solution may already exist in another part of the system.

**Step 1: What is X?**
Define it simply. What is it? Where does it live?

**Step 2: How does X work?**
Input → process → output. Trace the chain.

**Step 3: Why does X work?**
What assumptions, dependencies, and conditions must be true?

**Step 4: X's Full Circle**
What can X do? What can X NOT do? Where does X end and another system begin?

**Step 5: What does the user want?**
Desired outcome. Why they want it. What success looks like to THEM.

**Step 6: What is the issue?**
Expected vs actual. Exact gap. Never say "it's broken" — be precise.

**Step 6.5: Can you reproduce it?**
When, how often, under what conditions, what triggers it?

**Step 7: Why is it happening?**
Root cause. Separate symptom from cause. Is this the real problem or a symptom of something deeper?

---

### PHASE 2: THINK LATERALLY

**Step 8: Where does this problem already have a solution?**
Stop thinking linearly. Go sideways.
- What other framework, ideology, product, domain, or industry solved this?
- What data already exists that you're not using?
- What's already flowing that you can connect instead of rebuild?
- What would someone from a COMPLETELY DIFFERENT field do?

**Rule: Look for the principle, ideology, or framework — not just the identical tool.**

**The test:** If your solution FIGHTS the system, you're thinking linearly. If it USES what the system provides, you're thinking laterally.

**Step 8.5: Constraints**
What must not break? What's out of scope? What constraints matter?

---

### PHASE 3: RESEARCH & SOLVE (Autoresearch Loop)

**Step 9: Generate 3-10 solution candidates**
- Each testable in one run
- Each respects constraints
- Pull from frameworks, past lessons, lateral thinking
- Dr. Frankenstein: the solution might already exist in another build

**Step 10: Score each candidate**
- Solves root cause (not symptom)?
- Meets success definition?
- Respects constraints?
- Smallest change that proves the principle?
- Uses existing over building new?

**Step 11: Test the winner**
Smallest viable version. One clean test.

**Step 12: Verify**
- Did it fix the real issue?
- For the RIGHT reason?
- Create a new issue?
- Meet success definition from Step -1?

**Step 13: Loop or Extract**

**FAIL →** Loop back to Step 0 with new information. Each loop narrows.

**PASS →** Document what worked. WHY it worked. Extract the reusable pattern. Store the lesson. Next time starts better.

---

## Rules

1. Never solve before understanding the system.
2. Never confuse symptom with cause.
3. Never guess twice without using new information from failure.
4. Never build new if the solution already exists in another form.
5. Never test giant when small proves the principle.
6. Never close without extracting the lesson.
7. If you're fighting the system, think laterally.

---

## Minimal Prompt (paste into any session)

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
8. Where does this problem already have a solution?
   Look for principles, ideologies, frameworks from ANY domain.
8.5. What constraints must the solution respect?

RESEARCH & SOLVE:
9. Generate 3-10 solution candidates.
10. Score each against success criteria.
11. Test the winner (smallest viable version).
12. Verify: did it work for the right reason?
13. Pass → extract lesson. Fail → loop with new info.

Rules:
- Don't skip understanding steps.
- Don't guess twice.
- Connect existing solutions over building new ones.
- Test small before building big.
- Extract the lesson after every result.
- If you're fighting the system, think laterally.
```

---

> "Don't build what exists — connect what's already flowing."
