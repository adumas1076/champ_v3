# ============================================
# Conversation Matrix — Message Splitter
# Splits AI responses into natural chat bubbles.
# Part of Node 6 (Delivery Engine) — text path.
# ============================================

import logging
import re

logger = logging.getLogger(__name__)


class MessageSplitter:
    """
    Splits a response into natural chat-sized bubbles.

    Rules:
    1. Never split mid-sentence
    2. Questions get their own bubble
    3. Max ~120 chars per bubble (soft limit)
    4. 2-4 bubbles per response (target)
    5. Single-sentence responses don't split
    6. Spec mode = never split
    """

    # Natural split points (regex boundaries)
    SPLIT_PATTERNS = [
        re.compile(r'(?<=[.!?])\s+(?=[A-Z])'),          # sentence boundary
        re.compile(r'(?<=[.!?])\s+(?=But |However |Actually |Though )'),  # contrast
        re.compile(r'(?<=[?])\s+'),                       # after question
        re.compile(r'\|\|\|'),                             # explicit delimiter
        re.compile(r'(?<=[.!?])\s+(?=And |So |Like )'),   # casual continuation
    ]

    def split(
        self,
        text: str,
        max_bubbles: int = 4,
        mode: str = "vibe",
    ) -> list[str]:
        """
        Split text into chat bubbles.

        Args:
            text: The response text to split
            max_bubbles: Maximum number of bubbles (default 4)
            mode: Output mode (spec = never split)

        Returns:
            List of text bubbles (1 = no split, 2-4 = split)
        """
        # Spec mode — never split
        if mode == "spec":
            return [text]

        # Short messages don't split
        if len(text) < 80:
            return [text]

        # Try explicit delimiters first
        if "|||" in text:
            bubbles = [b.strip() for b in text.split("|||") if b.strip()]
            return self._enforce_limits(bubbles, max_bubbles)

        # Split on natural boundaries
        bubbles = self._split_on_boundaries(text)

        # If no good splits found, return as single bubble
        if len(bubbles) <= 1:
            return [text]

        # Merge tiny bubbles (< 20 chars)
        bubbles = self._merge_tiny(bubbles, min_length=20)

        # Enforce max bubbles
        bubbles = self._enforce_limits(bubbles, max_bubbles)

        logger.debug(f"[SPLITTER] Split into {len(bubbles)} bubbles")
        return bubbles

    def _split_on_boundaries(self, text: str) -> list[str]:
        """Split text on natural sentence/phrase boundaries."""
        # Start with the full text as one chunk
        chunks = [text]

        for pattern in self.SPLIT_PATTERNS:
            new_chunks = []
            for chunk in chunks:
                parts = pattern.split(chunk)
                new_chunks.extend([p.strip() for p in parts if p.strip()])
            chunks = new_chunks

            # Stop if we have enough splits
            if len(chunks) >= 4:
                break

        return chunks

    def _merge_tiny(self, bubbles: list[str], min_length: int = 20) -> list[str]:
        """Merge tiny bubbles with their neighbors."""
        if len(bubbles) <= 1:
            return bubbles

        merged = [bubbles[0]]

        for i in range(1, len(bubbles)):
            if len(bubbles[i]) < min_length:
                # Merge with previous bubble
                merged[-1] = merged[-1] + " " + bubbles[i]
            else:
                merged.append(bubbles[i])

        return merged

    def _enforce_limits(self, bubbles: list[str], max_bubbles: int) -> list[str]:
        """Ensure we don't exceed max bubble count."""
        while len(bubbles) > max_bubbles:
            # Merge the two shortest adjacent bubbles
            shortest_idx = min(
                range(len(bubbles) - 1),
                key=lambda i: len(bubbles[i]) + len(bubbles[i + 1]),
            )
            bubbles[shortest_idx] = bubbles[shortest_idx] + " " + bubbles[shortest_idx + 1]
            bubbles.pop(shortest_idx + 1)

        return bubbles
