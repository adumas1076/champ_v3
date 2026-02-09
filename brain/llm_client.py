# ============================================
# CHAMP V3 — LiteLLM Client
# Async HTTP client for LiteLLM proxy (port 4000)
# Supports streaming + non-streaming
# ============================================

import logging
from typing import AsyncIterator

import httpx

from brain.config import Settings
from brain.models import ChatCompletionRequest, ChatCompletionResponse

logger = logging.getLogger(__name__)


class LiteLLMClient:
    """
    Async HTTP client for the LiteLLM proxy.
    Handles both streaming (SSE) and non-streaming requests.
    """

    def __init__(self, settings: Settings):
        self.base_url = settings.litellm_base_url
        self.api_key = settings.litellm_api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                limits=httpx.Limits(
                    max_connections=20, max_keepalive_connections=10
                ),
            )
        return self._client

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Non-streaming chat completion. Returns full response."""
        client = await self._get_client()

        payload = request.model_dump(exclude_none=True)
        payload["stream"] = False

        url = f"{self.base_url}/chat/completions"
        logger.info(
            f"[LLM] Request: {url} | model={payload.get('model')} | "
            f"messages={len(payload.get('messages', []))}"
        )

        response = await client.post(
            url, headers=self._headers(), json=payload
        )
        response.raise_for_status()
        return ChatCompletionResponse(**response.json())

    async def chat_completion_stream_raw(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[str]:
        """
        Streaming chat completion — yields raw SSE lines.
        Preserves exact format the OpenAI SDK expects.
        """
        client = await self._get_client()

        payload = request.model_dump(exclude_none=True)
        payload["stream"] = True

        url = f"{self.base_url}/chat/completions"
        logger.info(
            f"[LLM] Streaming: {url} | model={payload.get('model')}"
        )

        async with client.stream(
            "POST", url, headers=self._headers(), json=payload
        ) as response:
            response.raise_for_status()
            line_count = 0
            async for line in response.aiter_lines():
                if not line:
                    continue
                yield line
                line_count += 1
            logger.info(f"[LLM] Stream ended: {line_count} lines")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None