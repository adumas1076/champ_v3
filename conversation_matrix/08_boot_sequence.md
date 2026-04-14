# Operator Boot Sequence

How a new operator loads the Conversation Matrix Graph,
reads its dials, and starts a session. The universal startup
sequence every operator follows.

---

## THE BOOT SEQUENCE (7 Steps)

```
OPERATOR BOOT
    │
    ▼
Step 1: LOAD CONFIG
    │  Read operator YAML (e.g., champ.yaml)
    │  Extract: name, voice, persona_file, conversation_dna dials,
    │           tool_permissions, channels, boundaries, escalation
    │
    ▼
Step 2: LOAD PERSONA
    │  PersonaLoader reads persona file (7-section schema)
    │  Extract: identity, relational stance, voice patterns,
    │           mode triggers, capabilities, calibration examples
    │
    ▼
Step 3: COMPILE DNA
    │  Load 27 Laws defaults from 01_conversation_dna.md
    │  Apply operator's dial overrides from YAML config
    │  Apply channel modifiers (voice/text/spec adjustments)
    │  Generate compiled CONVERSATION RULES markdown
    │  Attach to persona as final section
    │
    ▼
Step 4: WIRE HOOKS
    │  Initialize HookManager with:
    │  - Existing components (HealingLoop, ModeDetector, etc.)
    │  - New components (EmotionDetector, CallbackManager, Scorer)
    │  - Anti-patterns from compiled DNA
    │  - Mode triggers from persona
    │  - never_say list from persona
    │
    ▼
Step 5: LOAD MEMORY
    │  SnapshotManager.capture():
    │  - Supabase profile + lessons + healing
    │  - Letta memory blocks (if available)
    │  - Mem0 context (if available)
    │  - conv_relationship_stage (NEW)
    │  - conv_law_scores (NEW)
    │  - conv_callbacks active (NEW)
    │  - conv_unresolved_threads (NEW)
    │  - conv_emotional_arcs last session (NEW)
    │  Freeze snapshot (immutable for session)
    │
    ▼
Step 6: INITIALIZE SCORING
    │  Load scoring rubric from compiled DNA
    │  Load absolute violations + heuristic checks
    │  Load dial weights for composite calculation
    │  Load historical baselines from conv_law_scores
    │
    ▼
Step 7: READY
    │  Operator is live.
    │  All 6 nodes connected.
    │  Waiting for first user message.
    │
    ▼
FIRST USER MESSAGE → Hook lifecycle begins
```

---

## STEP-BY-STEP CODE OUTLINE

### Step 1: Load Config

```python
async def boot_operator(operator_name: str) -> Operator:
    """Boot an operator from the Conversation Matrix Graph."""
    
    # 1. Load YAML config
    config_path = f"operators/configs/{operator_name}.yaml"
    config = load_yaml(config_path)
    
    # Validate required fields
    assert config.get("name"), "Operator config missing 'name'"
    assert config.get("persona_file"), "Operator config missing 'persona_file'"
```

### Step 2: Load Persona

```python
    # 2. Load persona file
    persona_loader = PersonaLoader(settings)
    persona_loader.set_persona_file(config["persona_file"])
    await persona_loader.load()
    
    persona_text = persona_loader.get_persona()
```

### Step 3: Compile DNA

```python
    # 3. Compile Conversation DNA
    dna_compiler = DNACompiler()
    
    # Load defaults
    dna_compiler.load_defaults()  # from 01_conversation_dna.md
    
    # Apply operator overrides
    overrides = config.get("conversation_dna", {})
    dna_compiler.apply_overrides(overrides)
    
    # Compile into markdown rules
    compiled_rules = dna_compiler.compile()
    
    # Attach to persona
    persona_text += f"\n\n---\n\n{compiled_rules}"
```

### Step 4: Wire Hooks

```python
    # 4. Initialize Hook Manager
    hook_config = HookConfig(
        anti_patterns=dna_compiler.get_anti_patterns(),
        mode_triggers=persona_loader.get_mode_triggers(),
        never_say=persona_loader.get_never_say(),
        channel=config.get("channels", {}),
    )
    
    hook_manager = HookManager(hook_config)
    hook_manager.healing = HealingLoop()
    hook_manager.mode_detector = ModeDetector()
    hook_manager.emotion_detector = EmotionDetector()
    hook_manager.callback_manager = CallbackManager(settings)
    hook_manager.conversation_scorer = ConversationScorer(
        rubric=dna_compiler.get_scoring_rubric(),
        dial_weights=dna_compiler.get_dial_weights(),
    )
```

### Step 5: Load Memory

```python
    # 5. Capture memory snapshot
    snapshot_manager = SnapshotManager()
    await snapshot_manager.capture(
        session_id=session_id,
        user_id=user_id,
        memory=supabase_memory,
        letta=letta_memory,
        mem0=mem0_memory,
        user_modeling=user_modeling,
        # NEW: conversation matrix tables
        callbacks=callback_manager,
        relationship=relationship_store,
        law_scores=law_score_store,
        unresolved=unresolved_store,
        emotional_arcs=arc_store,
    )
```

### Step 6: Initialize Scoring

```python
    # 6. Initialize scoring with baselines
    scorer = hook_manager.conversation_scorer
    scorer.load_baselines(
        user_id=user_id,
        operator_name=operator_name,
    )
```

### Step 7: Ready

```python
    # 7. Assemble operator
    operator = Operator(
        name=config["name"],
        persona=persona_text,
        hook_manager=hook_manager,
        snapshot_manager=snapshot_manager,
        dna_compiler=dna_compiler,
        config=config,
    )
    
    logger.info(
        f"[BOOT] Operator '{operator_name}' ready | "
        f"DNA: {len(overrides)} overrides | "
        f"Laws active: {len(dna_compiler.active_laws)} | "
        f"Snapshot: frozen | "
        f"Scoring: {len(scorer.absolute_violations)} violations tracked"
    )
    
    return operator
```

---

## NEW OPERATOR QUICKSTART

Time from zero to live operator: ~30 minutes.

### Step 1: Create YAML (5 min)
```yaml
name: billy
display_name: Billy
description: Billing specialist and sales closer.
owner: platform
voice:
  provider: openai
  voice: ballad
  temperature: 0.7
persona_file: persona/compiled/billy_prompt.md
conversation_dna:
  law_06_questions_as_setups: 9
  law_10_say_less_mean_more: 8
  law_12_expert_street_clothes: 9
  law_13_stack_stories: 9
tool_permissions:
  - browse_url
  - ask_brain
```

### Step 2: Write Persona (20 min)
Fill the 7-section schema from Section 2:
- A: Identity Core
- B: Relational Stance
- C: Voice & Speech (signature phrases, never_say)
- D: DNA Overrides (same as YAML — redundant intentionally)
- E: Mode Detection
- F: Capabilities
- G: Few-Shot Calibration (3-5 examples — most important part)

### Step 3: Boot (automatic)
```python
billy = await boot_operator("billy")
# Done. Billy is live with the full Conversation Matrix Graph.
```

---

## SESSION LIFECYCLE

```
BOOT (once per session)
    │
    ▼
TURN LOOP (repeats for every user message)
    │
    ├── Pre-Hooks fire (context assembly)
    ├── LLM generates response
    ├── Post-Hooks fire (scoring + extraction)
    ├── Delivery (voice or text)
    └── Loop back
    │
    ▼
SESSION END
    │
    ├── Write emotional arc to conv_emotional_arcs
    ├── Update relationship stage in conv_relationship_stage
    ├── Run LearningLoop (existing)
    ├── Run SkillEngine extraction (existing)
    ├── Stale callback cleanup
    ├── Release snapshot
    └── Close transcript logger
```

---

## VERSION

- v1.0 — 2026-04-13
- 7-step boot sequence
- ~30 min to create new operator
- Zero infrastructure per operator (all config)
