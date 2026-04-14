# ============================================
# CHAMP V3 — Async Memory Prefetch
# Harvested from: Hermes Agent (NousResearch)
#
# Pattern: At the end of Turn N, fire background
# tasks to pre-fetch context for Turn N+1.
# When the next user message arrives, results
# are already cached = zero blocking on response.
#
# This makes operators feel instant even with
# multiple memory sources (Supabase, Letta, Mem0).
# ============================================

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PrefetchResult:
    """Cached result from a background prefetch."""
    mem0_context: str = ""
    healing_context: str = ""
    user_model_update: str = ""
    fetched_at: float = 0.0
    query: str = ""
    stale: bool = False

    @property
    def age_seconds(self) -> float:
        if self.fetched_at == 0:
            return float("inf")
        return time.time() - self.fetched_at


class MemoryPrefetcher:
    """
    Zero-latency memory retrieval via background prefetching.

    How it works:
    1. After each assistant response, call prefetch(user_message)
    2. Background tasks fetch Mem0 context, healing updates, user model
    3. On the NEXT turn, call consume() to get cached results
    4. If cache is stale (>60s) or missing, falls back to sync fetch

    The frozen snapshot (from SnapshotManager) handles static memory.
    The prefetcher handles DYNAMIC per-turn context that benefits
    from query-specific retrieval (like Mem0 semantic search).
    """

    # Results older than this are considered stale
    STALE_THRESHOLD_SECONDS = 60.0

    def __init__(self):
        self._cache: dict[str, PrefetchResult] = {}
        self._pending: dict[str, asyncio.Task] = {}

    async def prefetch(
        self,
        session_id: str,
        user_message: str,
        user_id: str,
        mem0=None,
        memory=None,
        user_modeling=None,
        conv_id: Optional[str] = None,
    ) -> None:
        """
        Fire background tasks to pre-fetch context for the next turn.
        Called AFTER the assistant response is sent (non-blocking).
        """
        # Cancel any existing prefetch for this session
        existing = self._pending.pop(session_id, None)
        if existing and not existing.done():
            existing.cancel()

        # Launch background task
        task = asyncio.create_task(
            self._do_prefetch(
                session_id, user_message, user_id,
                mem0, memory, user_modeling, conv_id,
            )
        )
        self._pending[session_id] = task

    async def _do_prefetch(
        self,
        session_id: str,
        user_message: str,
        user_id: str,
        mem0,
        memory,
        user_modeling,
        conv_id: Optional[str],
    ) -> None:
        """Background prefetch worker."""
        result = PrefetchResult(query=user_message)

        tasks = []

        # 1. Mem0 semantic search (most expensive, benefits most from prefetch)
        if mem0:
            tasks.append(self._fetch_mem0(mem0, user_id, user_message, result))

        # 2. Healing context refresh
        if memory and conv_id:
            tasks.append(self._fetch_healing(memory, conv_id, user_message, result))

        # 3. User model dynamic update
        if user_modeling:
            tasks.append(
                self._fetch_user_model_update(user_modeling, user_id, user_message, result)
            )

        # Run all in parallel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        result.fetched_at = time.time()
        self._cache[session_id] = result

        logger.debug(
            f"[PREFETCH] Cached for session {session_id} | "
            f"mem0={len(result.mem0_context)}c | "
            f"healing={len(result.healing_context)}c | "
            f"user_model={len(result.user_model_update)}c"
        )

    def consume(self, session_id: str) -> Optional[PrefetchResult]:
        """
        Consume the cached prefetch result for a session.
        Returns None if no cache or cache is stale.
        Removes the cache entry after consumption.
        """
        result = self._cache.pop(session_id, None)

        if result is None:
            return None

        if result.age_seconds > self.STALE_THRESHOLD_SECONDS:
            result.stale = True
            logger.debug(
                f"[PREFETCH] Stale cache for {session_id} "
                f"({result.age_seconds:.1f}s old)"
            )

        return result

    def discard(self, session_id: str) -> None:
        """Clean up when session ends."""
        self._cache.pop(session_id, None)
        task = self._pending.pop(session_id, None)
        if task and not task.done():
            task.cancel()

    async def _fetch_mem0(self, mem0, user_id, query, result):
        try:
            ctx = await mem0.get_context(user_id, query=query)
            result.mem0_context = ctx or ""
        except Exception as e:
            logger.warning(f"[PREFETCH] Mem0 failed: {e}")

    async def _fetch_healing(self, memory, conv_id, user_message, result):
        try:
            from mind.healing import HealingLoop
            healing = HealingLoop()
            recent = await memory.get_recent_messages(conv_id, limit=4)
            # Just check if there's a friction pattern building
            detection = healing.detect(user_message, None, recent)
            if detection.warning_text:
                result.healing_context = detection.warning_text
        except Exception as e:
            logger.warning(f"[PREFETCH] Healing prefetch failed: {e}")

    async def _fetch_user_model_update(self, user_modeling, user_id, message, result):
        try:
            update = await user_modeling.get_dynamic_context(user_id, message)
            result.user_model_update = update or ""
        except Exception as e:
            logger.warning(f"[PREFETCH] User model update failed: {e}")
