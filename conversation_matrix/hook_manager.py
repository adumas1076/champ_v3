# ============================================
# Conversation Matrix — Hook Manager
# Wraps all pre/post hooks into a clean interface.
# Doesn't replace BrainPipeline — organizes it.
# ============================================

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from mind.emotion_detector import EmotionDetector, EmotionResult
from mind.callback_manager import CallbackManager, Callback
from mind.callback_extractor import CallbackExtractor
from conversation_matrix.conversation_scorer import ConversationScorer, ScoringResult
from conversation_matrix.dna_compiler import DNACompiler

logger = logging.getLogger(__name__)


@dataclass
class HookContext:
    """Context assembled by pre-hooks, consumed by LLM and post-hooks."""
    user_message: str = ""
    session_id: str = ""
    user_id: str = ""
    operator_name: str = "champ"
    channel: str = "text"

    # Pre-hook outputs
    mode: str = "vibe"
    emotion: Optional[EmotionResult] = None
    emotion_context: str = ""
    callback_context: str = ""
    callbacks: list = field(default_factory=list)
    conversation_history: list = field(default_factory=list)
    dna_modifiers: dict = field(default_factory=dict)


@dataclass
class PostHookResult:
    """Result of post-hook processing."""
    response: str = ""
    passed: bool = True
    needs_regeneration: bool = False
    regeneration_feedback: str = ""
    violations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class HookManager:
    """
    Manages pre and post hooks for the Conversation Matrix.

    Wraps existing pipeline steps (HealingLoop, MemoryPrefetch, etc.)
    and adds new hooks (emotion detection, callback injection, scoring).

    Design:
    - Hooks run in defined order
    - Each hook can add context
    - Pre-hooks build the enriched context
    - Post-hooks validate and extract from the response
    - All hooks are non-fatal — failure logs but doesn't block
    """

    def __init__(
        self,
        dna_compiler: DNACompiler,
        emotion_detector: Optional[EmotionDetector] = None,
        callback_manager: Optional[CallbackManager] = None,
        callback_extractor: Optional[CallbackExtractor] = None,
        conversation_scorer: Optional[ConversationScorer] = None,
    ):
        self.dna_compiler = dna_compiler
        self.emotion_detector = emotion_detector or EmotionDetector()
        self.callback_manager = callback_manager
        self.callback_extractor = callback_extractor or CallbackExtractor()
        self.conversation_scorer = conversation_scorer or ConversationScorer()
        self.max_regenerations = 2

    async def run_pre_hooks(
        self,
        user_message: str,
        session_id: str = "",
        user_id: str = "",
        operator_name: str = "champ",
        channel: str = "text",
        mode: str = "vibe",
        conversation_history: list[str] = None,
    ) -> HookContext:
        """
        Run all NEW pre-hooks and return enriched context.

        NOTE: Existing pre-hooks (HealingLoop, MemoryPrefetch, SnapshotManager,
        SkillEngine, ModeDetector, SecurityScan) continue to run in pipeline.py.
        This method adds the NEW hooks on top.
        """
        ctx = HookContext(
            user_message=user_message,
            session_id=session_id,
            user_id=user_id,
            operator_name=operator_name,
            channel=channel,
            mode=mode,
            conversation_history=conversation_history or [],
        )

        # ---- NEW Pre-Hook 4: Emotion Detection ----
        try:
            ctx.emotion = self.emotion_detector.detect(user_message)
            ctx.emotion_context = self.emotion_detector.format_for_injection(ctx.emotion)
        except Exception as e:
            logger.error(f"[HOOKS] Emotion detection failed (non-fatal): {e}")
            ctx.emotion_context = ""

        # ---- NEW Pre-Hook 7: Callback Injection ----
        if self.callback_manager:
            try:
                ctx.callbacks = await self.callback_manager.get_active(
                    user_id=user_id,
                    session_id=session_id,
                    operator_name=operator_name,
                    limit=5,
                )
                ctx.callback_context = self.callback_manager.format_for_injection(
                    ctx.callbacks
                )
            except Exception as e:
                logger.error(f"[HOOKS] Callback injection failed (non-fatal): {e}")
                ctx.callback_context = ""

        # ---- Apply mode DNA modifiers ----
        try:
            self.dna_compiler.apply_mode_modifier(mode)
            self.dna_compiler.apply_channel_modifier(channel)
        except Exception as e:
            logger.error(f"[HOOKS] DNA modifier application failed (non-fatal): {e}")

        logger.debug(
            f"[HOOKS] Pre-hooks complete | "
            f"emotion={ctx.emotion.primary if ctx.emotion else 'none'} | "
            f"callbacks={len(ctx.callbacks)} | "
            f"mode={mode} | channel={channel}"
        )

        return ctx

    async def run_post_hooks(
        self,
        response: str,
        ctx: HookContext,
        previous_response: str = "",
    ) -> PostHookResult:
        """
        Run all NEW post-hooks. Returns validated response or regeneration request.

        NOTE: Existing post-hooks (message storage, transcript logging,
        healing logging, prefetch, user modeling) continue in pipeline.py.
        """
        result = PostHookResult(response=response)

        # ---- NEW Post-Hook 1: Tier 1 Quick Check ----
        try:
            violations = self.conversation_scorer.quick_check(
                response=response,
                channel=ctx.channel,
                mode=ctx.mode,
            )
            if violations:
                result.passed = False
                result.needs_regeneration = True
                result.violations = violations
                result.regeneration_feedback = (
                    self.conversation_scorer.build_regeneration_feedback(violations)
                )
                logger.info(
                    f"[HOOKS] Tier 1 FAIL: {len(violations)} violations — "
                    f"regeneration requested"
                )
                return result
        except Exception as e:
            logger.error(f"[HOOKS] Tier 1 scoring failed (non-fatal): {e}")

        # ---- NEW Post-Hook 2: Heuristic Checks (warnings only) ----
        try:
            warnings = self.conversation_scorer.heuristic_check(
                response=response,
                history=ctx.conversation_history,
                user_emotion=ctx.emotion.primary if ctx.emotion else "neutral",
                mode=ctx.mode,
            )
            result.warnings = warnings
            if warnings:
                logger.debug(
                    f"[HOOKS] Heuristic warnings: {[w['rule'] for w in warnings]}"
                )
        except Exception as e:
            logger.error(f"[HOOKS] Heuristic check failed (non-fatal): {e}")

        # ---- NEW Post-Hook 3: Callback Extraction (async, non-blocking) ----
        if previous_response and ctx.user_message:
            try:
                asyncio.create_task(
                    self._extract_callbacks_async(
                        previous_response=previous_response,
                        user_reaction=ctx.user_message,
                        session_id=ctx.session_id,
                        user_id=ctx.user_id,
                        operator_name=ctx.operator_name,
                    )
                )
            except Exception as e:
                logger.error(f"[HOOKS] Callback extraction failed (non-fatal): {e}")

        result.passed = True
        logger.debug("[HOOKS] Post-hooks complete | PASSED")
        return result

    async def _extract_callbacks_async(
        self,
        previous_response: str,
        user_reaction: str,
        session_id: str,
        user_id: str,
        operator_name: str,
    ) -> None:
        """
        Async callback extraction — runs in background after each turn.
        Scans the user's message for signals that our previous response landed.
        """
        signals = self.callback_extractor.scan_user_message(user_reaction)

        if not signals or not self.callback_manager:
            return

        callback_entries = self.callback_extractor.extract_callback_context(
            previous_ai_response=previous_response,
            user_reaction=user_reaction,
            signals=signals,
        )

        for entry in callback_entries:
            await self.callback_manager.store(
                session_id=session_id,
                user_id=user_id,
                operator_name=operator_name,
                **entry,
            )

    def get_additional_context(self, ctx: HookContext) -> str:
        """
        Get the additional context strings to append to memory_context
        in the pipeline. Called from pipeline.py after existing context build.
        """
        parts = []

        if ctx.emotion_context:
            parts.append(ctx.emotion_context)

        if ctx.callback_context:
            parts.append(ctx.callback_context)

        return "\n\n".join(parts) if parts else ""
