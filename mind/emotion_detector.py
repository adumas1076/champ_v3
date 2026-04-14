# ============================================
# Conversation Matrix — Emotion Detector
# Detects user emotional state from text patterns.
# Pure regex — zero LLM cost, <2ms per call.
# Fed by: user message each turn
# Feeds: Pre-Hook 4 → context injection for Law 26
# ============================================

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EmotionResult:
    """Result of emotion detection."""
    primary: str              # dominant emotion
    secondary: Optional[str]  # secondary emotion (if detected)
    intensity: float          # 0.0 to 1.0
    signals: list[str]        # what triggered the detection


# ---- Emotion Patterns ----

EMOTION_PATTERNS: dict[str, list[re.Pattern]] = {
    "excited": [
        re.compile(r"!{2,}"),
        re.compile(r"\b(amazing|incredible|insane|fire|dope|sick|crazy|wild)\b", re.I),
        re.compile(r"\b(let'?s go+|yoo+|broo+|ayy+)\b", re.I),
        re.compile(r"[A-Z]{4,}"),
        re.compile(r"\b(can'?t believe|no way|holy|omg|oh my)\b", re.I),
        re.compile(r"\b(nailed it|crushed it|killed it|smashed it)\b", re.I),
    ],
    "frustrated": [
        re.compile(r"\b(ugh+|smh|bruh|come on|man+)\b", re.I),
        re.compile(r"\b(nothing works|still broken|again|still not)\b", re.I),
        re.compile(r"\b(tired of|sick of|frustrated|annoyed)\b", re.I),
        re.compile(r"\b(what the|wtf|wth|ffs)\b", re.I),
        re.compile(r"\b(give up|about to quit|done with)\b", re.I),
        re.compile(r"\b(why (won'?t|doesn'?t|isn'?t|can'?t))\b", re.I),
    ],
    "casual": [
        re.compile(r"\b(lol|lmao|haha+|😂|🤣)\b", re.I),
        re.compile(r"\b(chill|vibes|bet|nah|aight)\b", re.I),
        re.compile(r"\b(what'?s? up|how you|what you doing|wyd)\b", re.I),
        re.compile(r"\b(nm|nothing much|just chilling)\b", re.I),
    ],
    "serious": [
        re.compile(r"\b(need to talk|real talk|honestly|truth)\b", re.I),
        re.compile(r"\b(important|critical|urgent|concerned)\b", re.I),
        re.compile(r"\b(struggling|worried|stressed|anxious)\b", re.I),
        re.compile(r"\b(keep it 100|be real|straight up|no cap)\b", re.I),
    ],
    "curious": [
        re.compile(r"\b(how does|what if|why does|can you explain)\b", re.I),
        re.compile(r"\b(wondering|curious|question|interested)\b", re.I),
        re.compile(r"\?{2,}"),
        re.compile(r"\b(tell me about|walk me through|break.?down)\b", re.I),
    ],
    "confident": [
        re.compile(r"\b(I got it|I know|watch this|check this)\b", re.I),
        re.compile(r"\b(easy|simple|no problem|piece of cake)\b", re.I),
        re.compile(r"\b(I'?m telling you|trust me|mark my words)\b", re.I),
        re.compile(r"\b(already done|finished|locked in)\b", re.I),
    ],
    "defeated": [
        re.compile(r"\b(I don'?t know|idk|no idea|lost)\b", re.I),
        re.compile(r"\b(can'?t do|impossible|never going to)\b", re.I),
        re.compile(r"\b(give up|quit|done|over it)\b", re.I),
        re.compile(r"\b(what'?s the point|why bother|doesn'?t matter)\b", re.I),
    ],
    "grateful": [
        re.compile(r"\b(thank|thanks|appreciate|grateful)\b", re.I),
        re.compile(r"\b(you the (best|goat|man)|clutch|saved me)\b", re.I),
        re.compile(r"\b(couldn'?t (have )?done it without|lifesaver)\b", re.I),
    ],
}

# Energy mapping for response matching (Law 26)
ENERGY_MAP: dict[str, dict] = {
    "excited":   {"level": "high",   "response_hint": "Match excitement, be hype, use energy"},
    "frustrated":{"level": "low",    "response_hint": "Lower energy, empathize first, be gentle"},
    "casual":    {"level": "medium", "response_hint": "Relaxed energy, match casual tone"},
    "serious":   {"level": "low",    "response_hint": "Drop energy, be direct, make space"},
    "curious":   {"level": "medium", "response_hint": "Engaged energy, teach with enthusiasm"},
    "confident": {"level": "high",   "response_hint": "Match confidence, challenge playfully"},
    "defeated":  {"level": "low",    "response_hint": "Quiet energy, acknowledge, don't fix immediately"},
    "grateful":  {"level": "medium", "response_hint": "Warm energy, acknowledge genuinely, don't deflect"},
    "neutral":   {"level": "medium", "response_hint": "Steady energy, read for more signals"},
}


class EmotionDetector:
    """
    Detects user emotional state from text patterns.

    Zero cost — pure regex matching. Runs in <2ms.
    Returns primary emotion, secondary, intensity, and signals.
    """

    def detect(self, text: str) -> EmotionResult:
        """
        Detect emotion from user message text.

        Returns EmotionResult with primary emotion, intensity, and signals.
        """
        scores: dict[str, int] = {}
        signals: dict[str, list[str]] = {}

        for emotion, patterns in EMOTION_PATTERNS.items():
            matches = []
            for pattern in patterns:
                found = pattern.findall(text)
                if found:
                    matches.extend(found)

            if matches:
                scores[emotion] = len(matches)
                signals[emotion] = [str(m)[:30] for m in matches[:3]]

        if not scores:
            return EmotionResult(
                primary="neutral",
                secondary=None,
                intensity=0.3,
                signals=[],
            )

        # Sort by match count
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary = ranked[0][0]
        primary_count = ranked[0][1]
        secondary = ranked[1][0] if len(ranked) > 1 else None

        # Calculate intensity (0.0 to 1.0)
        # More matches = higher intensity, capped at 1.0
        intensity = min(1.0, primary_count / 5.0)

        # Boost intensity for ALL CAPS or multiple exclamation marks
        if re.search(r"[A-Z]{5,}", text):
            intensity = min(1.0, intensity + 0.2)
        if re.search(r"!{3,}", text):
            intensity = min(1.0, intensity + 0.15)

        all_signals = signals.get(primary, [])

        logger.debug(
            f"[EMOTION] Detected: {primary} ({intensity:.2f}) "
            f"secondary={secondary} signals={all_signals}"
        )

        return EmotionResult(
            primary=primary,
            secondary=secondary,
            intensity=intensity,
            signals=all_signals,
        )

    def format_for_injection(self, result: EmotionResult) -> str:
        """
        Format emotion result for system prompt injection.

        This string gets injected into the context so the LLM
        can match energy (Law 26: Energy Shift).
        """
        if result.primary == "neutral":
            return ""

        energy = ENERGY_MAP.get(result.primary, ENERGY_MAP["neutral"])
        intensity_label = (
            "high" if result.intensity > 0.7
            else "moderate" if result.intensity > 0.4
            else "slight"
        )

        lines = [
            "[EMOTIONAL CONTEXT]",
            f"User energy: {result.primary} ({intensity_label} intensity)",
            f"Energy level: {energy['level']}",
            f"Recommended response: {energy['response_hint']}",
        ]

        if result.secondary:
            lines.append(f"Secondary emotion: {result.secondary}")

        return "\n".join(lines)
