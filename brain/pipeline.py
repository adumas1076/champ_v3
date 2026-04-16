# ============================================
# CHAMP V3 — Brain Pipeline
# The nerve center for Phase 2.
# Flow: Mode Detect → Loop Select → Persona Load → Context Build → LiteLLM
# ============================================

import asyncio
import json
import logging
import time
from typing import AsyncIterator

from brain.config import Settings
from brain.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    OutputMode,
)
from brain.persona_loader import PersonaLoader
from brain.mode_detector import ModeDetector
from brain.loop_selector import LoopSelector
from brain.context_builder import ContextBuilder
from brain.context_compressor import ContextCompressor
from brain.llm_client import LiteLLMClient
from brain.cortex_router import select_model
from brain.memory import SupabaseMemory
from brain.memory_snapshot import SnapshotManager
from brain.memory_prefetch import MemoryPrefetcher
from brain.transcript_logger import TranscriptLogger
from mind.healing import HealingLoop
from mind.letta_memory import LettaMemory
from mind.mem0_memory import Mem0Memory
from mind.user_modeling import UserModeling
from mind.skill_engine import SkillEngine
from mind.session_search import SessionSearch
from mind import memory_security

# ---- Conversation Matrix (optional, backward compatible) ----
try:
    from conversation_matrix.hook_manager import HookManager
    from conversation_matrix.dna_compiler import DNACompiler
    from conversation_matrix.conversation_scorer import ConversationScorer
    from mind.emotion_detector import EmotionDetector
    from mind.callback_manager import CallbackManager
    from mind.callback_extractor import CallbackExtractor
    CONVERSATION_MATRIX_AVAILABLE = True
except ImportError:
    CONVERSATION_MATRIX_AVAILABLE = False

logger = logging.getLogger(__name__)


class BrainPipeline:
    """
    Phase 2 Brain Pipeline.

    Every request flows through:
    1. Extract user message
    2. Detect output mode (Vibe/Build/Spec) — BEFORE the LLM call
    3. Fetch memory context (profile + lessons + healing)
    4. Build enriched context (persona + memory + mode instructions)
    5. Forward to LiteLLM with enriched context
    6. Store exchange in Supabase (non-blocking)
    7. Return response that sounds like Champ
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_client = LiteLLMClient(settings)
        self.persona_loader = PersonaLoader(settings)
        self.mode_detector = ModeDetector()
        self.loop_selector = LoopSelector()
        self.context_builder = ContextBuilder()
        self.context_compressor = ContextCompressor(settings)
        self.memory = SupabaseMemory(settings)
        self.healing = HealingLoop()
        self.letta = LettaMemory(settings)
        self.mem0 = Mem0Memory(settings)

        # ---- Hermes-harvested systems ----
        self.snapshot_manager = SnapshotManager()
        self.prefetcher = MemoryPrefetcher()
        self.user_modeling = UserModeling(settings)
        self.skill_engine = SkillEngine(settings)
        self.session_search = SessionSearch(settings)

        # Active transcript loggers keyed by conversation_id
        self._transcript_loggers: dict[str, TranscriptLogger] = {}

        # ---- Conversation Matrix (optional) ----
        self.hook_manager: HookManager | None = None
        self._last_assistant_response: str = ""

    async def startup(self) -> None:
        """Initialize components on app startup."""
        await self.persona_loader.load()
        await self.memory.connect()
        letta_ok = await self.letta.connect()
        mem0_ok = await self.mem0.connect()

        # Hermes-harvested systems startup
        modeling_ok = await self.user_modeling.connect()
        skills_ok = await self.skill_engine.connect()
        search_ok = self.session_search.connect()

        # Sync Supabase profile → Letta memory.human block (default user on startup)
        if letta_ok:
            profile_data = await self.memory.get_profile_data(self.settings.default_user)
            if profile_data:
                synced = await self.letta.sync_from_supabase(profile_data)
                logger.info(
                    f"[LETTA] Synced {len(profile_data)} profile entries to memory.human"
                    if synced else "[LETTA] Profile sync skipped (no data or error)"
                )

        # ---- Conversation Matrix initialization ----
        matrix_ok = False
        if CONVERSATION_MATRIX_AVAILABLE:
            try:
                dna = DNACompiler()
                dna.load_defaults()
                # Load operator overrides from config if available
                # (PersonaLoader handles this in full boot sequence)
                scorer = ConversationScorer(
                    rubric=dna.get_scoring_rubric(),
                    dial_weights=dna.get_dial_weights(),
                )
                cb_manager = CallbackManager(self.settings)
                await cb_manager.connect()

                self.hook_manager = HookManager(
                    dna_compiler=dna,
                    emotion_detector=EmotionDetector(),
                    callback_manager=cb_manager,
                    callback_extractor=CallbackExtractor(),
                    conversation_scorer=scorer,
                )
                matrix_ok = True
                logger.info("[MATRIX] Conversation Matrix initialized")
            except Exception as e:
                logger.warning(f"[MATRIX] Init failed (graceful degradation): {e}")
                self.hook_manager = None

        logger.info(
            f"Brain pipeline initialized | "
            f"Letta: {'connected' if letta_ok else 'offline (graceful degradation)'} | "
            f"Mem0: {'connected' if mem0_ok else 'offline (graceful degradation)'} | "
            f"UserModeling: {'connected' if modeling_ok else 'offline'} | "
            f"Skills: {'connected' if skills_ok else 'offline'} | "
            f"SessionSearch: {'connected' if search_ok else 'offline'} | "
            f"Matrix: {'active' if matrix_ok else 'offline'}"
        )

    async def shutdown(self) -> None:
        """Cleanup on app shutdown."""
        await self.llm_client.close()
        await self.memory.disconnect()
        await self.letta.disconnect()
        await self.mem0.disconnect()
        await self.user_modeling.disconnect()
        await self.skill_engine.disconnect()
        self.session_search.disconnect()
        logger.info("Brain pipeline shut down")

    # ---- Session Snapshot Lifecycle ----

    async def capture_snapshot(
        self, session_id: str, user_id: str
    ) -> None:
        """
        Capture frozen memory snapshot at session start.
        Called once — snapshot stays immutable for the entire session.
        Hermes Pattern #1: Frozen Snapshot.
        """
        await self.snapshot_manager.capture(
            session_id=session_id,
            user_id=user_id,
            memory=self.memory,
            letta=self.letta,
            mem0=self.mem0,
            user_modeling=self.user_modeling,
        )

    def release_session(self, session_id: str) -> None:
        """Clean up session-scoped resources."""
        self.snapshot_manager.discard(session_id)
        self.prefetcher.discard(session_id)
        self.context_compressor.discard_session(session_id)

    async def handle_request(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Handle a non-streaming chat completion request."""
        start_time = time.time()
        _regen_count = 0

        # 1. Extract user message
        user_message = self._extract_user_message(request)

        # 1.1 Security scan on user message (Hermes Pattern #6)
        threats = memory_security.scan_content(user_message)
        if threats:
            logger.warning(
                f"[SECURITY] User message threats: {[t['threat_type'] for t in threats]}"
            )

        # 2. Detect mode BEFORE LLM call
        mode = self.mode_detector.detect(user_message)

        # 2.1 Select execution loop
        loop = self.loop_selector.select(user_message)
        loop_instruction = self.loop_selector.get_instruction(loop)

        # 2.5 Resolve user ID — multi-user support
        user_id = self._resolve_user_id(request)
        conv_id = request.user or None

        # 2.6 Healing detection (real-time friction check)
        recent = await self.memory.get_recent_messages(conv_id, limit=6) if conv_id else []
        healing = self.healing.detect(user_message, mode, recent)
        if healing.mode_override:
            logger.info(f"[HEALING] Mode override: {mode.value} -> {healing.mode_override.value}")
            mode = healing.mode_override

        # 3. Memory context — FROZEN SNAPSHOT + PREFETCH (Hermes Patterns #1 & #2)
        # Try frozen snapshot first (session-scoped, stable, prefix-cache friendly)
        snapshot = self.snapshot_manager.get(conv_id or "") if conv_id else None
        if snapshot and snapshot.is_frozen:
            memory_context = snapshot.format()
        else:
            # Fallback: live fetch (first request before snapshot exists)
            memory_context = await self.memory.get_context(user_id)
            letta_context = await self.letta.get_all_blocks()
            if letta_context:
                memory_context = (memory_context + "\n\n" + letta_context) if memory_context else letta_context

        # Consume prefetch cache (dynamic per-turn context from background fetch)
        prefetch = self.prefetcher.consume(conv_id or "")
        if prefetch and not prefetch.stale:
            if prefetch.mem0_context:
                memory_context = (memory_context + "\n\n" + prefetch.mem0_context) if memory_context else prefetch.mem0_context
            if prefetch.healing_context:
                memory_context = (memory_context + "\n\n" + prefetch.healing_context) if memory_context else prefetch.healing_context
            if prefetch.user_model_update:
                memory_context = (memory_context + "\n\n" + prefetch.user_model_update) if memory_context else prefetch.user_model_update
        else:
            # No prefetch cache — sync fetch Mem0 (first turn or stale)
            mem0_context = await self.mem0.get_context(user_id, query=user_message)
            if mem0_context:
                memory_context = (memory_context + "\n\n" + mem0_context) if memory_context else mem0_context

        if healing.warning_text:
            memory_context = memory_context + "\n\n" + healing.warning_text if memory_context else healing.warning_text
        if loop_instruction:
            memory_context = memory_context + loop_instruction if memory_context else loop_instruction

        # 3.5 Skill recall (Hermes Pattern #4)
        operator_name = self._resolve_operator_name(request)
        recalled_skills = await self.skill_engine.recall(operator_name, user_message)
        if recalled_skills:
            skills_text = self.skill_engine.format_skills_for_prompt(recalled_skills)
            memory_context = (memory_context + "\n\n" + skills_text) if memory_context else skills_text

        # 4. Build enriched context (persona + memory + mode + loop)
        enriched_messages = self.context_builder.build(
            original_messages=request.messages,
            persona=self.persona_loader.get_persona(),
            mode=mode,
            memory_context=memory_context,
            model=request.model,
        )

        # 4.5 Context compression (Hermes Pattern #7)
        if self.context_compressor.should_compress(enriched_messages, request.model):
            enriched_messages = await self.context_compressor.compress(
                session_id=conv_id or "unknown",
                messages=enriched_messages,
                model=request.model,
            )

        # 4.7 Cortex Routing — select optimal model per-turn
        route = select_model(
            message=user_message,
            has_images=self._has_images(request),
            operator_name=operator_name,
            current_model=request.model if request.model != self.settings.default_model else None,
        )
        logger.info(f"[CORTEX] {route.reason} → model={route.model} (tier={route.cost_tier})")

        enriched_request = request.model_copy(
            update={"messages": enriched_messages, "model": route.model}
        )

        # 5. Forward to LiteLLM
        response = await self.llm_client.chat_completion(enriched_request)

        # 5.5 Conversation Matrix post-hooks (scoring + callback extraction)
        assistant_content = response.choices[0].message.content if response.choices else ""
        if self.hook_manager and hook_ctx and assistant_content:
            try:
                post_result = await self.hook_manager.run_post_hooks(
                    response=assistant_content,
                    ctx=hook_ctx,
                    previous_response=self._last_assistant_response,
                )
                if post_result.needs_regeneration and _regen_count < 2:
                    _regen_count += 1
                    logger.info(f"[MATRIX] Regenerating (attempt {_regen_count}): {post_result.regeneration_feedback[:100]}")
                    # Inject feedback and regenerate
                    regen_msg = ChatMessage(role="system", content=post_result.regeneration_feedback)
                    enriched_messages_regen = enriched_messages + [regen_msg]
                    regen_request = request.model_copy(update={"messages": enriched_messages_regen})
                    response = await self.llm_client.chat_completion(regen_request)
                    assistant_content = response.choices[0].message.content if response.choices else assistant_content
                self._last_assistant_response = assistant_content
            except Exception as e:
                logger.error(f"[MATRIX] Post-hook failed (non-fatal): {e}")

        # 6. Store exchange (non-blocking, non-fatal)
        if conv_id:
            try:
                await self.memory.store_message(
                    conv_id, "user", user_message
                )
                await self.memory.store_message(
                    conv_id, "assistant", assistant_content,
                    mode=mode.value, model_used=request.model,
                )
            except Exception as e:
                logger.error(f"Message storage failed (non-fatal): {e}")

            # 6.1 Log to transcript logger (non-fatal)
            try:
                tl = self.get_or_create_transcript_logger(conv_id)
                tl.log_user(user_message)
                tl.log_agent(assistant_content)
            except Exception as e:
                logger.error(f"Transcript logging failed (non-fatal): {e}")

        # 6.5 Log healing issues to Supabase (non-blocking)
        if healing.issues and conv_id:
            for issue in healing.issues:
                try:
                    await self.memory.insert_healing(
                        user_id=user_id,
                        error_type=issue["type"],
                        severity=issue["severity"],
                        trigger_context=issue.get("context", ""),
                        prevention_rule=issue.get("rule", ""),
                    )
                except Exception as e:
                    logger.error(f"Healing log failed (non-fatal): {e}")

        # 7. Post-response: fire async prefetch for NEXT turn (Hermes Pattern #2)
        if conv_id:
            await self.prefetcher.prefetch(
                session_id=conv_id,
                user_message=user_message,
                user_id=user_id,
                mem0=self.mem0,
                memory=self.memory,
                user_modeling=self.user_modeling,
                conv_id=conv_id,
            )

        # 7.1 Post-response: async user modeling observation (Hermes Pattern #3)
        if conv_id and assistant_content:
            asyncio.create_task(
                self.user_modeling.observe(
                    user_id=user_id,
                    operator_name=operator_name,
                    user_message=user_message,
                    assistant_response=assistant_content,
                    session_id=conv_id,
                )
            )

        elapsed = time.time() - start_time
        logger.info(
            f"[BRAIN] mode={mode.value} | loop={loop.value} | model={request.model} | "
            f"memory={len(memory_context)}chars | "
            f"healing={len(healing.issues)} issues | "
            f"skills={len(recalled_skills)} | "
            f"snapshot={'frozen' if (snapshot and snapshot.is_frozen) else 'live'} | "
            f"prefetch={'hit' if (prefetch and not prefetch.stale) else 'miss'} | "
            f"{elapsed:.1f}s"
        )

        return response

    async def handle_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[str]:
        """
        Handle a streaming chat completion request.
        Primary path for voice agent.
        Yields raw SSE lines from LiteLLM.
        """
        start_time = time.time()

        # 1. Extract user message
        user_message = self._extract_user_message(request)
        logger.info(f"[STREAM] User: {user_message[:100]}")

        # 1.1 Security scan (Hermes Pattern #6)
        threats = memory_security.scan_content(user_message)
        if threats:
            logger.warning(f"[STREAM][SECURITY] Threats: {[t['threat_type'] for t in threats]}")

        # 2. Detect mode BEFORE LLM call
        mode = self.mode_detector.detect(user_message)

        # 2.1 Select execution loop
        loop = self.loop_selector.select(user_message)
        loop_instruction = self.loop_selector.get_instruction(loop)
        logger.info(f"[STREAM] Mode: {mode.value} | Loop: {loop.value}")

        # 2.5 Resolve user ID — multi-user support
        user_id = self._resolve_user_id(request)
        conv_id = request.user or None

        # 2.6 Healing detection (real-time friction check)
        recent = await self.memory.get_recent_messages(conv_id, limit=6) if conv_id else []
        healing = self.healing.detect(user_message, mode, recent)
        if healing.mode_override:
            logger.info(f"[STREAM][HEALING] Mode override: {mode.value} -> {healing.mode_override.value}")
            mode = healing.mode_override

        # 3. Memory context — FROZEN SNAPSHOT + PREFETCH (Hermes Patterns #1 & #2)
        snapshot = self.snapshot_manager.get(conv_id or "") if conv_id else None
        if snapshot and snapshot.is_frozen:
            memory_context = snapshot.format()
        else:
            memory_context = await self.memory.get_context(user_id)
            letta_context = await self.letta.get_all_blocks()
            if letta_context:
                memory_context = (memory_context + "\n\n" + letta_context) if memory_context else letta_context

        # Consume prefetch cache
        prefetch = self.prefetcher.consume(conv_id or "")
        if prefetch and not prefetch.stale:
            if prefetch.mem0_context:
                memory_context = (memory_context + "\n\n" + prefetch.mem0_context) if memory_context else prefetch.mem0_context
            if prefetch.healing_context:
                memory_context = (memory_context + "\n\n" + prefetch.healing_context) if memory_context else prefetch.healing_context
            if prefetch.user_model_update:
                memory_context = (memory_context + "\n\n" + prefetch.user_model_update) if memory_context else prefetch.user_model_update
        else:
            mem0_context = await self.mem0.get_context(user_id, query=user_message)
            if mem0_context:
                memory_context = (memory_context + "\n\n" + mem0_context) if memory_context else mem0_context

        if healing.warning_text:
            memory_context = memory_context + "\n\n" + healing.warning_text if memory_context else healing.warning_text
        if loop_instruction:
            memory_context = memory_context + loop_instruction if memory_context else loop_instruction

        # 3.5 Skill recall (Hermes Pattern #4)
        operator_name = self._resolve_operator_name(request)
        recalled_skills = await self.skill_engine.recall(operator_name, user_message)
        if recalled_skills:
            skills_text = self.skill_engine.format_skills_for_prompt(recalled_skills)
            memory_context = (memory_context + "\n\n" + skills_text) if memory_context else skills_text

        # 4. Build enriched context (persona + memory + mode + loop)
        enriched_messages = self.context_builder.build(
            original_messages=request.messages,
            persona=self.persona_loader.get_persona(),
            mode=mode,
            memory_context=memory_context,
            model=request.model,
        )

        # 4.5 Context compression (Hermes Pattern #7)
        if self.context_compressor.should_compress(enriched_messages, request.model):
            enriched_messages = await self.context_compressor.compress(
                session_id=conv_id or "unknown",
                messages=enriched_messages,
                model=request.model,
            )

        # 4.7 Cortex Routing — select optimal model per-turn
        route = select_model(
            message=user_message,
            has_images=self._has_images(request),
            operator_name=operator_name,
            current_model=request.model if request.model != self.settings.default_model else None,
        )
        logger.info(f"[STREAM][CORTEX] {route.reason} → model={route.model} (tier={route.cost_tier})")

        enriched_request = request.model_copy(
            update={"messages": enriched_messages, "model": route.model}
        )

        # 5. Stream from LiteLLM
        full_response = ""
        chunk_count = 0
        async for line in self.llm_client.chat_completion_stream_raw(
            enriched_request
        ):
            # Peek at content for logging (don't modify the stream)
            if line.startswith("data: ") and line[6:].strip() != "[DONE]":
                try:
                    chunk = json.loads(line[6:])
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            full_response += content
                except (json.JSONDecodeError, IndexError, KeyError):
                    pass

            yield line
            chunk_count += 1

        # 6. Store exchange (non-blocking, non-fatal)
        if conv_id:
            try:
                await self.memory.store_message(
                    conv_id, "user", user_message
                )
                await self.memory.store_message(
                    conv_id, "assistant", full_response,
                    mode=mode.value, model_used=request.model,
                )
            except Exception as e:
                logger.error(f"Stream message storage failed (non-fatal): {e}")

            # 6.1 Log to transcript logger (non-fatal)
            try:
                tl = self.get_or_create_transcript_logger(conv_id)
                tl.log_user(user_message)
                tl.log_agent(full_response)
            except Exception as e:
                logger.error(f"Stream transcript logging failed (non-fatal): {e}")

        # 6.5 Log healing issues to Supabase (non-blocking)
        if healing.issues and conv_id:
            for issue in healing.issues:
                try:
                    await self.memory.insert_healing(
                        user_id=user_id,
                        error_type=issue["type"],
                        severity=issue["severity"],
                        trigger_context=issue.get("context", ""),
                        prevention_rule=issue.get("rule", ""),
                    )
                except Exception as e:
                    logger.error(f"Stream healing log failed (non-fatal): {e}")

        # 7. Post-response: fire async prefetch for NEXT turn (Hermes Pattern #2)
        if conv_id:
            await self.prefetcher.prefetch(
                session_id=conv_id,
                user_message=user_message,
                user_id=user_id,
                mem0=self.mem0,
                memory=self.memory,
                user_modeling=self.user_modeling,
                conv_id=conv_id,
            )

        # 7.1 Post-response: async user modeling observation (Hermes Pattern #3)
        if conv_id and full_response:
            asyncio.create_task(
                self.user_modeling.observe(
                    user_id=user_id,
                    operator_name=operator_name,
                    user_message=user_message,
                    assistant_response=full_response,
                    session_id=conv_id,
                )
            )

        elapsed = time.time() - start_time
        logger.info(
            f"[STREAM] Done: {chunk_count} chunks, "
            f"{len(full_response)} chars, memory={len(memory_context)}chars, "
            f"healing={len(healing.issues)} issues, "
            f"skills={len(recalled_skills)}, "
            f"snapshot={'frozen' if (snapshot and snapshot.is_frozen) else 'live'}, "
            f"prefetch={'hit' if (prefetch and not prefetch.stale) else 'miss'}, "
            f"{elapsed:.1f}s"
        )

    # ---- Transcript Logger Management ----

    def get_or_create_transcript_logger(self, session_id: str) -> TranscriptLogger:
        """Get an existing transcript logger for a session, or create one."""
        if session_id not in self._transcript_loggers:
            self._transcript_loggers[session_id] = TranscriptLogger(session_id)
            logger.info(f"[TRANSCRIPT] Logger created for session {session_id}")
        return self._transcript_loggers[session_id]

    def get_transcript_logger(self, session_id: str) -> TranscriptLogger | None:
        """Get the transcript logger for a session, or None if not found."""
        return self._transcript_loggers.get(session_id)

    def close_transcript_logger(self, session_id: str) -> TranscriptLogger | None:
        """Close and remove the transcript logger for a session. Returns the logger."""
        tl = self._transcript_loggers.pop(session_id, None)
        if tl:
            tl.close()
        return tl

    def _extract_user_message(self, request: ChatCompletionRequest) -> str:
        """Pull the latest user message text from the request.
        Extracts text parts from multimodal messages.
        Image parts are preserved in the original message for LiteLLM forwarding.
        """
        for msg in reversed(request.messages):
            if msg.role == "user":
                if isinstance(msg.content, str):
                    return msg.content
                if isinstance(msg.content, list):
                    text_parts = [
                        part.get("text", "")
                        for part in msg.content
                        if isinstance(part, dict) and part.get("type") == "text"
                    ]
                    return " ".join(text_parts)
        return ""

    def _resolve_user_id(self, request: ChatCompletionRequest) -> str:
        """
        Extract the user ID from the request.

        Multi-user support: the user field can carry either a conversation ID
        or a user_id:conversation_id format. We extract the user_id portion.

        Falls back to settings.default_user if not provided.
        """
        raw = request.user or ""
        if ":" in raw:
            # Format: "user_id:conversation_id"
            return raw.split(":")[0]
        if raw:
            # Could be just a conversation ID — check if it looks like a user ID
            # (no dashes = likely a user ID, dashes = likely a UUID conversation ID)
            if "-" not in raw and len(raw) < 50:
                return raw
        return self.settings.default_user

    def _resolve_operator_name(self, request: ChatCompletionRequest) -> str:
        """Extract operator name from request metadata, default to 'champ'."""
        # Check if operator name is passed in metadata or headers
        raw = request.user or ""
        if ":" in raw:
            parts = raw.split(":")
            if len(parts) >= 3:
                return parts[2]  # user_id:conv_id:operator_name
        return "champ"

    def _has_images(self, request: ChatCompletionRequest) -> bool:
        """Check if the request contains image content."""
        for msg in request.messages:
            if isinstance(msg.content, list):
                for part in msg.content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return True
        return False