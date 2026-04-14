# Node 3: Hook System

The interceptor layer. Fires BEFORE and AFTER every response.
The gatekeeper between the user and the operator.

---

## HOW THIS NODE WORKS

The Hook System is the nerve center of the Conversation Matrix Graph.
Every other node flows THROUGH hooks. Nothing reaches the user without
passing through this layer.

**Key principle:** Hooks don't generate responses. They PREPARE the
context (pre-hooks) and VALIDATE the output (post-hooks). The LLM
does the thinking. Hooks make sure it thinks with the right context
and delivers with the right quality.

---

## WHAT ALREADY EXISTS IN CHAMP

CHAMP's BrainPipeline already has hook-like behavior scattered
throughout the pipeline. This spec consolidates and extends it.

| Current CHAMP | Maps To | Status |
|---------------|---------|--------|
| `HealingLoop.detect()` | Pre-Hook: Friction Detection | EXISTS — keep, extend |
| `MemoryPrefetcher.prefetch()` | Pre-Hook: Memory Injection | EXISTS — keep |
| `SnapshotManager.capture()` | Pre-Hook: Snapshot Load | EXISTS — keep |
| `UserModeling.observe()` | Post-Hook: Learning Extraction | EXISTS — keep |
| `SkillEngine.recall()` | Pre-Hook: Skill Injection | EXISTS — keep |
| `ModeDetector.detect()` | Pre-Hook: Mode Detection | EXISTS — keep |
| (doesn't exist) | Pre-Hook: Emotion Detection | NEW |
| (doesn't exist) | Pre-Hook: Callback Injection | NEW |
| (doesn't exist) | Post-Hook: Conversation Scoring | NEW |
| (doesn't exist) | Post-Hook: Law Violation Detection | NEW |
| (doesn't exist) | Post-Hook: Callback Extraction | NEW |

**Migration:** Not a rewrite. The existing pipeline stays. We add
a HookManager that wraps and organizes these existing steps + new ones.

---

## THE HOOK LIFECYCLE

```
USER INPUT ARRIVES
       │
       ▼
┌─────────────────────────────────────────────┐
│             PRE-HOOKS (before LLM)          │
│                                             │
│  1. Security Scan .............. [EXISTS]   │
│  2. Mode Detection ............. [EXISTS]   │
│  3. Healing/Friction Detection . [EXISTS]   │
│  4. Emotion Detection .......... [NEW]     │
│  5. Memory Snapshot Load ....... [EXISTS]   │
│  6. Memory Prefetch Consume .... [EXISTS]   │
│  7. Callback Injection ......... [NEW]     │
│  8. Skill Recall ............... [EXISTS]   │
│  9. Context Assembly ........... [EXISTS]   │
│                                             │
│  OUTPUT: Enriched prompt ready for LLM      │
└─────────────────────────────────────────────┘
       │
       ▼
   LLM GENERATES RESPONSE
       │
       ▼
┌─────────────────────────────────────────────┐
│            POST-HOOKS (after LLM)           │
│                                             │
│  1. Conversation Scoring ....... [NEW]     │
│     └─ If FAIL → regenerate with feedback   │
│     └─ If PASS → continue to delivery       │
│  2. Law Violation Quick Check .. [NEW]     │
│  3. Callback Extraction ........ [NEW]     │
│  4. Entity/Fact Extraction ..... [NEW]     │
│  5. Message Storage ............ [EXISTS]   │
│  6. Transcript Logging ......... [EXISTS]   │
│  7. Healing Issue Logging ...... [EXISTS]   │
│  8. Memory Prefetch (next turn)  [EXISTS]   │
│  9. User Modeling Observation .. [EXISTS]   │
│                                             │
│  OUTPUT: Validated response → Delivery      │
└─────────────────────────────────────────────┘
       │
       ▼
   NODE 6 (DELIVERY ENGINE) → USER
```

---

## PRE-HOOKS (Detailed)

### Pre-Hook 1: Security Scan [EXISTS]
**Source:** `mind/memory_security.py`
**When:** Every turn
**Cost:** Zero (regex, no LLM)
**What it does:** Scans user message for injection attempts, prompt leaks.

```python
# Already exists in pipeline.py line 155-159
threats = memory_security.scan_content(user_message)
```

**No changes needed.**

---

### Pre-Hook 2: Mode Detection [EXISTS]
**Source:** `brain/mode_detector.py`
**When:** Every turn
**Cost:** Zero (pattern matching, no LLM)
**What it does:** Detects Vibe/Build/Spec mode from user message.

```python
# Already exists in pipeline.py line 162
mode = self.mode_detector.detect(user_message)
```

**Upgrade:** Mode now also triggers DNA dial modifiers from Section 2.
When mode = SPEC, Laws 9, 11, 13 get dial adjustments.

---

### Pre-Hook 3: Friction Detection [EXISTS]
**Source:** `mind/healing.py`
**When:** Every turn
**Cost:** Zero (regex + string similarity, no LLM)
**What it does:** Detects wrong mode, looping, tool failure, user frustration.

```python
# Already exists in pipeline.py line 174-176
healing = self.healing.detect(user_message, mode, recent)
```

**Upgrade:** Add new detection patterns for conversation law violations:

```python
# NEW patterns to add to healing.py

# AI is being too formal (Law 9 violation)
FORMALITY_SIGNALS = [
    re.compile(r"\byou sound like a robot\b", re.IGNORECASE),
    re.compile(r"\bthat sounds like AI\b", re.IGNORECASE),
    re.compile(r"\btoo formal\b", re.IGNORECASE),
    re.compile(r"\bloosen up\b", re.IGNORECASE),
]

# AI is being too agreeable (Law 4/22/24 violation)
PUSHOVER_SIGNALS = [
    re.compile(r"\byou always agree\b", re.IGNORECASE),
    re.compile(r"\bpush back\b", re.IGNORECASE),
    re.compile(r"\bwhat do YOU think\b", re.IGNORECASE),
    re.compile(r"\bgive me your real opinion\b", re.IGNORECASE),
    re.compile(r"\bkeep it 100\b", re.IGNORECASE),
]

# AI is over-explaining (Law 10 violation)
VERBOSE_SIGNALS = [
    re.compile(r"\btoo long\b", re.IGNORECASE),
    re.compile(r"\btl;?dr\b", re.IGNORECASE),
    re.compile(r"\bjust answer\b", re.IGNORECASE),
    re.compile(r"\bget to the point\b", re.IGNORECASE),
    re.compile(r"\bshorter\b", re.IGNORECASE),
]
```

---

### Pre-Hook 4: Emotion Detection [NEW]
**Source:** New module — `mind/emotion_detector.py`
**When:** Every turn
**Cost:** Zero for text (pattern matching). Optional LLM call for deep analysis.
**What it does:** Detects user emotional state from text patterns.
Injects as context so the AI can match energy (Law 26).

**Text-Based Detection (zero cost):**
```python
EMOTION_PATTERNS = {
    "excited": [
        re.compile(r"!{2,}"),                    # multiple exclamation marks
        re.compile(r"\b(amazing|incredible|insane|fire|dope|sick)\b", re.I),
        re.compile(r"\b(let'?s go|yoo+|bro+)\b", re.I),
        re.compile(r"[A-Z]{4,}"),                # ALL CAPS words
    ],
    "frustrated": [
        re.compile(r"\b(ugh|smh|bruh|come on|man)\b", re.I),
        re.compile(r"\b(nothing works|still broken|again)\b", re.I),
        re.compile(r"\b(tired of|sick of|frustrated)\b", re.I),
        re.compile(r"\b(what the|wtf|wth)\b", re.I),
    ],
    "casual": [
        re.compile(r"\b(lol|lmao|haha|😂)\b", re.I),
        re.compile(r"\b(chill|vibes|bet|nah)\b", re.I),
        re.compile(r"\b(what'?s? up|how you|what you)\b", re.I),
    ],
    "serious": [
        re.compile(r"\b(need to talk|real talk|honestly|truth)\b", re.I),
        re.compile(r"\b(important|critical|urgent|concerned)\b", re.I),
        re.compile(r"\b(struggling|worried|stressed)\b", re.I),
    ],
    "curious": [
        re.compile(r"\b(how does|what if|why does|can you explain)\b", re.I),
        re.compile(r"\b(wondering|curious|question)\b", re.I),
        re.compile(r"\?{2,}"),                    # multiple question marks
    ],
    "confident": [
        re.compile(r"\b(I got it|I know|watch this|check this)\b", re.I),
        re.compile(r"\b(nailed it|crushed it|killed it)\b", re.I),
        re.compile(r"\b(easy|simple|no problem)\b", re.I),
    ],
}

# Returns: { "primary": "excited", "secondary": "confident", "intensity": 0.8 }
```

**Voice-Based Detection (future — Node 6 integration):**
When voice is active, prosody features (pitch, speed, volume) feed into
emotion detection. Higher accuracy than text alone. Requires Hume API
or SpeechBrain model (see research findings).

**Injection format:**
```
[EMOTIONAL CONTEXT]
User energy: excited (high intensity)
Recommended response energy: match excitement, be hype
Active energy laws: Law 26 (Energy Shift) at dial 8
```

---

### Pre-Hook 5: Memory Snapshot Load [EXISTS]
**Source:** `brain/memory_snapshot.py`
**When:** First turn of session (frozen for entire session)
**Cost:** One-time Supabase fetch
**What it does:** Loads user profile, lessons, healing patterns from 4 sources.

```python
# Already exists in pipeline.py line 181-183
snapshot = self.snapshot_manager.get(conv_id)
```

**No changes needed.** Snapshot already handles this perfectly.

---

### Pre-Hook 6: Memory Prefetch Consume [EXISTS]
**Source:** `brain/memory_prefetch.py`
**When:** Every turn (consumes cache from previous turn's async fetch)
**Cost:** Zero (consuming pre-cached results)
**What it does:** Injects Mem0 semantic search results, healing context,
user model updates from the background prefetch.

```python
# Already exists in pipeline.py line 192-204
prefetch = self.prefetcher.consume(conv_id)
```

**No changes needed.**

---

### Pre-Hook 7: Callback Injection [NEW]
**Source:** New module — `mind/callback_manager.py`
**When:** Every turn
**Cost:** One Supabase query (fetch recent callbacks)
**What it does:** Pulls recent callback-worthy moments and injects them
into context so the AI can reference them (Law 15, 25).

**What gets injected:**
```python
@dataclass
class CallbackContext:
    recent_callbacks: list[dict]    # last 5 callback-worthy moments
    inside_jokes: list[dict]        # tagged inside jokes
    unresolved_threads: list[dict]  # things left hanging
    last_roast: dict | None         # last roasting moment (for Law 22)

# Injection format:
# [CALLBACK CONTEXT]
# - Earlier this session: user laughed at "doorman analogy" (high engagement)
# - Last session: unresolved disagreement about deployment strategy
# - Inside joke: "sweatlessly" — user finds this funny
# - Available roast: user said they'd beat you at golf but hasn't played in weeks
```

**How callbacks get tagged (Post-Hook 3 feeds this):**
A moment becomes callback-worthy when:
1. User reacted with laughter (lol, haha, 😂)
2. User showed strong emotional response (!! or CAPS)
3. User explicitly called it out ("that's fire", "facts")
4. An analogy or story landed (user referenced it later)
5. A disagreement was left unresolved

---

### Pre-Hook 8: Skill Recall [EXISTS]
**Source:** `mind/skill_engine.py`
**When:** Every turn
**Cost:** One Supabase query
**What it does:** Matches user message against learned skill triggers.

```python
# Already exists in pipeline.py line 212-216
recalled_skills = await self.skill_engine.recall(operator_name, user_message)
```

**No changes needed.**

---

### Pre-Hook 9: Context Assembly [EXISTS]
**Source:** `brain/context_builder.py`
**When:** Every turn
**Cost:** Zero (string assembly)
**What it does:** Combines persona + memory + mode + skills into enriched prompt.

**Upgrade:** Now also includes:
- Emotion context (from Pre-Hook 4)
- Callback context (from Pre-Hook 7)
- Active conversation DNA rules (compiled from dial positions)
- Channel-specific DNA modifiers

**Final assembled context order:**
```
1. OS System Prompt (Layer 1 — cached)
2. Compiled Persona (Layer 2 — cached)
3. Conversation DNA Rules (compiled from dials — cached)
4. ─── DYNAMIC BOUNDARY ─── (everything below rebuilds per turn)
5. Memory Snapshot (frozen for session)
6. Prefetch Context (Mem0 + user model)
7. Emotional Context (detected this turn)
8. Callback Context (recent callbacks + inside jokes)
9. Healing Warnings (if any)
10. Recalled Skills (if any)
11. Conversation History
12. Current User Message
```

---

## POST-HOOKS (Detailed)

### Post-Hook 1: Conversation Scoring [NEW]
**Source:** New — connects to Node 5 (Scoring)
**When:** Every turn (lightweight check). Deep scoring async.
**Cost:** Depends on implementation (see Section 5 for options)
**What it does:** Validates the generated response against active
conversation DNA laws before it reaches the user.

**Two-tier approach:**

**Tier 1 — Quick Check (zero cost, every turn):**
Regex/pattern-based checks for absolute violations:
```python
ABSOLUTE_VIOLATIONS = {
    "numbered_list_in_voice": re.compile(r"^\d+[\.\)]\s", re.MULTILINE),
    "great_question": re.compile(r"\bgreat question\b", re.IGNORECASE),
    "happy_to_help": re.compile(r"\bhappy to help\b", re.IGNORECASE),
    "as_an_ai": re.compile(r"\bas an AI\b", re.IGNORECASE),
    "lets_dive_in": re.compile(r"\blet'?s dive in\b", re.IGNORECASE),
    "key_takeaways": re.compile(r"\bkey takeaways\b", re.IGNORECASE),
    "in_conclusion": re.compile(r"\bin conclusion\b", re.IGNORECASE),
    "moving_on": re.compile(r"\bmoving on to\b", re.IGNORECASE),
    "triple_exclamation": re.compile(r"!{3,}"),
    "excessive_emoji": re.compile(r"[\U0001F600-\U0001F64F]{3,}"),
}

# If ANY absolute violation found → regenerate with feedback
```

**Tier 2 — Deep Score (LLM-based, async, sampled):**
Run on ~20% of responses (configurable). Full 27-law scoring.
Results stored for learning. See Section 5 for full rubric.

**Regeneration flow:**
```
Response generated
    → Tier 1 quick check
    → VIOLATION FOUND
    → Inject feedback: "Your response used a numbered list.
       Rewrite using stories instead of lists."
    → LLM regenerates (max 2 retries)
    → Re-check
    → PASS → Delivery
```

**Max regeneration attempts: 2.** If still failing after 2 retries,
deliver the best version with a log entry for learning.

---

### Post-Hook 2: Law Violation Quick Check [NEW]
**Source:** Extension of Tier 1 scoring
**When:** Every turn
**Cost:** Zero (regex/heuristics)
**What it does:** Fast heuristic checks beyond absolute violations.

```python
HEURISTIC_CHECKS = {
    # Law 9: Incomplete Syntax — is the response TOO perfect?
    "too_perfect": lambda text: (
        all(s.strip().endswith(('.', '!', '?', ':'))
            for s in text.split('\n') if s.strip())
        and len(text) > 100
    ),
    
    # Law 27: Conversation Pulse — is response length monotonous?
    "monotone_length": lambda text, history: (
        abs(len(text) - avg_length(history[-3:])) < 20
        if len(history) >= 3 else False
    ),
    
    # Law 7: Repeat for Weight — synonym cycling detected?
    "synonym_cycling": lambda text: (
        # Check if key phrases are restated with different words
        # instead of repeated for emphasis
        # Implementation: detect paraphrase patterns
        False  # placeholder — needs NLP
    ),
    
    # Law 26: Energy Mismatch
    "energy_mismatch": lambda text, user_emotion: (
        user_emotion == "excited" and not any(
            c in text for c in ['!', 'CAPS', 'bro', 'yo', 'fire', 'dope']
        )
    ),
}
```

**These are warnings, not blockers.** They get logged and fed back
to Node 5 (Scoring) for pattern tracking. Only absolute violations
trigger regeneration.

---

### Post-Hook 3: Callback Extraction [NEW]
**Source:** New module — `mind/callback_extractor.py`
**When:** Every turn (async, non-blocking)
**Cost:** Zero for basic detection, optional LLM for deep extraction
**What it does:** Scans the conversation turn for callback-worthy moments.
Feeds Pre-Hook 7 for future turns.

**Detection patterns:**
```python
CALLBACK_SIGNALS = {
    # User laughed
    "laughter": [
        re.compile(r"\b(lol|lmao|haha|😂|🤣|dead)\b", re.I),
        re.compile(r"\bthat'?s? (funny|hilarious)\b", re.I),
    ],
    
    # User strongly agreed
    "strong_agreement": [
        re.compile(r"\b(facts|exactly|100|bingo|nailed it)\b", re.I),
        re.compile(r"\bthat'?s? (fire|it|perfect)\b", re.I),
    ],
    
    # User referenced AI's earlier point (organic callback)
    "organic_reference": [
        re.compile(r"\blike you said\b", re.I),
        re.compile(r"\byou mentioned\b", re.I),
        re.compile(r"\bthat .+ thing you said\b", re.I),
    ],
    
    # Unresolved disagreement
    "unresolved": [
        re.compile(r"\bagree to disagree\b", re.I),
        re.compile(r"\bI still think\b", re.I),
        re.compile(r"\bnot convinced\b", re.I),
        re.compile(r"\bwe'?ll see\b", re.I),
    ],
    
    # User challenged or roasted back
    "roast_moment": [
        re.compile(r"\byeah right\b", re.I),
        re.compile(r"\byou wish\b", re.I),
        re.compile(r"\bboy stop\b", re.I),
        re.compile(r"\bget out of here\b", re.I),
    ],
}

# Storage format:
# {
#     "type": "laughter",
#     "trigger": "doorman analogy",
#     "user_reaction": "lol that's fire",
#     "session_id": "...",
#     "timestamp": "...",
#     "callback_score": 0.92,
#     "times_called_back": 0
# }
```

---

### Post-Hook 4: Entity/Fact Extraction [NEW]
**Source:** New — feeds Node 4 (Memory) Conversation Graph
**When:** Async, non-blocking, every turn
**Cost:** Optional LLM call (can batch at session end instead)
**What it does:** Extracts entities, facts, and relationship signals
from the conversation turn. Feeds the future Conversation Graph.

**Two modes:**

**Mode A — Lightweight (per turn, no LLM):**
```python
# Extract mentions of people, places, dates, topics
# Pattern matching on named entities
# Detect fact statements ("I just started playing golf")
# Detect opinion statements ("I think we should...")
# Detect emotional shifts (sentiment change from previous turn)
```

**Mode B — Deep (session end, LLM-based):**
```python
# Full transcript analysis
# Entity relationship extraction
# Fact evolution detection (old fact → new fact)
# Emotional arc mapping
# Relationship stage assessment
# Already partially exists via LearningLoop.capture()
```

**Default: Mode A per turn + Mode B at session end.**

---

### Post-Hook 5-9: Existing Pipeline Steps [EXISTS]

These already work in the current BrainPipeline. No changes needed:

| Post-Hook | Source | What It Does |
|-----------|--------|-------------|
| 5. Message Storage | `memory.store_message()` | Store to Supabase |
| 6. Transcript Logging | `TranscriptLogger` | Log full transcript |
| 7. Healing Issue Logging | `memory.insert_healing()` | Log friction events |
| 8. Memory Prefetch | `prefetcher.prefetch()` | Background fetch for next turn |
| 9. User Modeling | `user_modeling.observe()` | Dual-peer observation |

---

## THE HOOK MANAGER

New class that wraps the pipeline's existing steps into a clean
hook architecture. Not a rewrite — an organizational layer.

```python
class HookManager:
    """
    Manages pre and post hooks for the Conversation Matrix.
    
    Wraps existing pipeline steps (HealingLoop, MemoryPrefetch, etc.)
    and adds new hooks (emotion detection, callback injection, scoring).
    
    Design:
    - Hooks run in defined order
    - Each hook receives context, can add to it
    - Pre-hooks build the enriched context
    - Post-hooks validate and extract from the response
    - Hooks are non-fatal — failure logs but doesn't block
    """
    
    def __init__(self, config: HookConfig):
        # Existing components (injected from BrainPipeline)
        self.healing = None          # HealingLoop
        self.mode_detector = None    # ModeDetector
        self.snapshot_manager = None # SnapshotManager
        self.prefetcher = None       # MemoryPrefetcher
        self.skill_engine = None     # SkillEngine
        self.user_modeling = None    # UserModeling
        
        # New components
        self.emotion_detector = EmotionDetector()
        self.callback_manager = CallbackManager()
        self.callback_extractor = CallbackExtractor()
        self.conversation_scorer = ConversationScorer()
        
        # Config
        self.config = config
        self.max_regenerations = 2
    
    async def run_pre_hooks(
        self,
        user_message: str,
        session_id: str,
        user_id: str,
        conversation_history: list[dict],
    ) -> HookContext:
        """
        Run all pre-hooks and return enriched context.
        
        Returns HookContext with:
        - mode: detected output mode
        - emotion: detected user emotion
        - memory_context: assembled memory string
        - callbacks: available callback moments
        - healing: friction warnings
        - skills: recalled skills
        - dna_modifiers: mode/channel adjustments to law dials
        """
        ctx = HookContext(user_message=user_message)
        
        # 1. Security (existing)
        ctx.threats = memory_security.scan_content(user_message)
        
        # 2. Mode detection (existing)
        ctx.mode = self.mode_detector.detect(user_message)
        
        # 3. Friction detection (existing + extended)
        ctx.healing = self.healing.detect(
            user_message, ctx.mode, conversation_history
        )
        if ctx.healing.mode_override:
            ctx.mode = ctx.healing.mode_override
        
        # 4. Emotion detection (NEW)
        ctx.emotion = self.emotion_detector.detect(user_message)
        
        # 5. Memory snapshot (existing)
        ctx.snapshot = self.snapshot_manager.get(session_id)
        
        # 6. Prefetch consume (existing)
        ctx.prefetch = self.prefetcher.consume(session_id)
        
        # 7. Callback injection (NEW)
        ctx.callbacks = await self.callback_manager.get_active(
            session_id=session_id,
            user_id=user_id,
            limit=5,
        )
        
        # 8. Skill recall (existing)
        ctx.skills = await self.skill_engine.recall(
            operator_name=ctx.operator_name,
            user_message=user_message,
        )
        
        # 9. Compile DNA modifiers based on mode + channel
        ctx.dna_modifiers = self._compile_dna_modifiers(ctx.mode, ctx.channel)
        
        return ctx
    
    async def run_post_hooks(
        self,
        response: str,
        ctx: HookContext,
    ) -> PostHookResult:
        """
        Run all post-hooks. Returns validated response or regeneration request.
        """
        result = PostHookResult(response=response)
        
        # 1. Quick score (zero cost)
        violations = self.conversation_scorer.quick_check(response)
        if violations:
            result.needs_regeneration = True
            result.regeneration_feedback = self._build_feedback(violations)
            return result
        
        # 2. Heuristic checks (zero cost)
        warnings = self.conversation_scorer.heuristic_check(
            response, ctx.emotion, ctx.conversation_history
        )
        result.warnings = warnings  # logged, not blocking
        
        # 3-4. Async, non-blocking extractions
        asyncio.create_task(
            self.callback_extractor.extract(
                user_message=ctx.user_message,
                response=response,
                session_id=ctx.session_id,
            )
        )
        
        # 5-9. Existing pipeline steps (unchanged)
        # These continue to run as they do now in BrainPipeline
        
        result.passed = True
        return result
```

---

## INTEGRATION WITH BRAINPIPELINE

The existing `BrainPipeline.handle_request()` and `handle_stream()`
get a small refactor — NOT a rewrite:

```python
# CURRENT pipeline.py flow:
# 1. Extract user message
# 2. Mode detection
# 3. Healing detection
# 4. Memory fetch
# 5. Context build
# 6. LLM call
# 7. Storage + prefetch

# UPGRADED pipeline.py flow:
# 1. hook_manager.run_pre_hooks()     ← wraps steps 1-5
# 2. Context build (with hook output)
# 3. LLM call
# 4. hook_manager.run_post_hooks()    ← wraps step 7 + new checks
# 5. If regeneration needed → loop back to step 3 (max 2x)
# 6. Deliver via Node 6
```

The pipeline gets SIMPLER, not more complex. The HookManager
encapsulates the growing list of pre/post processing steps.

---

## NODE CONNECTIONS

### RECEIVES FROM:
| Source | What | Why |
|--------|------|-----|
| Node 1 (DNA) | Anti-patterns per law | "Flag if response uses bullet points" |
| Node 2 (Persona) | Mode triggers, personality-specific patterns | "If user says 'keep it 100', switch to direct mode" |
| Node 4 (Memory) | Recalled memories, callbacks, user model | Injected into prompt context |
| Node 5 (Scoring) | Pass/fail result + feedback | Triggers regeneration or delivery |

### SENDS TO:
| Destination | What | Why |
|------------|------|-----|
| Node 2 (Persona) | Emotion context + memory context | AI knows user's state and history |
| Node 4 (Memory) | Extracted callbacks, entities, facts | New data to store |
| Node 5 (Scoring) | Generated response to validate | Score before delivery |
| Node 6 (Delivery) | Go signal + validated response | "Score passed — deliver this" |

---

## NEW FILES TO CREATE

| File | Purpose | Priority |
|------|---------|----------|
| `mind/emotion_detector.py` | Text-based emotion detection (regex) | HIGH |
| `mind/callback_manager.py` | Store/retrieve callback-worthy moments | HIGH |
| `mind/callback_extractor.py` | Detect callback-worthy moments in turns | MEDIUM |
| `brain/hook_manager.py` | Wraps all hooks into clean interface | HIGH |
| `brain/conversation_scorer.py` | Quick check + heuristic scoring | HIGH |

**Existing files to extend:**
| File | Change | Priority |
|------|--------|----------|
| `mind/healing.py` | Add formality, pushover, verbose signal patterns | MEDIUM |
| `brain/pipeline.py` | Refactor to use HookManager | MEDIUM |
| `brain/context_builder.py` | Accept emotion + callback context | MEDIUM |

---

## PERFORMANCE BUDGET

Every pre-hook must run in under 50ms total. Every post-hook must
be non-blocking (async) except for Tier 1 scoring (which is regex
and runs in <5ms).

| Hook | Cost | Latency |
|------|------|---------|
| Security scan | Zero (regex) | <1ms |
| Mode detection | Zero (regex) | <1ms |
| Healing detection | Zero (regex) | <2ms |
| Emotion detection | Zero (regex) | <2ms |
| Snapshot load | Zero (cached) | <1ms |
| Prefetch consume | Zero (cached) | <1ms |
| Callback injection | Supabase query | <20ms |
| Skill recall | Supabase query | <20ms |
| Context assembly | String concat | <1ms |
| **Total pre-hooks** | | **<50ms** |
| Tier 1 scoring | Zero (regex) | <5ms |
| Deep scoring | LLM call (async, sampled) | non-blocking |
| Callback extraction | Zero (regex, async) | non-blocking |
| Entity extraction | Zero or LLM (async) | non-blocking |
| **Total post-hooks (blocking)** | | **<5ms** |

**Zero additional latency on the critical path.** Everything expensive
is either cached, async, or sampled.

---

## VERSION

- v1.0 — 2026-04-13
- Source: CHAMP V3 BrainPipeline + Claude Code hook architecture
- Migration: Wraps existing pipeline, doesn't replace it
