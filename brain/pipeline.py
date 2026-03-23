# ============================================
# CHAMP V3 — Brain Pipeline
# The nerve center for Phase 2.
# Flow: Mode Detect → Loop Select → Persona Load → Context Build → LiteLLM
# ============================================

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
from brain.llm_client import LiteLLMClient
from brain.memory import SupabaseMemory
from mind.healing import HealingLoop
from mind.letta_memory import LettaMemory

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
        self.memory = SupabaseMemory(settings)
        self.healing = HealingLoop()
        self.letta = LettaMemory(settings)

    async def startup(self) -> None:
        """Initialize components on app startup."""
        await self.persona_loader.load()
        await self.memory.connect()
        letta_ok = await self.letta.connect()

        # Sync Supabase profile → Letta memory.human block (default user on startup)
        if letta_ok:
            profile_data = await self.memory.get_profile_data(self.settings.default_user)
            if profile_data:
                synced = await self.letta.sync_from_supabase(profile_data)
                logger.info(
                    f"[LETTA] Synced {len(profile_data)} profile entries to memory.human"
                    if synced else "[LETTA] Profile sync skipped (no data or error)"
                )

        logger.info(
            f"Brain pipeline initialized | "
            f"Letta: {'connected' if letta_ok else 'offline (graceful degradation)'}"
        )

    async def shutdown(self) -> None:
        """Cleanup on app shutdown."""
        await self.llm_client.close()
        await self.memory.disconnect()
        await self.letta.disconnect()
        logger.info("Brain pipeline shut down")

    async def handle_request(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Handle a non-streaming chat completion request."""
        start_time = time.time()

        # 1. Extract user message
        user_message = self._extract_user_message(request)

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

        # 3. Fetch memory context (Supabase + Letta) — per user
        memory_context = await self.memory.get_context(user_id)
        letta_context = await self.letta.get_all_blocks()
        if letta_context:
            memory_context = (memory_context + "\n\n" + letta_context) if memory_context else letta_context
        if healing.warning_text:
            memory_context = memory_context + "\n\n" + healing.warning_text if memory_context else healing.warning_text
        if loop_instruction:
            memory_context = memory_context + loop_instruction if memory_context else loop_instruction

        # 4. Build enriched context (persona + memory + mode + loop)
        enriched_messages = self.context_builder.build(
            original_messages=request.messages,
            persona=self.persona_loader.get_persona(),
            mode=mode,
            memory_context=memory_context,
        )
        # Auto-route images to vision model (Gemini Flash)
        model_override = {}
        if self._has_images(request):
            model_override = {"model": "gemini-flash"}
            logger.info("[BRAIN] Image detected — routing to Gemini Flash (vision)")

        enriched_request = request.model_copy(
            update={"messages": enriched_messages, **model_override}
        )

        # 5. Forward to LiteLLM
        response = await self.llm_client.chat_completion(enriched_request)

        # 6. Store exchange (non-blocking, non-fatal)
        if conv_id:
            try:
                await self.memory.store_message(
                    conv_id, "user", user_message
                )
                assistant_content = response.choices[0].message.content if response.choices else ""
                await self.memory.store_message(
                    conv_id, "assistant", assistant_content,
                    mode=mode.value, model_used=request.model,
                )
            except Exception as e:
                logger.error(f"Message storage failed (non-fatal): {e}")

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

        elapsed = time.time() - start_time
        logger.info(
            f"[BRAIN] mode={mode.value} | loop={loop.value} | model={request.model} | "
            f"memory={len(memory_context)}chars | "
            f"healing={len(healing.issues)} issues | {elapsed:.1f}s"
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

        # 3. Fetch memory context (Supabase + Letta) — per user
        memory_context = await self.memory.get_context(user_id)
        letta_context = await self.letta.get_all_blocks()
        if letta_context:
            memory_context = (memory_context + "\n\n" + letta_context) if memory_context else letta_context
        if healing.warning_text:
            memory_context = memory_context + "\n\n" + healing.warning_text if memory_context else healing.warning_text
        if loop_instruction:
            memory_context = memory_context + loop_instruction if memory_context else loop_instruction

        # 4. Build enriched context (persona + memory + mode + loop)
        enriched_messages = self.context_builder.build(
            original_messages=request.messages,
            persona=self.persona_loader.get_persona(),
            mode=mode,
            memory_context=memory_context,
        )
        # Auto-route images to vision model (Gemini Flash)
        model_override = {}
        if self._has_images(request):
            model_override = {"model": "gemini-flash"}
            logger.info("[STREAM] Image detected — routing to Gemini Flash (vision)")

        enriched_request = request.model_copy(
            update={"messages": enriched_messages, **model_override}
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

        elapsed = time.time() - start_time
        logger.info(
            f"[STREAM] Done: {chunk_count} chunks, "
            f"{len(full_response)} chars, memory={len(memory_context)}chars, "
            f"healing={len(healing.issues)} issues, "
            f"{elapsed:.1f}s"
        )

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

    def _has_images(self, request: ChatCompletionRequest) -> bool:
        """Check if the request contains image content."""
        for msg in request.messages:
            if isinstance(msg.content, list):
                for part in msg.content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return True
        return False