# ============================================
# Conversation Matrix — Callback Extractor
# Detects callback-worthy moments in conversation turns.
# Pure regex — zero cost, runs async after each turn.
# Feeds: CallbackManager.store()
# ============================================

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CallbackSignal:
    """A detected callback-worthy signal."""
    callback_type: str
    trigger: str            # what matched
    engagement_score: float # estimated engagement


# ---- Signal Patterns ----

CALLBACK_SIGNALS: dict[str, list[re.Pattern]] = {
    "laughter": [
        re.compile(r"\b(lol|lmao|lmfao|haha+|hehe+)\b", re.I),
        re.compile(r"(😂|🤣|💀)", re.I),
        re.compile(r"\b(dead|I'?m dying|I can'?t)\b", re.I),
        re.compile(r"\bthat'?s? (funny|hilarious|comedy)\b", re.I),
    ],
    "strong_agreement": [
        re.compile(r"\b(facts|exactly|100|bingo|nailed it)\b", re.I),
        re.compile(r"\bthat'?s? (fire|it|perfect|exactly)\b", re.I),
        re.compile(r"\b(yes+|yep+|absolutely|precisely)\b", re.I),
        re.compile(r"\b(on point|spot on|couldn'?t agree more)\b", re.I),
        re.compile(r"(🔥|💯|🎯)", re.I),
    ],
    "organic_reference": [
        re.compile(r"\blike you said\b", re.I),
        re.compile(r"\byou mentioned\b", re.I),
        re.compile(r"\bthat .{1,30} thing you said\b", re.I),
        re.compile(r"\bremember when (you|we)\b", re.I),
        re.compile(r"\bearlier you (said|mentioned|were talking)\b", re.I),
    ],
    "unresolved": [
        re.compile(r"\bagree to disagree\b", re.I),
        re.compile(r"\bI still think\b", re.I),
        re.compile(r"\bnot convinced\b", re.I),
        re.compile(r"\bwe'?ll see\b", re.I),
        re.compile(r"\bI don'?t (know|agree|buy) (that|it)\b", re.I),
        re.compile(r"\bmaybe you'?re right\b", re.I),
    ],
    "roast_moment": [
        re.compile(r"\byeah right\b", re.I),
        re.compile(r"\byou wish\b", re.I),
        re.compile(r"\bboy stop\b", re.I),
        re.compile(r"\bget out of here\b", re.I),
        re.compile(r"\b(oh really|sure bud|whatever you say)\b", re.I),
        re.compile(r"\byou'?re (crazy|tripping|bugging|wilding)\b", re.I),
    ],
    "analogy_landed": [
        re.compile(r"\bgood (analogy|comparison|example)\b", re.I),
        re.compile(r"\bthat makes (sense|it click)\b", re.I),
        re.compile(r"\bmakes sense\b", re.I),
        re.compile(r"\boh I (get it|see)\b", re.I),
        re.compile(r"\bnow I understand\b", re.I),
        re.compile(r"\boh ok.{0,10}(got it|I see|makes sense)\b", re.I),
        re.compile(r"\bclick(ed|s)?\b", re.I),
    ],
}

# Engagement score estimates per type
ENGAGEMENT_SCORES: dict[str, float] = {
    "laughter": 0.9,
    "strong_agreement": 0.8,
    "organic_reference": 0.95,    # user referencing us back = highest signal
    "unresolved": 0.7,
    "roast_moment": 0.85,
    "analogy_landed": 0.8,
}


class CallbackExtractor:
    """
    Scans conversation turns for callback-worthy moments.

    Runs async after each turn. Zero cost (regex).
    Detected signals get stored via CallbackManager.
    """

    def scan_user_message(self, user_message: str) -> list[CallbackSignal]:
        """
        Scan a user message for callback signals.

        The user's reaction to our previous response tells us
        whether what we said was callback-worthy.
        """
        signals = []

        for signal_type, patterns in CALLBACK_SIGNALS.items():
            for pattern in patterns:
                matches = pattern.findall(user_message)
                if matches:
                    signals.append(CallbackSignal(
                        callback_type=signal_type,
                        trigger=str(matches[0])[:50],
                        engagement_score=ENGAGEMENT_SCORES.get(signal_type, 0.5),
                    ))
                    break  # one match per type is enough

        if signals:
            logger.debug(
                f"[CALLBACK_EXTRACT] Found {len(signals)} signals: "
                f"{[s.callback_type for s in signals]}"
            )

        return signals

    def extract_callback_context(
        self,
        previous_ai_response: str,
        user_reaction: str,
        signals: list[CallbackSignal],
    ) -> list[dict]:
        """
        Build callback entries from detected signals.

        Combines what the AI said (trigger) with how the user
        reacted (signal) to create a storable callback.
        """
        callbacks = []

        for signal in signals:
            # Extract the most relevant part of the AI response
            trigger_text = self._extract_trigger(previous_ai_response, signal)

            callbacks.append({
                "callback_type": signal.callback_type,
                "trigger_text": trigger_text,
                "user_reaction": user_reaction[:200],
                "context_summary": f"User reacted with {signal.callback_type} to: {trigger_text[:60]}",
                "engagement_score": signal.engagement_score,
            })

        return callbacks

    def _extract_trigger(
        self,
        ai_response: str,
        signal: CallbackSignal,
    ) -> str:
        """
        Extract the part of the AI response that likely triggered the reaction.

        Simple heuristic: take the last 1-2 sentences of the response,
        as reactions usually respond to the most recent thing said.
        """
        sentences = [s.strip() for s in re.split(r'[.!?]+', ai_response) if s.strip()]

        if not sentences:
            return ai_response[:100]

        # For analogies, look for "like" or "think of it as"
        if signal.callback_type == "analogy_landed":
            for s in sentences:
                if any(word in s.lower() for word in ["like a", "think of", "imagine", "same as"]):
                    return s[:150]

        # Default: last meaningful sentence
        last = sentences[-1] if sentences else ai_response[:100]
        return last[:150]
