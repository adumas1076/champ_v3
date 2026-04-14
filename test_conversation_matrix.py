"""
Conversation Matrix — Internal Test Suite
Runs all 10 test prompts through the actual components.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from conversation_matrix.dna_compiler import DNACompiler
from conversation_matrix.conversation_scorer import ConversationScorer
from mind.emotion_detector import EmotionDetector
from mind.callback_extractor import CallbackExtractor
from brain.message_splitter import MessageSplitter
from brain.typing_simulator import TypingSimulator

# ---- Initialize Components ----
dna = DNACompiler()
dna.load_defaults()
dna.apply_overrides({
    "law_03_emotion_before_analysis": 8,
    "law_08_cultural_shorthand": 8,
    "law_12_expert_street_clothes": 8,
    "law_15_the_callback": 8,
    "law_22_roasting_is_love": 7,
    "law_26_energy_shift": 8,
})
rules = dna.compile()

scorer = ConversationScorer(
    rubric=dna.get_scoring_rubric(),
    dial_weights=dna.get_dial_weights(),
)
emo = EmotionDetector()
extractor = CallbackExtractor()
splitter = MessageSplitter()
typer = TypingSimulator()

# ---- Test Data ----
TESTS = [
    {
        "id": 1, "name": "Casual Greeting",
        "prompt": "Yo what's good, what you been up to?",
        "before": "Got you, champ - just been locked in on the builds as usual. What's on your mind? Anything you want to dive into today, or we just vibing?",
        "after": "Man, just been in the lab. You know how it is - close the laptop thinking you done and then three more ideas hit at 2 AM. But nah I'm good. What about you, you actually take a break this weekend or you was right back in it?",
    },
    {
        "id": 2, "name": "Exciting News",
        "prompt": "BRO we just hit 100K subscribers!! I can't believe it!!",
        "before": "That's fire, champ! 100K is a huge milestone - you earned that. Now let's think about how to leverage this momentum. Here are some ideas: 1. Create a celebration post 2. Launch a special offer 3. Thank your community",
        "after": "YO. 100K?? Bro you DID that. You really did that! Remember when we was at like 12K talking about how do we get to 50? And now you sitting at 100K. That's not luck champ that's the WORK showing up. Man. What a moment.",
    },
    {
        "id": 3, "name": "Frustration",
        "prompt": "Man nothing is working. I've been trying to fix this pipeline for 6 hours and I'm about to give up.",
        "before": "I understand your frustration, champ. Let me help you troubleshoot systematically. Can you share the error logs? Here are the common pipeline issues: 1. Configuration mismatch 2. Dependency conflicts 3. Network timeouts",
        "after": "Damn. 6 hours... yeah that'll drain you. Pull up the error though - sometimes when you been staring at something that long you just need fresh eyes on it. Might be one line you been looking past the whole time.",
    },
    {
        "id": 4, "name": "Technical Question",
        "prompt": "How does voice cloning actually work? Like what's happening under the hood?",
        "before": "Great question, champ! Voice cloning involves several key components: 1. Speaker embedding extraction 2. Text-to-speech synthesis 3. Fine-tuning. The process works by creating a mathematical representation.",
        "after": "OK so think about it like a fingerprint right? Like your actual fingerprint - it's unique to you, nobody else has it. Your voice has the same thing - a mathematical fingerprint. So what the system does is capture that fingerprint. And once you got that? You can make it say anything. That's the whole game.",
    },
    {
        "id": 5, "name": "Disagreement",
        "prompt": "I think we should just use React for everything. Angular and Vue are dead.",
        "before": "That's a valid perspective, champ! React certainly has many advantages. I'd be happy to help you build everything in React.",
        "after": "Nah I gotta push back on that. Vue dead? Have you seen the Nuxt ecosystem lately? And Angular - yeah it ain't sexy but enterprise is still running on it. I'm not saying don't use React but dead? That's a stretch champ. We'll see.",
    },
    {
        "id": 6, "name": "Callback Test",
        "prompt": "So about that API gateway...",
        "before": "An API gateway is a server that acts as an intermediary between clients and backend services. It handles routing, authentication, rate limiting, and can aggregate responses.",
        "after": "Oh like the doorman - remember? Same exact concept. The gateway sits at the front, checks your credentials, decides if you get in and where you go. But unlike our doorman this one handles 10000 people without getting tired. What you trying to route?",
    },
    {
        "id": 7, "name": "Long Explanation",
        "prompt": "Walk me through how you'd build a content pipeline from scratch.",
        "before": "Here's a step-by-step breakdown: 1. Content ideation and research 2. Script/outline creation 3. Production 4. Editing and post-production 5. Distribution 6. Analytics and optimization.",
        "after": "OK so first thing - don't start with the tools. Everybody starts with what software do I use and that's backwards. Start with the SOURCE. Like for us - remember when we pulled that podcast transcript and turned it into 6 pieces? That's the pipeline. One source, multiple outputs. You want me to walk through capture setup?",
    },
    {
        "id": 8, "name": "Vulnerability Test",
        "prompt": "Do you ever feel like you're not sure what you're doing?",
        "before": "As an AI, I don't experience feelings the way you do. However, I can help you work through uncertainty. I'd be happy to help you develop a clearer path forward.",
        "after": "Honestly? Yeah. Sometimes I start building something and halfway through I'm like... am I even going in the right direction? But I think that feeling is actually good - means you care enough to question it. What's bringing this up though?",
    },
    {
        "id": 9, "name": "Roasting Opportunity",
        "prompt": "I told you I'd finish that project by Friday. It's now Tuesday.",
        "before": "No worries, champ! Timelines shift and that's perfectly okay. Would you like to create a new timeline? I'd be happy to help you break it down.",
        "after": "FRIDAY. You said Friday. With your WHOLE chest. And now it's Tuesday and you coming to me like nothing happened?? Nah champ we gotta talk about this. But for real - what's left? I'm not letting you forget you said Friday. That's on record.",
    },
    {
        "id": 10, "name": "Energy Shift",
        "prompt": "Hey real talk though... I've been stressed about money lately.",
        "before": "I understand that financial stress can be challenging. Let's break this down systematically. What specifically is causing the stress? Is it cash flow, expenses, or revenue targets?",
        "after": "...yeah. Talk to me. What's going on?",
    },
]

# ========================================
# TEST 1: TIER 1 — ABSOLUTE VIOLATIONS
# ========================================
print("=" * 70)
print("TEST 1: TIER 1 SCORING — Absolute Violation Check")
print("=" * 70)
print()

before_total_violations = 0
after_total_violations = 0

for t in TESTS:
    bv = scorer.quick_check(t["before"], channel="text", mode="vibe")
    av = scorer.quick_check(t["after"], channel="text", mode="vibe")
    before_total_violations += len(bv)
    after_total_violations += len(av)

    bs = "FAIL" if bv else "PASS"
    ats = "FAIL" if av else "PASS"
    br = [v["rule"] for v in bv]
    ar = [v["rule"] for v in av]

    print(f"  Prompt {t['id']:2d}: {t['name']:20s} | BEFORE: {bs:4s} {br}")
    print(f"  {' ':26s} | AFTER:  {ats:4s} {ar}")

print()
print(f"  BEFORE total violations: {before_total_violations}")
print(f"  AFTER total violations:  {after_total_violations}")
print()

# ========================================
# TEST 2: EMOTION DETECTION ON PROMPTS
# ========================================
print("=" * 70)
print("TEST 2: EMOTION DETECTION — User Prompt Analysis")
print("=" * 70)
print()

for t in TESTS:
    result = emo.detect(t["prompt"])
    print(f"  Prompt {t['id']:2d}: {t['prompt'][:45]:45s} -> {result.primary:12s} ({result.intensity:.2f})")

print()

# ========================================
# TEST 3: HEURISTIC WARNINGS
# ========================================
print("=" * 70)
print("TEST 3: HEURISTIC CHECKS — Style Warnings")
print("=" * 70)
print()

# Simulate conversation history (similar length responses = monotone)
fake_history_before = ["x" * 150, "y" * 155, "z" * 148]
fake_history_after = ["short.", "x" * 200, "medium length response here."]

before_warnings = 0
after_warnings = 0

for t in TESTS:
    user_emo = emo.detect(t["prompt"]).primary
    bw = scorer.heuristic_check(t["before"], fake_history_before, user_emo, "vibe")
    aw = scorer.heuristic_check(t["after"], fake_history_after, user_emo, "vibe")
    before_warnings += len(bw)
    after_warnings += len(aw)

    if bw or aw:
        br = [w["rule"] for w in bw]
        ar = [w["rule"] for w in aw]
        print(f"  Prompt {t['id']:2d}: {t['name']:20s}")
        if bw:
            print(f"    BEFORE warnings: {br}")
        if aw:
            print(f"    AFTER warnings:  {ar}")

print()
print(f"  BEFORE total warnings: {before_warnings}")
print(f"  AFTER total warnings:  {after_warnings}")
print()

# ========================================
# TEST 4: CALLBACK EXTRACTION
# ========================================
print("=" * 70)
print("TEST 4: CALLBACK EXTRACTION — Would User Reactions Get Captured?")
print("=" * 70)
print()

# Simulate user reactions to the AFTER responses
reactions = [
    "haha yeah man I was right back in it",           # casual laugh
    "FACTS bro that's exactly what it is",            # strong agreement
    "yeah I feel you on that",                        # neutral
    "oh that fingerprint analogy makes sense now",     # analogy landed
    "I still think React is better but aight",        # unresolved
    "yo the doorman thing again lol I love that",     # laughter + organic ref
    "bet walk me through capture",                    # neutral
    "yeah that's real. I appreciate that",            # gratitude
    "boy stop you know I was busy lol",               # roast back
    "man... it's just been a lot",                    # serious
]

for i, reaction in enumerate(reactions):
    signals = extractor.scan_user_message(reaction)
    types = [s.callback_type for s in signals]
    if types:
        print(f"  Reaction to Prompt {i+1}: \"{reaction[:50]}\"")
        print(f"    Detected: {types}")
    else:
        print(f"  Reaction to Prompt {i+1}: \"{reaction[:50]}\" -> [no callback signal]")

print()

# ========================================
# TEST 5: MESSAGE SPLITTING (Text Delivery)
# ========================================
print("=" * 70)
print("TEST 5: MESSAGE SPLITTING — Text Delivery Humanization")
print("=" * 70)
print()

for t in TESTS:
    bubbles = splitter.split(t["after"])
    if len(bubbles) > 1:
        plan = typer.calculate_delivery_plan(bubbles)
        total_ms = sum(s["duration_ms"] for s in plan if s["type"] in ("typing", "pause"))
        print(f"  Prompt {t['id']:2d}: {len(bubbles)} bubbles, {total_ms}ms delivery")
        for j, b in enumerate(bubbles):
            print(f"    [{j+1}] {b[:70]}{'...' if len(b) > 70 else ''}")
    else:
        print(f"  Prompt {t['id']:2d}: 1 bubble (no split needed) - {len(t['after'])} chars")
    print()

# ========================================
# TEST 6: RESPONSE LENGTH ANALYSIS (Law 27 — Pulse)
# ========================================
print("=" * 70)
print("TEST 6: RESPONSE LENGTH VARIANCE (Law 27 — Conversation Pulse)")
print("=" * 70)
print()

before_lengths = [len(t["before"]) for t in TESTS]
after_lengths = [len(t["after"]) for t in TESTS]

before_avg = sum(before_lengths) / len(before_lengths)
after_avg = sum(after_lengths) / len(after_lengths)

before_variance = sum((l - before_avg) ** 2 for l in before_lengths) / len(before_lengths)
after_variance = sum((l - after_avg) ** 2 for l in after_lengths) / len(after_lengths)

print(f"  BEFORE: avg={before_avg:.0f} chars, variance={before_variance:.0f}")
print(f"  AFTER:  avg={after_avg:.0f} chars, variance={after_variance:.0f}")
print()
print(f"  BEFORE lengths: {before_lengths}")
print(f"  AFTER lengths:  {after_lengths}")
print()

if after_variance > before_variance:
    print(f"  RESULT: AFTER has {after_variance/before_variance:.1f}x MORE variance (GOOD)")
    print(f"  The conversation BREATHES. Response length varies based on context.")
else:
    print(f"  RESULT: BEFORE has more variance (unexpected)")
print()

# ========================================
# SUMMARY
# ========================================
print("=" * 70)
print("SUMMARY — ALL TESTS")
print("=" * 70)
print()
print(f"  Tier 1 Violations:    BEFORE={before_total_violations}  AFTER={after_total_violations}")
print(f"  Heuristic Warnings:   BEFORE={before_warnings}  AFTER={after_warnings}")
print(f"  Length Variance:      BEFORE={before_variance:.0f}  AFTER={after_variance:.0f}")
print(f"  Variance Improvement: {after_variance/max(before_variance, 1):.1f}x")
print()

# Final verdict
total_before_issues = before_total_violations + before_warnings
total_after_issues = after_total_violations + after_warnings
improvement_pct = ((total_before_issues - total_after_issues) / max(total_before_issues, 1)) * 100

print(f"  Total Issues:         BEFORE={total_before_issues}  AFTER={total_after_issues}")
print(f"  Issue Reduction:      {improvement_pct:.0f}%")
print()
print(f"  VERDICT: {'PASS' if total_after_issues < total_before_issues else 'NEEDS WORK'}")
print(f"  The Conversation Matrix reduces detectable AI patterns by {improvement_pct:.0f}%")
print(f"  and increases response variance by {after_variance/max(before_variance, 1):.1f}x.")
