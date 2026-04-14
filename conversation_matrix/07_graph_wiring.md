# Graph Wiring: Node-to-Node Data Contracts

Every connection between nodes. What format. What triggers it.
What payload flows through. No ambiguity.

---

## COMPLETE EDGE MAP

### DNA → Persona
**Trigger:** Operator boot (once at session start)
**Payload:** Compiled behavioral rules based on active dial positions
**Format:** Markdown string appended to persona prompt
**Contract:**
```python
@dataclass
class DNAToPersona:
    compiled_rules: str          # markdown CONVERSATION RULES section
    active_laws: list[int]       # law IDs with dial >= 3
    dial_positions: dict[int, int]  # {law_id: dial_value}
```

### DNA → Scoring
**Trigger:** Operator boot (once), updated if dials change
**Payload:** Full scoring rubric per active law
**Format:** Dict of law_id → scoring criteria
**Contract:**
```python
@dataclass
class DNAToScoring:
    rubric: dict[int, LawScoringCriteria]
    absolute_violations: list[ViolationRule]
    heuristic_checks: list[HeuristicRule]
    dial_weights: dict[int, float]  # for composite calculation
```

### DNA → Hooks
**Trigger:** Operator boot (once)
**Payload:** Anti-patterns to watch for per active law
**Format:** List of regex patterns + feedback strings
**Contract:**
```python
@dataclass
class DNAToHooks:
    watch_patterns: list[WatchPattern]  # patterns that violate laws
    channel_modifiers: dict[str, dict[int, int]]  # voice/text/spec adjustments
```

### DNA → Memory
**Trigger:** Operator boot (once)
**Payload:** Which dimensions to track per law
**Format:** List of trackable metrics
**Contract:**
```python
@dataclass
class DNAToMemory:
    trackable_laws: list[int]    # which laws to score and store
    law_names: dict[int, str]    # {1: "think_out_loud", ...}
```

### DNA → Delivery
**Trigger:** Operator boot + per-turn mode changes
**Payload:** Style constraints for output formatting
**Format:** Rules dict
**Contract:**
```python
@dataclass
class DNAToDelivery:
    no_lists_in: list[str]       # ["voice", "text"]
    imperfection_dial: int       # Law 9 position
    repetition_allowed: bool     # Law 7 dial >= 3
    max_response_variability: float  # Law 27 dial → pacing range
```

---

### Persona → DNA
**Trigger:** Operator boot (once)
**Payload:** Dial override positions from operator config
**Format:** Dict of law_id → override value
**Contract:**
```python
@dataclass
class PersonaToDNA:
    dial_overrides: dict[int, int]    # {3: 8, 8: 8, 12: 8, ...}
    mode_modifiers: dict[str, dict[int, int]]  # per-mode adjustments
```

### Persona → Hooks
**Trigger:** Operator boot (once)
**Payload:** Mode triggers + personality-specific detection patterns
**Format:** Trigger rules
**Contract:**
```python
@dataclass
class PersonaToHooks:
    mode_triggers: dict[str, list[str]]  # {"vibe": ["quick", "thoughts?"], ...}
    name_switch_rules: dict[str, str]    # {"default": "champ", "serious": "Anthony"}
    never_say: list[str]                 # phrases to always catch
```

### Persona → Delivery
**Trigger:** Operator boot (once)
**Payload:** Voice and formatting configuration
**Format:** Config dict
**Contract:**
```python
@dataclass
class PersonaToDelivery:
    voice_provider: str          # "openai" | "fish_s2" | "chatterbox"
    voice_id: str                # "ash"
    voice_temperature: float     # 0.8
    avg_word_count: int          # 289
    uses_bold: bool              # True
    uses_caps: bool              # True
    formatting_mode: str         # "conversational" | "structured" | "minimal"
```

### Persona → Memory
**Trigger:** Operator boot (once)
**Payload:** Operator identity for persistence
**Format:** Identity dict
**Contract:**
```python
@dataclass
class PersonaToMemory:
    operator_name: str           # "champ"
    identity_summary: str        # compressed identity for Letta persona block
    relational_stance: str       # "teammate"
```

---

### Hooks → Persona (Pre-Hook Output)
**Trigger:** Every turn (pre-hooks complete)
**Payload:** Enriched context for prompt injection
**Format:** Context strings
**Contract:**
```python
@dataclass
class HooksToPersona:
    emotion_context: str         # "[EMOTIONAL CONTEXT] User energy: excited"
    memory_context: str          # assembled memory snapshot + prefetch
    callback_context: str        # "[CALLBACKS] doorman analogy, sweatlessly joke"
    healing_warnings: str        # "[HEALING WARNING] looping detected"
    mode: str                    # "vibe" | "build" | "spec"
    dna_modifiers: dict[int, int]  # mode/channel adjustments to dials
```

### Hooks → Scoring (Post-Hook)
**Trigger:** Every turn (response generated)
**Payload:** Response text to validate
**Format:** Response + context
**Contract:**
```python
@dataclass
class HooksToScoring:
    response: str                # the generated response text
    channel: str                 # "voice" | "text" | "spec"
    mode: str                    # "vibe" | "build" | "spec"
    user_emotion: str            # detected emotion
    conversation_history: list[str]  # last 3-5 assistant responses
```

### Hooks → Memory (Post-Hook Extractions)
**Trigger:** Every turn (async, non-blocking)
**Payload:** Extracted callbacks, entities, facts
**Format:** Extraction results
**Contract:**
```python
@dataclass
class HooksToMemory:
    callbacks: list[CallbackEvent]    # new callback-worthy moments
    emotion_data_point: EmotionPoint  # this turn's emotion reading
    entities: list[Entity]            # extracted entities (future)
    facts: list[Fact]                 # extracted facts (future)
```

### Hooks → Delivery (Go Signal)
**Trigger:** Post-hooks complete + scoring passed
**Payload:** Validated response + delivery instructions
**Format:** Delivery package
**Contract:**
```python
@dataclass
class HooksToDelivery:
    response: str                # validated response text
    channel: str                 # "voice" | "text" | "spec"
    user_emotion: str            # for prosody tag selection
    mode: str                    # affects delivery formatting
    go: bool                     # True = deliver, False = blocked
```

---

### Memory → Hooks (Pre-Hook Injection)
**Trigger:** Every turn (pre-hooks request context)
**Payload:** Memories, callbacks, user model
**Format:** Formatted strings for prompt injection
**Contract:**
```python
@dataclass
class MemoryToHooks:
    snapshot: str                # frozen session snapshot
    prefetch: str                # Mem0 + user model dynamic context
    callbacks: list[dict]        # active callbacks for injection
    unresolved: list[dict]       # open threads
    relationship_stage: str      # "close"
    roast_modifier: int          # +2
    law_preferences: dict[int, float]  # {13: 0.91, 8: 0.88}
```

### Memory → Persona
**Trigger:** Session start (snapshot injection)
**Payload:** User model + relationship history
**Format:** Formatted context string
**Contract:**
```python
@dataclass
class MemoryToPersona:
    relationship_stage: str      # "close"
    session_count: int           # 23
    total_messages: int          # 1847
    formality_level: str         # "full homie energy"
    roast_modifier: int          # +2
    user_model: str              # synthesized representation
    last_session_arc: str        # "valley — started excited, hit frustration, recovered"
```

### Memory → DNA
**Trigger:** Session start (law preferences loaded)
**Payload:** Which laws work best with this user
**Format:** Law scores
**Contract:**
```python
@dataclass
class MemoryToDNA:
    law_scores: dict[int, float]     # {13: 0.91, 8: 0.88, 9: 0.31}
    recommended_adjustments: dict[int, int]  # {9: -2, 22: +1}
```

### Memory → Scoring
**Trigger:** Session start (baselines loaded)
**Payload:** Historical performance data
**Format:** Baseline metrics
**Contract:**
```python
@dataclass
class MemoryToScoring:
    avg_composite: float         # 0.73
    law_averages: dict[int, float]  # per-law rolling averages
    trend: str                   # "improving" | "stable" | "declining"
```

---

### Scoring → Hooks
**Trigger:** Every turn (after scoring)
**Payload:** Pass/fail + feedback
**Format:** Scoring result
**Contract:**
```python
@dataclass
class ScoringToHooks:
    passed: bool
    violations: list[dict]       # absolute violations found
    warnings: list[dict]         # heuristic warnings
    feedback: str                # regeneration instructions (if failed)
    composite_score: float       # 0.0-1.0 (if deep scored)
```

### Scoring → Memory
**Trigger:** Every deep-scored turn (async)
**Payload:** Per-law scores
**Format:** Score dict
**Contract:**
```python
@dataclass
class ScoringToMemory:
    law_scores: dict[int, float]  # {1: 0.7, 3: 0.9, ...}
    composite: float
    session_id: str
    turn_number: int
```

### Scoring → DNA
**Trigger:** Every 10 sessions (batch analysis)
**Payload:** Law effectiveness report
**Format:** Recommendation dict
**Contract:**
```python
@dataclass
class ScoringToDNA:
    effectiveness: dict[int, float]     # per-law averages across all sessions
    recommended_default_changes: dict[int, int]  # suggested new defaults
    high_performers: list[int]          # laws that consistently score well
    low_performers: list[int]           # laws that consistently score poorly
```

### Scoring → Persona
**Trigger:** Every deep-scored turn
**Payload:** Performance feedback
**Format:** Feedback string
**Contract:**
```python
@dataclass
class ScoringToPersona:
    feedback: str                # "Scoring low on Law 11 — be messier"
    top_strength: str            # "law_13_stack_stories"
    top_weakness: str            # "law_09_incomplete_syntax"
```

---

### Delivery → Memory
**Trigger:** Every turn (after delivery)
**Payload:** What was actually delivered + timing
**Format:** Delivery receipt
**Contract:**
```python
@dataclass
class DeliveryToMemory:
    delivered_text: str          # final text (after splitting/imperfection)
    channel: str                 # "voice" | "text"
    bubbles: int                 # number of text bubbles (text only)
    total_delivery_ms: int       # total time to deliver
    timestamp: str               # ISO timestamp
```

### Delivery → Hooks
**Trigger:** Every turn (delivery complete)
**Payload:** Confirmation
**Format:** Simple signal
**Contract:**
```python
@dataclass
class DeliveryToHooks:
    delivered: bool
    delivery_id: str
```

---

## EDGE COUNT SUMMARY

| From → To | Edges | Trigger |
|-----------|-------|---------|
| DNA → Others | 5 | Boot |
| Persona → Others | 4 | Boot |
| Hooks → Others | 4 | Per turn |
| Memory → Others | 4 | Boot + per turn |
| Scoring → Others | 4 | Per turn |
| Delivery → Others | 2 | Per turn |
| **Total edges** | **23** | |

---

## VERSION

- v1.0 — 2026-04-13
- 23 edges, all typed with dataclass contracts
