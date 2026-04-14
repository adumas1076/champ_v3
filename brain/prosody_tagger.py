# ============================================
# Conversation Matrix — Prosody Tagger
# Injects emotion/prosody tags into text before TTS.
# Tags are compatible with Fish S2 Pro, Chatterbox
# Turbo, and fall back gracefully on OpenAI TTS.
# ============================================

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ---- Tag Format ----
# Fish S2 Pro: [laugh], [whisper], [excited], [gentle] — free-form
# Chatterbox Turbo: [laugh], [sigh], [cough] — fixed tags
# OpenAI TTS: ignores tags (safe fallback)
# We use Fish S2 format — most flexible, degrades gracefully.


# ---- Emotion → Prosody Mapping ----

EMOTION_PROSODY = {
    "excited": {
        "opening_tag": "[energetic, upbeat] ",
        "emphasis_tag": "[excited] ",
        "pace": "faster",
    },
    "frustrated": {
        "opening_tag": "[gentle, empathetic] ",
        "emphasis_tag": "[softer] ",
        "pace": "slower",
    },
    "casual": {
        "opening_tag": "",  # no tag needed — natural default
        "emphasis_tag": "",
        "pace": "normal",
    },
    "serious": {
        "opening_tag": "[calm, steady] ",
        "emphasis_tag": "[thoughtful pause] ",
        "pace": "slower",
    },
    "curious": {
        "opening_tag": "[interested, engaged] ",
        "emphasis_tag": "[curious] ",
        "pace": "normal",
    },
    "confident": {
        "opening_tag": "[confident, assured] ",
        "emphasis_tag": "[strong] ",
        "pace": "normal",
    },
    "defeated": {
        "opening_tag": "[gentle, warm] ",
        "emphasis_tag": "[soft] ",
        "pace": "slower",
    },
    "grateful": {
        "opening_tag": "[warm, genuine] ",
        "emphasis_tag": "[sincere] ",
        "pace": "normal",
    },
    "neutral": {
        "opening_tag": "",
        "emphasis_tag": "",
        "pace": "normal",
    },
}

# ---- Content-Based Tags ----
# These inject based on what the AI is SAYING, not just user emotion

CONTENT_TAGS = [
    {
        "name": "laughter",
        "detect": re.compile(r"\b(lol|haha|lmao|that's funny)\b", re.I),
        "tag": " [light laugh] ",
        "position": "after",  # inject after the matched phrase
    },
    {
        "name": "thinking",
        "detect": re.compile(r"\b(actually|wait|hmm|let me think)\b", re.I),
        "tag": " [thoughtful pause] ",
        "position": "before",
    },
    {
        "name": "emphasis",
        "detect": re.compile(r"\b[A-Z]{4,}\b"),  # ALL CAPS words
        "tag": " [emphasis] ",
        "position": "before",
    },
    {
        "name": "trailing_off",
        "detect": re.compile(r"\.{3}"),  # ellipsis
        "tag": " [trailing off] ",
        "position": "replace",
    },
    {
        "name": "self_correction",
        "detect": re.compile(r"\b(actually no|wait no|I mean|well actually)\b", re.I),
        "tag": " [self-correcting] ",
        "position": "before",
    },
    {
        "name": "heavy_moment",
        "detect": re.compile(r"\b(damn|man|bro|tough|rough|real talk)\b", re.I),
        "tag": " [slower, weight] ",
        "position": "before",
    },
]


class ProsodyTagger:
    """
    Injects prosody tags into text before sending to TTS.

    Two tag sources:
    1. User emotion (from EmotionDetector) → opening tag + pace
    2. Response content → inline tags at specific phrases

    Tags degrade gracefully:
    - Fish S2 Pro: interprets all tags
    - Chatterbox Turbo: interprets fixed tags, ignores free-form
    - OpenAI TTS: ignores all tags (reads text normally)
    """

    def __init__(self, tts_provider: str = "openai"):
        self.tts_provider = tts_provider
        self._tag_enabled = tts_provider in ("fish_s2", "chatterbox", "cartesia")

    def tag(
        self,
        text: str,
        user_emotion: str = "neutral",
        intensity: float = 0.5,
        enable_content_tags: bool = True,
    ) -> str:
        """
        Inject prosody tags into text for TTS.

        Args:
            text: The response text to tag
            user_emotion: Detected user emotion (from EmotionDetector)
            intensity: Emotion intensity 0.0-1.0
            enable_content_tags: Whether to inject content-based tags

        Returns:
            Tagged text ready for TTS
        """
        # If TTS doesn't support tags, return as-is
        if not self._tag_enabled:
            return text

        tagged = text

        # 1. Opening emotion tag (only if intensity > 0.4)
        if intensity > 0.4:
            prosody = EMOTION_PROSODY.get(user_emotion, EMOTION_PROSODY["neutral"])
            opening = prosody.get("opening_tag", "")
            if opening:
                tagged = opening + tagged

        # 2. Content-based inline tags
        if enable_content_tags:
            tagged = self._inject_content_tags(tagged)

        tag_count = tagged.count("[")
        if tag_count > 0:
            logger.debug(
                f"[PROSODY] Injected {tag_count} tags | "
                f"emotion={user_emotion} ({intensity:.2f}) | "
                f"provider={self.tts_provider}"
            )

        return tagged

    def _inject_content_tags(self, text: str) -> str:
        """Inject content-based prosody tags at detected phrases."""
        for rule in CONTENT_TAGS:
            matches = list(rule["detect"].finditer(text))
            if not matches:
                continue

            # Only tag the first occurrence (don't over-tag)
            match = matches[0]
            tag = rule["tag"]
            pos = rule["position"]

            if pos == "before":
                text = text[:match.start()] + tag + text[match.start():]
            elif pos == "after":
                text = text[:match.end()] + tag + text[match.end():]
            elif pos == "replace":
                text = text[:match.start()] + tag + text[match.end():]

        return text

    def strip_tags(self, text: str) -> str:
        """Remove all prosody tags from text (for display/logging)."""
        return re.sub(r'\[.*?\]\s*', '', text)

    def set_provider(self, provider: str) -> None:
        """Update TTS provider (changes whether tags are injected)."""
        self.tts_provider = provider
        self._tag_enabled = provider in ("fish_s2", "chatterbox", "cartesia")
        logger.info(f"[PROSODY] Provider set to {provider}, tags={'enabled' if self._tag_enabled else 'disabled'}")
