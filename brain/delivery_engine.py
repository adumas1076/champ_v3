# ============================================
# Conversation Matrix — Delivery Engine
# Node 6: The last mile. How responses reach the user.
# Routes to voice path or text path based on channel.
# ============================================

import logging
import random
import re
from dataclasses import dataclass, field
from typing import Optional

from brain.message_splitter import MessageSplitter
from brain.typing_simulator import TypingSimulator
from brain.prosody_tagger import ProsodyTagger
from brain.backchannel_manager import BackchannelManager

logger = logging.getLogger(__name__)


@dataclass
class DeliveryPlan:
    """Complete delivery plan for a response."""
    channel: str                     # voice | text | spec
    original_text: str               # before any processing
    processed_text: str              # after processing (tags or imperfection)
    bubbles: list[str] = field(default_factory=list)
    delivery_steps: list[dict] = field(default_factory=list)
    total_delivery_ms: int = 0
    prosody_tags_added: int = 0
    imperfections_added: int = 0


class DeliveryEngine:
    """
    The last mile of the Conversation Matrix.

    Takes a scored, validated response and prepares it for delivery
    to the user through the appropriate channel.

    Voice path: prosody tags → TTS → stream via LiveKit
    Text path: split into bubbles → typing simulation → deliver sequentially
    Spec path: deliver as-is (clean, no processing)

    Integrates:
    - MessageSplitter (text bubble creation)
    - TypingSimulator (realistic delivery timing)
    - ProsodyTagger (voice emotion tags)
    - BackchannelManager (listening signals during user speech)
    - ImperfectionEngine (strategic text imperfection)
    """

    def __init__(
        self,
        tts_provider: str = "openai",
        imperfection_dial: int = 5,
    ):
        self.splitter = MessageSplitter()
        self.typer = TypingSimulator()
        self.prosody = ProsodyTagger(tts_provider=tts_provider)
        self.backchannels = BackchannelManager()

        self._imperfection_dial = imperfection_dial
        self._user_style = {}  # learned from user messages over time

    def prepare(
        self,
        text: str,
        channel: str = "text",
        mode: str = "vibe",
        user_emotion: str = "neutral",
        emotion_intensity: float = 0.5,
    ) -> DeliveryPlan:
        """
        Prepare a response for delivery.

        Doesn't actually send anything — returns a DeliveryPlan
        that the caller executes. This separation allows the
        pipeline to inspect the plan before committing.

        Args:
            text: The validated response text
            channel: "voice" | "text" | "spec"
            mode: "vibe" | "build" | "spec"
            user_emotion: Detected emotion from EmotionDetector
            emotion_intensity: 0.0-1.0

        Returns:
            DeliveryPlan with all steps and timing
        """
        plan = DeliveryPlan(
            channel=channel,
            original_text=text,
            processed_text=text,
        )

        if channel == "spec" or mode == "spec":
            # Spec mode: deliver as-is, no processing
            plan.processed_text = text
            plan.bubbles = [text]
            plan.delivery_steps = [{"type": "send", "text": text, "bubble_index": 0}]
            return plan

        if channel == "voice":
            plan = self._prepare_voice(plan, user_emotion, emotion_intensity)
        else:
            plan = self._prepare_text(plan, mode, user_emotion)

        return plan

    def _prepare_voice(
        self,
        plan: DeliveryPlan,
        user_emotion: str,
        emotion_intensity: float,
    ) -> DeliveryPlan:
        """
        Voice delivery path.
        Injects prosody tags → sends to TTS → streams via LiveKit.
        """
        # Inject prosody tags based on user emotion + content
        tagged = self.prosody.tag(
            text=plan.original_text,
            user_emotion=user_emotion,
            intensity=emotion_intensity,
            enable_content_tags=True,
        )

        plan.processed_text = tagged
        plan.prosody_tags_added = tagged.count("[") - plan.original_text.count("[")
        plan.bubbles = [tagged]  # voice is one stream, no splitting

        plan.delivery_steps = [
            {"type": "tts_stream", "text": tagged, "bubble_index": 0}
        ]

        logger.debug(
            f"[DELIVERY] Voice plan: {plan.prosody_tags_added} tags added | "
            f"emotion={user_emotion} ({emotion_intensity:.2f})"
        )

        return plan

    def _prepare_text(
        self,
        plan: DeliveryPlan,
        mode: str,
        user_emotion: str,
    ) -> DeliveryPlan:
        """
        Text delivery path.
        Split → imperfect → typing simulation → delivery plan.
        """
        text = plan.original_text

        # Apply strategic imperfection (based on Law 9 dial)
        text, imperfection_count = self._apply_imperfections(text, mode)
        plan.imperfections_added = imperfection_count

        # Split into bubbles
        bubbles = self.splitter.split(text, mode=mode)
        plan.bubbles = bubbles
        plan.processed_text = " ||| ".join(bubbles)

        # Calculate delivery timing
        plan.delivery_steps = self.typer.calculate_delivery_plan(bubbles)

        plan.total_delivery_ms = sum(
            step["duration_ms"]
            for step in plan.delivery_steps
            if step["type"] in ("typing", "pause")
        )

        logger.debug(
            f"[DELIVERY] Text plan: {len(bubbles)} bubbles | "
            f"{plan.total_delivery_ms}ms total | "
            f"{imperfection_count} imperfections"
        )

        return plan

    def _apply_imperfections(self, text: str, mode: str) -> tuple[str, int]:
        """
        Apply strategic imperfections to text.
        Based on Law 9 (Incomplete Syntax) dial position.
        """
        dial = self._imperfection_dial
        count = 0

        # Spec/build mode: no imperfections
        if mode in ("spec", "build") or dial < 3:
            return text, 0

        # Mirror user's lowercase style
        if self._user_style.get("uses_lowercase", False) and dial >= 5:
            if random.random() < 0.25 and text[0].isupper():
                text = text[0].lower() + text[1:]
                count += 1

        # Drop trailing period (casual)
        if dial >= 5 and text.endswith(".") and random.random() < 0.15:
            text = text[:-1]
            count += 1

        # Abbreviation matching
        if dial >= 6 and self._user_style.get("uses_abbreviations", False):
            if " you " in text and random.random() < 0.1:
                text = text.replace(" you ", " u ", 1)
                count += 1

        return text, count

    def learn_user_style(self, user_message: str) -> None:
        """
        Learn user's text style from their messages.
        Updates internal style model for imperfection matching.
        """
        # Lowercase detection
        if user_message and user_message[0].islower():
            self._user_style["uses_lowercase"] = True

        # Abbreviation detection
        if any(abbr in user_message.lower() for abbr in [" u ", " ur ", " r ", " 2 ", " 4 "]):
            self._user_style["uses_abbreviations"] = True

        # Emoji detection
        if re.search(r'[\U0001F600-\U0001FAD6]', user_message):
            self._user_style["uses_emoji"] = True

    def set_imperfection_dial(self, dial: int) -> None:
        """Update the imperfection dial (Law 9 position)."""
        self._imperfection_dial = max(0, min(10, dial))

    def set_tts_provider(self, provider: str) -> None:
        """Update TTS provider for prosody tagging."""
        self.prosody.set_provider(provider)

    # ---- Backchannel Delegation ----

    def start_user_speaking(self) -> None:
        """Called when user starts talking (voice mode)."""
        self.backchannels.start_user_turn()

    def stop_user_speaking(self) -> None:
        """Called when user stops talking (voice mode)."""
        self.backchannels.end_user_turn()

    def check_backchannel(
        self,
        pause_ms: int,
        user_emotion: str = "neutral",
    ):
        """Check if we should inject a backchannel during user speech."""
        return self.backchannels.should_backchannel(pause_ms, user_emotion)
