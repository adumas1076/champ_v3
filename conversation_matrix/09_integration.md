# Integration with CHAMP Codebase

How the Conversation Matrix Graph wires into the existing
CHAMP V3 codebase. What changes. What stays. Migration plan.

---

## PRINCIPLE: WRAP, DON'T REWRITE

The existing BrainPipeline, HealingLoop, PersonaLoader, SnapshotManager,
and all other components STAY. The Conversation Matrix adds a layer
on top — organizing existing functionality and adding new capabilities.

**Zero existing tests should break.**

---

## FILE CHANGES MAP

### NEW FILES (Create)

| File | Purpose | Priority |
|------|---------|----------|
| `conversation_matrix/__init__.py` | Package init | HIGH |
| `conversation_matrix/dna_compiler.py` | Compile 27 Laws into prompt rules from dial positions | HIGH |
| `conversation_matrix/hook_manager.py` | Wraps pre/post hooks into clean interface | HIGH |
| `conversation_matrix/conversation_scorer.py` | Tier 1 quick check + Tier 2 deep scoring | HIGH |
| `mind/emotion_detector.py` | Text-based emotion detection (regex) | HIGH |
| `mind/callback_manager.py` | Store/retrieve callback-worthy moments | HIGH |
| `mind/callback_extractor.py` | Detect callback signals in turns | MEDIUM |
| `brain/delivery_engine.py` | Delivery orchestrator (voice/text routing) | MEDIUM |
| `brain/message_splitter.py` | Split responses into chat bubbles | MEDIUM |
| `brain/typing_simulator.py` | Calculate typing delays | MEDIUM |
| `brain/imperfection_engine.py` | Strategic text imperfection | LOW |
| `brain/prosody_tagger.py` | Voice prosody tag injection | LOW |
| `brain/backchannel_manager.py` | Backchannel clip timing | LOW |

### MODIFIED FILES (Extend)

| File | Change | Risk |
|------|--------|------|
| `brain/pipeline.py` | Add hook_manager calls around existing flow | LOW — additive, no removals |
| `brain/persona_loader.py` | Add DNA compilation step after persona load | LOW — appends, doesn't modify |
| `brain/context_builder.py` | Accept emotion + callback context params | LOW — new optional params |
| `brain/memory_snapshot.py` | Add new table queries to snapshot capture | LOW — additive |
| `mind/healing.py` | Add formality/pushover/verbose signal patterns | LOW — new patterns only |
| `operators/configs/champ.yaml` | Add conversation_dna section | LOW — backward compatible |

### UNCHANGED FILES (No Touch)

Everything else. Specifically:
- `agent.py` — no changes
- `operators/base.py` — no changes
- `operators/champ.py` — no changes
- `brain/llm_client.py` — no changes
- `brain/mode_detector.py` — no changes
- `brain/context_compressor.py` — no changes
- `mind/learning.py` — no changes
- `mind/user_modeling.py` — no changes
- `mind/skill_engine.py` — no changes
- `mind/session_search.py` — no changes
- `mind/memory_security.py` — no changes
- `mind/letta_memory.py` — no changes
- `mind/mem0_memory.py` — no changes
- All existing tests — no changes

---

## DATABASE MIGRATION

### New Supabase Migration: `013_conversation_matrix.sql`

```sql
-- Conversation Matrix Graph — 5 new tables
-- Migration: 013_conversation_matrix.sql
-- Date: 2026-04-13

-- 1. Callback-worthy moments
CREATE TABLE IF NOT EXISTS conv_callbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    callback_type TEXT NOT NULL,
    trigger_text TEXT NOT NULL,
    user_reaction TEXT,
    context_summary TEXT,
    engagement_score REAL DEFAULT 0.5,
    times_called_back INTEGER DEFAULT 0,
    last_called_back TIMESTAMPTZ,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_callbacks_user ON conv_callbacks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_callbacks_score ON conv_callbacks(engagement_score DESC);

-- 2. Emotional arcs per session
CREATE TABLE IF NOT EXISTS conv_emotional_arcs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    arc_data JSONB NOT NULL,
    dominant_emotion TEXT,
    arc_shape TEXT,
    peak_moment TEXT,
    valley_moment TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_arcs_user ON conv_emotional_arcs(user_id);

-- 3. Per-law effectiveness scores
CREATE TABLE IF NOT EXISTS conv_law_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    law_id INTEGER NOT NULL,
    law_name TEXT NOT NULL,
    avg_score REAL DEFAULT 0.5,
    times_scored INTEGER DEFAULT 0,
    times_positive INTEGER DEFAULT 0,
    times_negative INTEGER DEFAULT 0,
    recommended_dial REAL,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, operator_name, law_id)
);
CREATE INDEX IF NOT EXISTS idx_law_scores_user ON conv_law_scores(user_id, operator_name);

-- 4. Relationship stage tracking
CREATE TABLE IF NOT EXISTS conv_relationship_stage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    stage TEXT DEFAULT 'new',
    session_count INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    stage_history JSONB DEFAULT '[]',
    roast_modifier INTEGER DEFAULT 0,
    formality_level TEXT DEFAULT 'warm but measured',
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, operator_name)
);

-- 5. Unresolved conversation threads
CREATE TABLE IF NOT EXISTS conv_unresolved_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    topic TEXT NOT NULL,
    user_position TEXT,
    operator_position TEXT,
    context_snippet TEXT,
    status TEXT DEFAULT 'open',
    revisit_count INTEGER DEFAULT 0,
    last_revisited TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_unresolved_user ON conv_unresolved_threads(user_id, status);

-- Upsert function for law scores (rolling average)
CREATE OR REPLACE FUNCTION upsert_law_score(
    p_user_id TEXT,
    p_operator_name TEXT,
    p_law_id INTEGER,
    p_law_name TEXT,
    p_new_score REAL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO conv_law_scores (user_id, operator_name, law_id, law_name, avg_score, times_scored, updated_at)
    VALUES (p_user_id, p_operator_name, p_law_id, p_law_name, p_new_score, 1, now())
    ON CONFLICT (user_id, operator_name, law_id) DO UPDATE SET
        avg_score = (conv_law_scores.avg_score * conv_law_scores.times_scored + p_new_score) 
                    / (conv_law_scores.times_scored + 1),
        times_scored = conv_law_scores.times_scored + 1,
        updated_at = now();
END;
$$ LANGUAGE plpgsql;
```

---

## PIPELINE.PY INTEGRATION

### Current Flow (handle_request)
```
1. Extract user message
2. Security scan
3. Mode detection
4. Loop selection
5. User ID resolution
6. Healing detection
7. Memory fetch (snapshot + prefetch)
8. Skill recall
9. Context build
10. Compression check
11. LLM call
12. Storage
13. Prefetch next turn
14. User modeling
```

### Upgraded Flow (minimal changes)
```python
async def handle_request(self, request):
    # Steps 1-5: UNCHANGED
    user_message = self._extract_user_message(request)
    # ... (same as current)
    
    # Step 6: EXTENDED — run all pre-hooks via HookManager
    if self.hook_manager:
        hook_ctx = await self.hook_manager.run_pre_hooks(
            user_message=user_message,
            session_id=conv_id,
            user_id=user_id,
            conversation_history=recent,
        )
        mode = hook_ctx.mode  # may have been overridden
        memory_context = hook_ctx.assembled_context
    else:
        # FALLBACK: existing flow (backward compatible)
        # ... (current code unchanged)
    
    # Steps 7-10: UNCHANGED (context build, compression)
    
    # Step 11: LLM call — UNCHANGED
    response = await self.llm_client.chat_completion(enriched_request)
    
    # Step 12: NEW — post-hook scoring
    if self.hook_manager:
        post_result = await self.hook_manager.run_post_hooks(
            response=assistant_content,
            ctx=hook_ctx,
        )
        if post_result.needs_regeneration and self._regen_count < 2:
            self._regen_count += 1
            # Inject feedback and re-call LLM
            # ... (regeneration logic)
    
    # Steps 13-14: UNCHANGED (storage, prefetch, user modeling)
```

**Key: The `if self.hook_manager` guard means the entire Conversation
Matrix is optional.** If HookManager isn't initialized, the pipeline
runs exactly as it does today. Zero risk.

---

## ROLLOUT PLAN

### Phase 1: Foundation (Week 1)
- [ ] Create `013_conversation_matrix.sql` migration
- [ ] Create `conversation_matrix/dna_compiler.py`
- [ ] Create `mind/emotion_detector.py`
- [ ] Update `champ.yaml` with conversation_dna section
- [ ] Update `persona_loader.py` to compile DNA rules
- [ ] Test: Champ boots with DNA rules in prompt

### Phase 2: Hooks + Scoring (Week 2)
- [ ] Create `conversation_matrix/hook_manager.py`
- [ ] Create `conversation_matrix/conversation_scorer.py`
- [ ] Create `mind/callback_manager.py`
- [ ] Update `pipeline.py` with hook_manager integration
- [ ] Test: Tier 1 scoring catches violations, regeneration works

### Phase 3: Memory Integration (Week 3)
- [ ] Create `mind/callback_extractor.py`
- [ ] Update `memory_snapshot.py` with new table queries
- [ ] Wire callback injection into pre-hooks
- [ ] Test: Callbacks stored, injected, and referenced across sessions

### Phase 4: Delivery (Week 4)
- [ ] Create `brain/message_splitter.py`
- [ ] Create `brain/typing_simulator.py`
- [ ] Create `brain/delivery_engine.py`
- [ ] Test: Text messages split into bubbles with typing indicators

### Phase 5: Voice Upgrades (Week 5+)
- [ ] Create `brain/prosody_tagger.py`
- [ ] Create `brain/backchannel_manager.py`
- [ ] Record backchannel audio clips
- [ ] Test: Voice responses have prosody tags, backchannels work

---

## TESTING STRATEGY

### Gate Test: Before/After Comparison
```python
# test_conversation_matrix.py

async def test_dna_compilation():
    """DNA compiles and attaches to persona."""
    compiler = DNACompiler()
    compiler.load_defaults()
    compiler.apply_overrides({"law_08_cultural_shorthand": 8})
    rules = compiler.compile()
    assert "cultural shorthand" in rules.lower()
    assert "you feel me" in rules.lower()

async def test_tier1_catches_violations():
    """Tier 1 scoring catches absolute violations."""
    scorer = ConversationScorer()
    result = scorer.quick_check("Great question! Here are 3 key points:\n1. First...")
    assert len(result) >= 2  # "great_question" + "numbered_list"

async def test_emotion_detection():
    """Emotion detector catches basic patterns."""
    detector = EmotionDetector()
    result = detector.detect("BRO THAT'S INSANE!!! Let's GOOO")
    assert result["primary"] == "excited"

async def test_callback_extraction():
    """Callback extractor finds laughter signals."""
    extractor = CallbackExtractor()
    result = extractor.scan("lol that doorman analogy was fire")
    assert len(result) >= 1
    assert result[0]["type"] in ("laughter", "strong_agreement")

async def test_backward_compatible():
    """Pipeline works without HookManager (no conversation_matrix)."""
    pipeline = BrainPipeline(settings)
    pipeline.hook_manager = None  # not initialized
    # Should run exactly as current codebase
    response = await pipeline.handle_request(test_request)
    assert response is not None
```

---

## VERSION

- v1.0 — 2026-04-13
- 13 new files, 6 modified files, 0 deleted files
- 5 new Supabase tables
- 5-phase rollout over ~5 weeks
- Fully backward compatible (hook_manager is optional)
