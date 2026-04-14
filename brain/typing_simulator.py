# ============================================
# Conversation Matrix — Typing Simulator
# Calculates realistic typing delays for text delivery.
# Part of Node 6 (Delivery Engine) — text path.
# ============================================

import logging
import random

logger = logging.getLogger(__name__)


class TypingSimulator:
    """
    Calculates realistic typing delay per chat bubble.

    Based on HumanTyping research:
    - Average typing speed: ~70 WPM = ~22ms per character
    - Minimum delay: 500ms (even for short messages)
    - Maximum delay: 3000ms (never make them wait too long)
    - Jitter: ±20% (not mechanical)
    """

    BASE_MS_PER_CHAR = 22
    MIN_DELAY_MS = 500
    MAX_DELAY_MS = 3000
    JITTER_PERCENT = 0.20

    def typing_delay(self, text: str) -> int:
        """
        Calculate typing indicator duration in milliseconds.

        Args:
            text: The bubble text that's being "typed"

        Returns:
            Delay in milliseconds for the typing indicator
        """
        base = len(text) * self.BASE_MS_PER_CHAR

        # Clamp to range
        base = max(self.MIN_DELAY_MS, min(self.MAX_DELAY_MS, base))

        # Add jitter (±20%)
        jitter = base * self.JITTER_PERCENT
        base += random.uniform(-jitter, jitter)

        return int(base)

    def pause_between(self, prev_bubble: str, next_bubble: str) -> int:
        """
        Calculate pause between bubbles in milliseconds.

        Different pause lengths based on content:
        - After a question: longer pause (let it breathe)
        - Before a contrast (But, However): medium pause
        - Default continuation: short pause
        """
        # After a question — let it breathe
        if prev_bubble.rstrip().endswith("?"):
            return random.randint(1500, 3000)

        # Before a contrast marker
        contrast_starters = ("But ", "However ", "Actually ", "Though ", "Nah ")
        if any(next_bubble.strip().startswith(s) for s in contrast_starters):
            return random.randint(800, 1500)

        # After something heavy/emotional
        heavy_endings = ("...", "man.", "bro.", "damn.", "tough.")
        if any(prev_bubble.rstrip().endswith(e) for e in heavy_endings):
            return random.randint(1000, 2000)

        # Default continuation
        return random.randint(300, 800)

    def calculate_delivery_plan(self, bubbles: list[str]) -> list[dict]:
        """
        Create a full delivery plan for a set of bubbles.

        Returns a list of delivery steps with timing:
        [
            {"type": "typing", "duration_ms": 1200, "bubble_index": 0},
            {"type": "send", "text": "First bubble text", "bubble_index": 0},
            {"type": "pause", "duration_ms": 600, "bubble_index": 0},
            {"type": "typing", "duration_ms": 800, "bubble_index": 1},
            {"type": "send", "text": "Second bubble text", "bubble_index": 1},
            ...
        ]
        """
        plan = []

        for i, bubble in enumerate(bubbles):
            # Typing indicator
            plan.append({
                "type": "typing",
                "duration_ms": self.typing_delay(bubble),
                "bubble_index": i,
            })

            # Send the message
            plan.append({
                "type": "send",
                "text": bubble,
                "bubble_index": i,
            })

            # Pause between bubbles (not after last one)
            if i < len(bubbles) - 1:
                plan.append({
                    "type": "pause",
                    "duration_ms": self.pause_between(bubble, bubbles[i + 1]),
                    "bubble_index": i,
                })

        total_ms = sum(
            step["duration_ms"]
            for step in plan
            if step["type"] in ("typing", "pause")
        )

        logger.debug(
            f"[TYPING] Delivery plan: {len(bubbles)} bubbles, "
            f"{len(plan)} steps, {total_ms}ms total"
        )

        return plan
