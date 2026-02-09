# ============================================
# CHAMP V3 — Brain Pipeline
# The nerve center for Phase 2.
# Flow: Mode Detect → Persona Load → Context Build → LiteLLM
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
from brain.context_builder import ContextBuilder
from brain.llm_client import LiteLLMClient
from brain.memory import SupabaseMemory

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
        self.context_builder = ContextBuilder()
        self.memory = SupabaseMemory(settings)

    async def startup(self) -> None:
        """Initialize components on app startup."""
        await self.persona_loader.load()
        await self.memory.connect()
        logger.info("Brain pipeline initialized")

    async def shutdown(self) -> None:
        """Cleanup on app shutdown."""
        await self.llm_client.close()
        await self.memory.disconnect()
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

        # 3. Fetch memory context
        memory_context = await self.memory.get_context("anthony")

        # 4. Build enriched context (persona + memory + mode)
        enriched_messages = self.context_builder.build(
            original_messages=request.messages,
            persona=self.persona_loader.get_persona(),
            mode=mode,
            memory_context=memory_context,
        )
        enriched_request = request.model_copy(
            update={"messages": enriched_messages}
        )

        # 5. Forward to LiteLLM
        response = await self.llm_client.chat_completion(enriched_request)

        # 6. Store exchange (non-blocking, non-fatal)
        conv_id = request.user or None
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

        elapsed = time.time() - start_time
        logger.info(
            f"[BRAIN] mode={mode.value} | model={request.model} | "
            f"memory={len(memory_context)}chars | {elapsed:.1f}s"
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
        logger.info(f"[STREAM] Mode: {mode.value}")

        # 3. Fetch memory context
        memory_context = await self.memory.get_context("anthony")

        # 4. Build enriched context (persona + memory + mode)
        enriched_messages = self.context_builder.build(
            original_messages=request.messages,
            persona=self.persona_loader.get_persona(),
            mode=mode,
            memory_context=memory_context,
        )
        enriched_request = request.model_copy(
            update={"messages": enriched_messages}
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
        conv_id = request.user or None
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

        elapsed = time.time() - start_time
        logger.info(
            f"[STREAM] Done: {chunk_count} chunks, "
            f"{len(full_response)} chars, memory={len(memory_context)}chars, "
            f"{elapsed:.1f}s"
        )

    def _extract_user_message(self, request: ChatCompletionRequest) -> str:
        """Pull the latest user message text from the request."""
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