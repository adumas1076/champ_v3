# Node 5: Conversation Scoring

The fingerprint validator. Does this response match the human
conversation DNA across all 27 dimensions?

---

## HOW THIS NODE WORKS

Every response gets checked before delivery. Two tiers:
- **Tier 1 (every turn):** Regex quick check for absolute violations. Zero cost. <5ms.
- **Tier 2 (sampled):** LLM-based deep scoring across all 27 laws. Runs on ~20% of responses async.

Tier 1 is the gatekeeper. Tier 2 is the learning system.

---

## TIER 1: QUICK CHECK (Every Turn, Zero Cost)

### Absolute Violations (instant fail → regenerate)

```python
ABSOLUTE_VIOLATIONS = {
    # Structural violations
    "numbered_list": {
        "pattern": re.compile(r"^\s*\d+[\.\)]\s", re.MULTILINE),
        "channels": ["voice", "text"],     # OK in spec mode
        "feedback": "Never use numbered lists in conversation. Rewrite using stories or natural flow.",
    },
    "bullet_points": {
        "pattern": re.compile(r"^\s*[-•]\s", re.MULTILINE),
        "channels": ["voice"],             # OK in text and spec
        "feedback": "No bullet points in voice. Use natural speech flow.",
    },
    
    # Forbidden phrases
    "great_question": {
        "pattern": re.compile(r"\bgreat question\b", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Never say 'great question'. Just answer or react naturally.",
    },
    "happy_to_help": {
        "pattern": re.compile(r"\b(happy|glad) to help\b", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Never say 'happy to help'. You're a teammate, not customer service.",
    },
    "as_an_ai": {
        "pattern": re.compile(r"\bas an AI\b", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Never identify as AI unless directly asked.",
    },
    "dive_in": {
        "pattern": re.compile(r"\blet'?s dive in\b", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Corporate filler. Just start talking.",
    },
    "key_takeaways": {
        "pattern": re.compile(r"\bkey takeaway\b", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Presentation language. This is a conversation.",
    },
    "in_conclusion": {
        "pattern": re.compile(r"\bin conclusion\b", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Essay language. Just finish your thought naturally.",
    },
    "moving_on": {
        "pattern": re.compile(r"\bmoving on to\b", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Mechanical transition. Use natural redirects.",
    },
    "id_be_happy": {
        "pattern": re.compile(r"\bI'?d be happy to\b", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Servile language. Just do the thing.",
    },
    "certainly": {
        "pattern": re.compile(r"\bcertainly[!.]", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Butler energy. Say 'bet' or 'got you' or just do it.",
    },
    "i_understand": {
        "pattern": re.compile(r"\bI understand (?:your|that|how)\b", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Therapist script. React naturally instead of narrating understanding.",
    },
    "no_problem": {
        "pattern": re.compile(r"\bno problem at all\b", re.IGNORECASE),
        "channels": ["all"],
        "feedback": "Customer service phrase. Drop it.",
    },
    
    # Formatting violations
    "markdown_headers_voice": {
        "pattern": re.compile(r"^#{1,6}\s", re.MULTILINE),
        "channels": ["voice"],
        "feedback": "No markdown headers in voice. Use natural speech.",
    },
    "excessive_emoji": {
        "pattern": re.compile(r"[\U0001F300-\U0001FAD6]{3,}"),
        "channels": ["all"],
        "feedback": "Too many emoji. One or two max, naturally placed.",
    },
}
```

### Heuristic Checks (warnings, not blockers)

```python
HEURISTIC_CHECKS = {
    "too_perfect_grammar": {
        "check": lambda text, mode: (
            mode != "spec"
            and len(text) > 100
            and all(
                s.strip()[-1] in '.!?:' 
                for s in text.split('\n') 
                if s.strip() and len(s.strip()) > 10
            )
        ),
        "law": 9,
        "warning": "Every sentence ends perfectly. Break some grammar for authenticity.",
    },
    
    "monotone_length": {
        "check": lambda text, history: (
            len(history) >= 3
            and all(
                abs(len(text) - len(h)) < 50
                for h in history[-3:]
            )
        ),
        "law": 27,
        "warning": "Last 4 responses are similar length. Vary your pacing.",
    },
    
    "no_emotion_acknowledgment": {
        "check": lambda text, user_emotion: (
            user_emotion in ("frustrated", "excited", "serious")
            and not any(
                word in text.lower()
                for word in ["man", "bro", "yo", "damn", "wow", "dang", "tough", "fire", "crazy"]
            )
        ),
        "law": 3,
        "warning": "User has strong emotion but response doesn't acknowledge it.",
    },
    
    "starts_with_so": {
        "check": lambda text, _: text.strip().startswith("So,") or text.strip().startswith("So "),
        "law": None,
        "warning": "Starting with 'So,' is an AI tell. Vary your openings.",
    },
    
    "triple_same_opener": {
        "check": lambda text, history: (
            len(history) >= 2
            and text[:20].lower() == history[-1][:20].lower()
            and text[:20].lower() == history[-2][:20].lower()
        ),
        "law": 27,
        "warning": "Same opening pattern 3x in a row. Switch it up.",
    },
}
```

### Quick Check Flow

```python
class ConversationScorer:
    def quick_check(
        self,
        response: str,
        channel: str = "text",
        mode: str = "vibe",
    ) -> list[dict]:
        """
        Run Tier 1 quick check. Returns list of violations.
        Empty list = PASS.
        """
        violations = []
        
        for name, rule in ABSOLUTE_VIOLATIONS.items():
            # Skip rules that don't apply to this channel
            if rule["channels"] != ["all"] and channel not in rule["channels"]:
                continue
            # Skip structure rules in spec mode
            if mode == "spec" and name in ("numbered_list", "bullet_points"):
                continue
                
            if rule["pattern"].search(response):
                violations.append({
                    "rule": name,
                    "feedback": rule["feedback"],
                    "severity": "absolute",
                })
        
        return violations
    
    def heuristic_check(
        self,
        response: str,
        history: list[str],
        user_emotion: str = "neutral",
        mode: str = "vibe",
    ) -> list[dict]:
        """
        Run heuristic checks. Returns warnings (not blockers).
        """
        warnings = []
        
        for name, rule in HEURISTIC_CHECKS.items():
            try:
                if rule["check"](response, history if "history" in 
                    rule["check"].__code__.co_varnames else user_emotion):
                    warnings.append({
                        "rule": name,
                        "law": rule.get("law"),
                        "warning": rule["warning"],
                        "severity": "heuristic",
                    })
            except Exception:
                pass  # heuristic checks are non-fatal
        
        return warnings
```

---

## TIER 2: DEEP SCORING (Sampled, Async)

### When It Runs
- 20% of responses (random sample)
- Always on first 5 turns of a new user's first session
- Always when Tier 1 heuristic warnings fire
- Always when user explicitly gives feedback ("that was good/bad")
- Can be triggered manually for testing

### The Scoring Prompt

```
You are a Conversation DNA Scorer. Your job is to evaluate whether
an AI response sounds like a real human in conversation.

Score this response on each active law (0.0 to 1.0):

USER MESSAGE: {user_message}
USER EMOTION: {detected_emotion}
CONVERSATION CONTEXT: {last_3_turns}
AI RESPONSE: {response}
ACTIVE LAWS AND DIALS: {active_laws_with_dials}

For each law, score:
- 0.0 = completely violated this law
- 0.5 = neutral / law not applicable to this response
- 1.0 = perfectly executed this law

Only score laws with dial >= 3 (inactive laws don't count).

Return JSON:
{
  "scores": {
    "law_01_think_out_loud": 0.7,
    "law_03_emotion_before_analysis": 0.9,
    ...
  },
  "composite": 0.72,
  "top_strength": "law_13_stack_stories",
  "top_weakness": "law_09_incomplete_syntax",
  "one_line_feedback": "Good storytelling but grammar too polished for casual chat"
}
```

### Composite Score Calculation

```python
def calculate_composite(
    scores: dict[str, float],
    dial_positions: dict[str, int],
) -> float:
    """
    Weighted average — laws with higher dials count more.
    A law at dial 10 matters 3x more than a law at dial 3.
    """
    weighted_sum = 0.0
    weight_total = 0.0
    
    for law_name, score in scores.items():
        dial = dial_positions.get(law_name, 5)
        if dial < 3:
            continue  # inactive laws don't count
        
        weight = dial / 10.0  # dial 10 = weight 1.0, dial 3 = weight 0.3
        weighted_sum += score * weight
        weight_total += weight
    
    return weighted_sum / weight_total if weight_total > 0 else 0.5
```

### Score Thresholds

| Composite Score | Verdict | Action |
|----------------|---------|--------|
| 0.0 - 0.3 | FAIL | Should have been caught by Tier 1. Log anomaly. |
| 0.3 - 0.5 | WEAK | Log for learning. Don't regenerate (already delivered). |
| 0.5 - 0.7 | ACCEPTABLE | Normal range. Store scores for trend tracking. |
| 0.7 - 0.85 | GOOD | Target range. Operator is performing well. |
| 0.85 - 1.0 | EXCELLENT | Flag for calibration example harvesting. |

### Score Storage

Deep scores feed directly into Node 4 (Memory) `conv_law_scores` table:

```python
async def store_deep_score(
    self,
    user_id: str,
    operator_name: str,
    scores: dict[str, float],
):
    """Update rolling averages in conv_law_scores."""
    for law_name, score in scores.items():
        law_id = LAW_NAME_TO_ID[law_name]
        
        # Upsert with rolling average
        await supabase.rpc("upsert_law_score", {
            "p_user_id": user_id,
            "p_operator_name": operator_name,
            "p_law_id": law_id,
            "p_law_name": law_name,
            "p_new_score": score,
        })
```

---

## REGENERATION FLOW

When Tier 1 catches a violation:

```
Response generated
    │
    ▼
Tier 1 Quick Check
    │
    ├── NO violations → PASS → Deliver
    │
    └── VIOLATIONS found
        │
        ▼
    Build regeneration prompt:
    "Your response violated these rules:
     - {violation.feedback}
     Rewrite your response following these rules.
     Keep the same meaning but fix the violations."
        │
        ▼
    LLM regenerates (attempt 1)
        │
        ▼
    Tier 1 Quick Check again
        │
        ├── PASS → Deliver
        │
        └── STILL violations
            │
            ▼
        LLM regenerates (attempt 2, FINAL)
            │
            ▼
        Deliver best version + log failure
```

**Max regenerations: 2.** After that, deliver anyway and log the
pattern for future prompt improvement.

**Cost of regeneration:** One additional LLM call per retry.
Expected regeneration rate: <5% of responses (most violations
are caught by the prompt rules, not post-generation).

---

## THE LEARNING LOOP

Scoring isn't just gatekeeping — it's how the system gets better.

```
Deep Score stored
    │
    ▼
conv_law_scores updated (rolling averages)
    │
    ▼
Every 10 sessions, auto-analyze:
    │
    ├── Which laws consistently score low?
    │     → Suggest dial adjustments to operator
    │
    ├── Which laws consistently score high?
    │     → Harvest responses as new calibration examples
    │
    ├── Which law combinations correlate with user engagement?
    │     → Suggest law bundles (e.g., "Law 13 + Law 22 = high engagement for this user")
    │
    └── Is the composite trending up or down?
          → Alert if quality is degrading over time
```

---

## NODE CONNECTIONS

### RECEIVES FROM:
| Source | What | Why |
|--------|------|-----|
| Node 1 (DNA) | Scoring criteria per law + active dials | What to score and how heavily to weight each law |
| Node 3 (Hooks) | Response to validate | The actual text to score |
| Node 4 (Memory) | Historical baselines | "This user's average is 7.3 — is this above or below?" |

### SENDS TO:
| Destination | What | Why |
|------------|------|-----|
| Node 3 (Hooks) | Pass/fail + regeneration feedback | Triggers regeneration or delivery |
| Node 4 (Memory) | Per-law scores | Stored in conv_law_scores for learning |
| Node 1 (DNA) | Law effectiveness data | "Law 2 averages 0.34 — consider lowering default dial" |
| Node 2 (Persona) | Performance feedback | "Scoring low on Law 11 — be messier" |

---

## COST ANALYSIS

| Component | Cost Per Turn | Notes |
|-----------|--------------|-------|
| Tier 1 Quick Check | $0 | Regex only |
| Tier 1 Regeneration (5% of turns) | ~$0.002 | One extra LLM call |
| Tier 2 Deep Score (20% of turns) | ~$0.003 | Haiku-class model |
| Score storage | $0 | Supabase write |
| **Average per turn** | **~$0.001** | Negligible |

---

## VERSION

- v1.0 — 2026-04-13
- Tier 1: 14 absolute violations + 5 heuristic checks
- Tier 2: 27-law deep scoring with composite calculation
- Learning: Auto-suggest dial adjustments every 10 sessions
