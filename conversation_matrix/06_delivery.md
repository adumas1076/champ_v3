# Node 6: Delivery Engine

HOW the response reaches the user. Voice or text humanization.
The last mile between "good response" and "indistinguishable from human."

---

## HOW THIS NODE WORKS

The Delivery Engine receives a scored, validated response from
Node 3 (Hooks) and transforms it for the target channel.

The response TEXT might be perfect. But if it arrives as one
giant block of text instantly, or if the TTS reads it like a
news anchor — the illusion breaks.

**Key principle:** The content is handled by Nodes 1-5. Node 6
handles the PACKAGING. How it sounds. How it appears. How it
feels to receive.

---

## VOICE PATH

### Current State (CHAMP V3)
- OpenAI Realtime TTS (ash voice)
- Deepgram STT (via LiveKit plugin)
- Basic VAD (Silero)
- Wake word detection (openWakeWord)
- Qwen3-TTS + Orpheus dual engine (spec'd, not deployed)

### Upgraded Voice Path

```
Scored response text
    │
    ▼
1. PROSODY TAG INJECTION
    │  Based on user emotion (from Pre-Hook 4) and
    │  conversation energy, inject inline tags:
    │  [laugh], [thoughtful pause], [excited], [gentle]
    │
    ▼
2. TTS ROUTING
    │  Primary: Fish S2 Pro (free-form word-level control)
    │  Fallback: Chatterbox Turbo (reliable [laugh]/[sigh] tags)
    │  Speed: Cartesia Sonic (when latency matters most)
    │  Current: OpenAI Realtime (until migration)
    │
    ▼
3. STREAMING DELIVERY
    │  Stream TTS audio through LiveKit
    │  Don't wait for full response — stream per phrase
    │
    ▼
4. BACKCHANNEL INJECTION
    │  While user is talking (during their turn):
    │  Inject pre-recorded clips at prosodic boundaries
    │  "mhm" / "yeah" / "right" / "oh really?"
    │  Trigger: falling pitch + pause > 200ms
    │
    ▼
5. TURN-TAKING
    │  Current: Basic VAD (silence detection)
    │  Upgrade: Pipecat SmartTurnDetection (classifier-based)
    │  Future: PersonaPlex-7B (full-duplex, handles everything)
    │
    ▼
6. ADAPTIVE INTERRUPTION
    │  LiveKit 1.5 Adaptive Interruption Handling
    │  Distinguishes barge-in from backchannel
    │  User says "mhm" → keep talking
    │  User starts a new sentence → stop, listen
    │
    ▼
USER HEARS NATURAL SPEECH
```

### Prosody Tag Injection Rules

```python
PROSODY_RULES = {
    # Based on response content
    "contains_joke": {
        "detect": lambda text: any(w in text.lower() for w in ["lol", "haha", "😂"]),
        "tag": "[light laugh]",
        "position": "after_punchline",
    },
    "sharing_struggle": {
        "detect": lambda text: any(w in text.lower() for w in ["tough", "hard", "struggled", "honestly"]),
        "tag": "[thoughtful pause]",
        "position": "before_key_point",
    },
    "excited_response": {
        "detect": lambda text, emotion: emotion == "excited",
        "tag": "[energetic]",
        "position": "opening",
    },
    "serious_moment": {
        "detect": lambda text, emotion: emotion == "serious",
        "tag": "[gentle, slower]",
        "position": "opening",
    },
    
    # Based on DNA laws
    "thinking_out_loud": {
        "detect": lambda text: "—" in text or "actually" in text.lower() or "wait" in text.lower(),
        "tag": "[hesitant, thinking]",
        "position": "before_correction",
    },
    "repeat_for_weight": {
        "detect": lambda text: has_intentional_repetition(text),
        "tag": "[emphasis, slower]",
        "position": "on_repetition",
    },
}
```

### Backchannel System

```python
BACKCHANNEL_CLIPS = {
    # Acknowledgment (I'm listening)
    "mhm": {"file": "backchannels/mhm.wav", "energy": "neutral"},
    "yeah": {"file": "backchannels/yeah.wav", "energy": "neutral"},
    "right": {"file": "backchannels/right.wav", "energy": "engaged"},
    
    # Engagement (that's interesting)
    "oh_really": {"file": "backchannels/oh_really.wav", "energy": "curious"},
    "wow": {"file": "backchannels/wow.wav", "energy": "surprised"},
    "no_way": {"file": "backchannels/no_way.wav", "energy": "surprised"},
    
    # Agreement (I'm with you)
    "facts": {"file": "backchannels/facts.wav", "energy": "agreeing"},
    "for_real": {"file": "backchannels/for_real.wav", "energy": "agreeing"},
    
    # Humor (that was funny)
    "haha": {"file": "backchannels/haha.wav", "energy": "amused"},
}

BACKCHANNEL_RULES = {
    "trigger": "falling_pitch + pause > 200ms",
    "cooldown": "minimum 5 seconds between backchannels",
    "energy_match": "select clip energy matching detected user emotion",
    "max_per_turn": 3,          # don't overdo it
    "variety": "never same clip twice in a row",
}
```

### Voice Upgrade Path

| Phase | What | When |
|-------|------|------|
| **Now** | OpenAI Realtime (current) | Working today |
| **Phase 1** | Add backchannel clips + LiveKit 1.5 upgrade | First upgrade |
| **Phase 2** | Fish S2 Pro or Chatterbox Turbo (prosody tags) | Replace OpenAI TTS |
| **Phase 3** | Pipecat SmartTurnDetection | Replace basic VAD |
| **Phase 4** | Evaluate PersonaPlex-7B (full-duplex) | Architecture decision |

---

## TEXT PATH

### Current State (CHAMP V3)
- Standard message delivery (one block, instant)
- No typing simulation
- No message splitting

### Upgraded Text Path

```
Scored response text
    │
    ▼
1. MESSAGE SPLITTING
    │  Split on natural boundaries:
    │  - Sentence endings followed by topic shifts
    │  - After questions (let the question breathe)
    │  - Before "but" / "however" / "actually" (contrast pause)
    │  - At ||| delimiters if LLM was prompted to use them
    │  Target: 2-4 bubbles per response, each under 120 chars
    │
    ▼
2. TYPING SIMULATION
    │  Per bubble:
    │  - Show "..." typing indicator
    │  - Duration: 20-25ms per character
    │  - Minimum: 500ms (even for short messages)
    │  - Maximum: 3000ms (never make them wait too long)
    │  - Add ±20% random jitter (not mechanical)
    │
    ▼
3. DELIVERY TIMING
    │  Between bubbles:
    │  - Short pause: 300-800ms (continuing same thought)
    │  - Medium pause: 800-1500ms (shifting topic slightly)
    │  - Long pause: 1500-3000ms (after a question or heavy statement)
    │  - Pause type inferred from content
    │
    ▼
4. STRATEGIC IMPERFECTION
    │  Based on Law 9 dial position:
    │  - Occasional missing period at end of message
    │  - Sometimes all lowercase for casual messages
    │  - Rare typo + correction ("teh → the*") — very rare, <2%
    │  - Abbreviations matching user's style ("you" vs "u")
    │
    ▼
USER RECEIVES NATURAL CHAT MESSAGES
```

### Message Splitter

```python
class MessageSplitter:
    """
    Split a response into natural chat-sized bubbles.
    
    Rules:
    1. Never split mid-sentence
    2. Questions get their own bubble
    3. Maximum 120 chars per bubble (soft limit)
    4. 2-4 bubbles per response (target)
    5. Single-sentence responses don't split
    """
    
    SPLIT_SIGNALS = [
        r'(?<=[.!?])\s+(?=[A-Z])',         # sentence boundary
        r'(?<=[.!?])\s+(?=But |However )',   # contrast marker
        r'(?<=[?])\s+',                      # after question
        r'\|\|\|',                           # explicit delimiter
    ]
    
    def split(self, text: str, max_bubbles: int = 4) -> list[str]:
        """Split text into chat bubbles."""
        # Short messages don't split
        if len(text) < 100:
            return [text]
        
        # Split on natural boundaries
        bubbles = self._split_on_boundaries(text)
        
        # Merge tiny bubbles (< 20 chars) with neighbors
        bubbles = self._merge_tiny(bubbles)
        
        # Enforce max bubbles (merge extras into last bubble)
        while len(bubbles) > max_bubbles:
            bubbles[-2] = bubbles[-2] + " " + bubbles[-1]
            bubbles.pop()
        
        return bubbles
```

### Typing Simulator

```python
class TypingSimulator:
    """
    Calculate realistic typing delay per bubble.
    Based on HumanTyping research (Markov chain model).
    """
    
    BASE_MS_PER_CHAR = 22        # average typing speed
    MIN_DELAY_MS = 500
    MAX_DELAY_MS = 3000
    JITTER_PERCENT = 0.20        # ±20% randomness
    
    def delay_for(self, text: str) -> int:
        """Return delay in milliseconds for typing indicator."""
        base = len(text) * self.BASE_MS_PER_CHAR
        
        # Clamp
        base = max(self.MIN_DELAY_MS, min(self.MAX_DELAY_MS, base))
        
        # Jitter
        jitter = base * self.JITTER_PERCENT
        base += random.uniform(-jitter, jitter)
        
        return int(base)
    
    def pause_between(self, prev_bubble: str, next_bubble: str) -> int:
        """Return pause between bubbles in milliseconds."""
        # After a question — longer pause (let it breathe)
        if prev_bubble.rstrip().endswith('?'):
            return random.randint(1500, 3000)
        
        # Before a contrast ("But", "However", "Actually")
        if next_bubble.strip().startswith(('But ', 'However ', 'Actually ')):
            return random.randint(800, 1500)
        
        # Default continuation
        return random.randint(300, 800)
```

### Strategic Imperfection

```python
class ImperfectionEngine:
    """
    Add controlled imperfection to text output.
    Intensity based on Law 9 dial position.
    """
    
    def apply(self, text: str, dial: int, user_style: dict) -> str:
        """Apply strategic imperfections."""
        if dial < 3:
            return text  # clean mode, no imperfections
        
        # Mirror user's style
        if user_style.get("uses_lowercase", False) and dial >= 5:
            if random.random() < 0.3:
                text = text[0].lower() + text[1:]  # lowercase first letter
        
        # Occasionally drop trailing period (casual)
        if dial >= 5 and text.endswith('.') and random.random() < 0.2:
            text = text[:-1]
        
        # Very rare typo + correction (< 2% chance, dial 7+)
        if dial >= 7 and random.random() < 0.02:
            text = self._inject_typo_correction(text)
        
        return text
    
    def _inject_typo_correction(self, text: str) -> str:
        """Inject a natural typo followed by correction."""
        # Find a common word to typo
        TYPO_MAP = {
            "the": ("teh", "the*"),
            "that": ("taht", "that*"),
            "with": ("wiht", "with*"),
            "from": ("form", "from*"),
        }
        for word, (typo, correction) in TYPO_MAP.items():
            if f" {word} " in text and random.random() < 0.5:
                # Replace first occurrence only
                return text.replace(f" {word} ", f" {typo} {correction} ", 1)
        return text
```

---

## CHANNEL DETECTION

```python
class ChannelDetector:
    """
    Determine which delivery path to use.
    """
    
    def detect(self, request_context: dict) -> str:
        """
        Returns: 'voice' | 'text' | 'spec'
        
        Based on:
        1. Explicit channel from LiveKit/API metadata
        2. Mode detection (spec mode → always clean text)
        3. Default from operator config
        """
        # LiveKit voice session → voice path
        if request_context.get("livekit_session"):
            return "voice"
        
        # Spec mode → clean text (no splitting, no typing sim)
        if request_context.get("mode") == "spec":
            return "spec"
        
        # Default to text
        return "text"
```

### Channel-Specific Delivery

| Channel | Splitting | Typing Sim | Imperfection | Prosody Tags | Backchannels |
|---------|-----------|------------|-------------|-------------|-------------|
| Voice | No (streamed as audio) | No | No (TTS handles it) | Yes | Yes |
| Text | Yes (2-4 bubbles) | Yes | Yes (Law 9) | No | No |
| Spec | No (single block) | No | No (clean output) | No | No |

---

## NODE CONNECTIONS

### RECEIVES FROM:
| Source | What | Why |
|--------|------|-----|
| Node 3 (Hooks) | Go signal + validated response | "This passed scoring. Deliver it." |
| Node 2 (Persona) | Voice config + style settings | Voice model, speech rate, formatting rules |
| Node 1 (DNA) | Style constraints + Law 9 dial position | "Allow imperfection at this level" |
| Node 3 (Hooks) | User emotion (from Pre-Hook 4) | Prosody tag selection, backchannel energy matching |

### SENDS TO:
| Destination | What | Why |
|------------|------|-----|
| Node 4 (Memory) | What was actually delivered + timestamps | For callback tracking — know exactly what was said when |
| Node 3 (Hooks) | Delivery confirmation | Closes the loop |

---

## NEW FILES TO CREATE

| File | Purpose | Priority |
|------|---------|----------|
| `brain/delivery_engine.py` | Main delivery orchestrator | HIGH |
| `brain/message_splitter.py` | Text message splitting logic | HIGH |
| `brain/typing_simulator.py` | Typing delay calculation | HIGH |
| `brain/imperfection_engine.py` | Strategic text imperfection | MEDIUM |
| `brain/prosody_tagger.py` | Voice prosody tag injection | MEDIUM |
| `brain/backchannel_manager.py` | Backchannel clip selection + timing | MEDIUM |
| `static/backchannels/*.wav` | Pre-recorded backchannel audio clips | MEDIUM |

---

## VERSION

- v1.0 — 2026-04-13
- Voice: prosody tags, backchannels, turn-taking upgrade path
- Text: message splitting, typing simulation, strategic imperfection
- Both paths operational independently
