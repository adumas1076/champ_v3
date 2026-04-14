# Node 4: Dual Memory

Everything the system remembers. Static rules + dynamic learnings.
Future: Conversation Graph for temporal relationship tracking.

---

## HOW THIS NODE WORKS

Memory is the only node that PERSISTS between sessions. Everything
else resets. Memory is what makes conversation #47 feel different
from conversation #1 — because the system KNOWS you now.

**Key principle:** CHAMP's existing memory system is the foundation.
We don't replace it. We add 5 new tables for conversation-specific
tracking and define how they feed the other nodes.

---

## WHAT ALREADY EXISTS (KEEP ALL)

| Component | What It Does | Location |
|-----------|-------------|----------|
| `mem_profile` | User facts, preferences, history | Supabase |
| `mem_lessons` | Proven patterns, draft → standard → locked | Supabase |
| `mem_healing` | Friction patterns, prevention rules | Supabase |
| `user_model_observations` | Dual-peer observations (user + AI) | Supabase |
| `user_model_representations` | Synthesized user/AI models | Supabase |
| `operator_skills` | Learned reusable skills with effectiveness | Supabase |
| `conversations` | Full session transcripts + metadata | Supabase |
| `messages` | Individual messages with role/mode | Supabase |
| `call_evaluations` | Scored session evaluations | Supabase |
| `SnapshotManager` | Frozen session-start memory capture | Python |
| `MemoryPrefetcher` | Async background fetch for next turn | Python |
| `LearningLoop` | Post-session extraction pipeline | Python |
| `UserModeling` | Dual-peer observation system | Python |
| `SkillEngine` | Skill creation and promotion | Python |
| `SessionSearch` | FTS5 full-text search across sessions | SQLite |
| `LettaMemory` | 5 self-editing memory blocks per operator | Letta API |
| `Mem0Memory` | Global shared semantic search | Mem0 API |
| `ContextCompressor` | Smart context compression (head/tail protection) | Python |

**Total existing components: 17.** All stay. All work.

---

## WHAT WE ADD (5 New Tables)

### Table 1: `conv_callbacks`
Callback-worthy moments that the AI can reference in future turns/sessions.

```sql
CREATE TABLE conv_callbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    
    -- What happened
    callback_type TEXT NOT NULL,          -- laughter | strong_agreement | organic_reference | unresolved | roast_moment
    trigger_text TEXT NOT NULL,           -- what the AI said that triggered the reaction
    user_reaction TEXT,                   -- what the user said in response
    context_summary TEXT,                 -- brief summary of the moment
    
    -- Scoring
    engagement_score REAL DEFAULT 0.5,    -- 0.0 to 1.0, how strong the reaction was
    times_called_back INTEGER DEFAULT 0,  -- how many times this has been referenced again
    last_called_back TIMESTAMPTZ,         -- when it was last referenced
    
    -- Lifecycle
    status TEXT DEFAULT 'active',         -- active | stale | archived
    created_at TIMESTAMPTZ DEFAULT now(),
    
    -- Indexes
    CONSTRAINT valid_type CHECK (callback_type IN (
        'laughter', 'strong_agreement', 'organic_reference',
        'unresolved', 'roast_moment', 'inside_joke', 'analogy_landed'
    ))
);

CREATE INDEX idx_callbacks_user ON conv_callbacks(user_id, status);
CREATE INDEX idx_callbacks_score ON conv_callbacks(engagement_score DESC);
```

**Fed by:** Post-Hook 3 (Callback Extraction)
**Consumed by:** Pre-Hook 7 (Callback Injection)

---

### Table 2: `conv_emotional_arcs`
Mood trajectory per session. How the user's energy changed over time.

```sql
CREATE TABLE conv_emotional_arcs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    
    -- Emotional data points (ordered by turn)
    arc_data JSONB NOT NULL,
    -- Format: [
    --   {"turn": 1, "emotion": "excited", "intensity": 0.8, "timestamp": "..."},
    --   {"turn": 5, "emotion": "frustrated", "intensity": 0.6, "timestamp": "..."},
    --   {"turn": 12, "emotion": "recovered", "intensity": 0.7, "timestamp": "..."}
    -- ]
    
    -- Summary
    dominant_emotion TEXT,                -- most frequent emotion this session
    arc_shape TEXT,                       -- rising | falling | valley | peak | flat | roller_coaster
    peak_moment TEXT,                     -- brief description of highest energy moment
    valley_moment TEXT,                   -- brief description of lowest energy moment
    
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_arcs_user ON conv_emotional_arcs(user_id);
```

**Fed by:** Pre-Hook 4 (Emotion Detection) accumulated over session, written at session end
**Consumed by:** Memory snapshot for next session — "last session ended on frustrated note"

---

### Table 3: `conv_law_scores`
Which of the 27 Laws land best with each user.

```sql
CREATE TABLE conv_law_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    
    -- Per-law tracking
    law_id INTEGER NOT NULL,              -- 1-27
    law_name TEXT NOT NULL,               -- "think_out_loud", "roasting_is_love", etc.
    
    -- Aggregate scores
    avg_score REAL DEFAULT 0.5,           -- rolling average effectiveness
    times_scored INTEGER DEFAULT 0,       -- how many times this law was evaluated
    times_positive INTEGER DEFAULT 0,     -- user responded positively
    times_negative INTEGER DEFAULT 0,     -- user responded negatively
    
    -- Current dial recommendation
    recommended_dial REAL,                -- suggested dial position based on data
    
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(user_id, operator_name, law_id)
);

CREATE INDEX idx_law_scores_user ON conv_law_scores(user_id, operator_name);
```

**Fed by:** Post-Hook 1 (Conversation Scoring) results
**Consumed by:** Node 1 (DNA) — auto-adjusts dials based on what works

---

### Table 4: `conv_relationship_stage`
Tracks how the relationship evolves over time.

```sql
CREATE TABLE conv_relationship_stage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    
    -- Current stage
    stage TEXT DEFAULT 'new',             -- new | familiar | close | day_one
    session_count INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    
    -- Signals that drove stage changes
    stage_history JSONB DEFAULT '[]',
    -- Format: [
    --   {"from": "new", "to": "familiar", "session": 4, "signal": "user started using slang"},
    --   {"from": "familiar", "to": "close", "session": 15, "signal": "user shared personal story"}
    -- ]
    
    -- Behavioral modifiers at current stage
    roast_modifier INTEGER DEFAULT 0,
    formality_level TEXT DEFAULT 'warm but measured',
    
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(user_id, operator_name)
);
```

**Fed by:** Post-session analysis (LearningLoop extension)
**Consumed by:** Node 2 (Persona) — adjusts roasting, formality, closeness

---

### Table 5: `conv_unresolved_threads`
Disagreements, open questions, things left hanging.

```sql
CREATE TABLE conv_unresolved_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    
    -- What's unresolved
    topic TEXT NOT NULL,                  -- brief description
    user_position TEXT,                   -- what the user thinks
    operator_position TEXT,               -- what the AI thinks
    context_snippet TEXT,                 -- relevant conversation excerpt
    
    -- Status
    status TEXT DEFAULT 'open',           -- open | revisited | resolved | stale
    revisit_count INTEGER DEFAULT 0,
    last_revisited TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_unresolved_user ON conv_unresolved_threads(user_id, status);
```

**Fed by:** Post-Hook 3 (Callback Extraction — unresolved type)
**Consumed by:** Pre-Hook 7 (Callback Injection) — "we never resolved X"

---

## MEMORY FLOW DIAGRAM

```
SESSION START
    │
    ├── SnapshotManager.capture() [EXISTS]
    │     ├── Supabase (profile, lessons, healing)
    │     ├── Letta (5 memory blocks)
    │     ├── Mem0 (semantic search)
    │     ├── UserModeling (representations)
    │     └── NEW: conv_relationship_stage (current stage + modifiers)
    │     └── NEW: conv_law_scores (top/bottom laws for this user)
    │     └── NEW: conv_callbacks (last 5 active, top 3 inside jokes)
    │     └── NEW: conv_unresolved_threads (open threads)
    │     └── NEW: conv_emotional_arcs (last session's arc summary)
    │
    ▼
    FROZEN SNAPSHOT (immutable for session, prefix cache friendly)
    │
EACH TURN
    │
    ├── Pre-Hook 7: Callback Injection
    │     └── Query conv_callbacks WHERE status='active' ORDER BY engagement_score DESC LIMIT 5
    │
    ├── Pre-Hook 4: Emotion Detection
    │     └── Accumulate emotion data points for arc
    │
    ├── [LLM generates response]
    │
    ├── Post-Hook 3: Callback Extraction
    │     └── INSERT INTO conv_callbacks (if callback-worthy moment detected)
    │
    ├── Post-Hook 1: Conversation Scoring
    │     └── UPDATE conv_law_scores (increment times_scored, update avg_score)
    │
    └── Post-Hook 9: User Modeling [EXISTS]
          └── INSERT INTO user_model_observations
    │
SESSION END
    │
    ├── LearningLoop.capture() [EXISTS]
    │     └── UPDATE mem_profile, mem_lessons
    │
    ├── NEW: Write emotional arc
    │     └── INSERT INTO conv_emotional_arcs (accumulated data points)
    │
    ├── NEW: Update relationship stage
    │     └── UPDATE conv_relationship_stage (session_count++, check stage transition)
    │
    ├── NEW: Stale callback cleanup
    │     └── UPDATE conv_callbacks SET status='stale' WHERE times_called_back=0 AND age > 30 days
    │
    └── SkillEngine.extract() [EXISTS]
          └── INSERT INTO operator_skills
```

---

## SNAPSHOT UPGRADE

The existing SnapshotManager adds 5 new data points to the frozen snapshot:

```python
# Added to snapshot.format() output:

[RELATIONSHIP]
Stage: close (session 23, 1,847 total messages)
Roast modifier: +2
Formality: full homie energy

[CONVERSATION LAWS - THIS USER]
Top performing: Law 13 (stack stories) 0.91, Law 8 (cultural shorthand) 0.88, Law 22 (roasting) 0.85
Low performing: Law 9 (vulnerability) 0.31, Law 2 (interrupt self) 0.34
Recommendation: Lean into stories and banter. Avoid vulnerability-heavy responses.

[ACTIVE CALLBACKS]
- "doorman analogy" — landed hard, session 18, engagement 0.94
- "sweatlessly" — inside joke, referenced 4x across sessions
- "pizza vending machine tangent" — user brought it back twice

[UNRESOLVED]
- Deployment strategy disagreement (session 21) — user wants monolith, operator suggested microservices. Never resolved.

[LAST SESSION ENERGY]
Arc: valley (started excited, hit frustration at turn 8, recovered by turn 15)
Dominant emotion: focused
Note: Session ended on positive note after breakthrough
```

---

## CONTEXT COMPACTION UPGRADE

When compaction fires mid-session, add CC's re-injection pattern:

```python
# After compaction, ALWAYS re-inject from disk:
# 1. Conversation DNA rules (27 Laws at current dials) — from Node 1
# 2. Persona core identity (who the operator IS) — from Node 2
# 3. Last 3 active callbacks — from conv_callbacks
# 4. Current relationship stage — from conv_relationship_stage
# 5. Unresolved threads — from conv_unresolved_threads

# These NEVER get summarized away. They are the relationship.
```

---

## NODE CONNECTIONS

### RECEIVES FROM:
| Source | What | Stored Where |
|--------|------|-------------|
| Node 3 (Hooks) | Callbacks, entities, facts, emotions | conv_callbacks, conv_emotional_arcs |
| Node 5 (Scoring) | Law effectiveness per response | conv_law_scores |
| Node 2 (Persona) | Operator identity facts | Letta persona block |
| Node 1 (DNA) | What to track per law | conv_law_scores schema |

### SENDS TO:
| Destination | What | Source |
|------------|------|--------|
| Node 3 (Hooks) | Memories, callbacks, user model for injection | Snapshot + prefetch + callback query |
| Node 2 (Persona) | Relationship stage, user model | conv_relationship_stage + user_model_representations |
| Node 1 (DNA) | Law preference profile per user | conv_law_scores |
| Node 5 (Scoring) | Historical baselines for comparison | conv_law_scores averages |

---

## VERSION

- v1.0 — 2026-04-13
- Migration: 5 new Supabase tables + snapshot upgrade + compaction upgrade
- Zero disruption to existing memory system
