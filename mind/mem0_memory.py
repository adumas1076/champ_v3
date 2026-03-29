# ============================================
# CHAMP V3 — Mem0 Global Memory Layer
# Cross-operator shared memory using Mem0.
# Maps to AIOSP context scope: "global"
#
# Architecture:
#   Letta  = per-operator deep memory (self-editing blocks)
#   Mem0   = cross-operator shared memory (fast semantic search)
#   Supabase = persistent storage (full history, never compacted)
#
# Mem0 handles:
#   - User facts shared across ALL operators
#   - Business knowledge any operator can query
#   - Cross-session context that persists forever
#   - Semantic search across accumulated knowledge
# ============================================

import logging
from typing import Optional

from brain.config import Settings

logger = logging.getLogger(__name__)


class Mem0Memory:
    """
    Global shared memory layer using Mem0.

    Maps to AIOSP context scope "global" — all operators can read,
    only the OS (host) writes. In practice, any operator can add
    memories but they're shared across the entire system.

    Lifecycle:
    1. connect()     — initialize Mem0 with config
    2. add()         — store a memory (user-scoped or global)
    3. search()      — semantic search across memories
    4. get_all()     — retrieve all memories for a user
    5. get_context()  — formatted string for system prompt injection
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._memory = None
        self._available = False

    async def connect(self) -> bool:
        """
        Initialize Mem0. Returns True if available, False if not.
        Graceful degradation — Brain works without Mem0.
        """
        if not getattr(self.settings, "mem0_enabled", False):
            logger.info("[MEM0] Mem0 not enabled — running without global memory")
            return False

        try:
            from mem0 import Memory

            # Build config based on settings
            config = {}

            # Use custom LLM if specified (default: uses OpenAI)
            mem0_llm_provider = getattr(self.settings, "mem0_llm_provider", "")
            mem0_llm_model = getattr(self.settings, "mem0_llm_model", "")
            if mem0_llm_provider and mem0_llm_model:
                config["llm"] = {
                    "provider": mem0_llm_provider,
                    "config": {"model": mem0_llm_model},
                }

            # Use custom embedder if specified
            mem0_embedder_provider = getattr(self.settings, "mem0_embedder_provider", "")
            mem0_embedder_model = getattr(self.settings, "mem0_embedder_model", "")
            if mem0_embedder_provider and mem0_embedder_model:
                config["embedder"] = {
                    "provider": mem0_embedder_provider,
                    "config": {"model": mem0_embedder_model},
                }

            # Use custom vector store if specified (default: in-memory/SQLite)
            mem0_vector_store = getattr(self.settings, "mem0_vector_store", "")
            if mem0_vector_store:
                config["vector_store"] = {
                    "provider": mem0_vector_store,
                    "config": {
                        "collection_name": "cocreatiq_global",
                    },
                }

            if config:
                self._memory = Memory.from_config(config)
            else:
                self._memory = Memory()

            self._available = True
            logger.info("[MEM0] Global memory layer initialized")
            return True

        except Exception as e:
            logger.warning(f"[MEM0] Failed to initialize (running without Mem0): {e}")
            self._available = False
            return False

    @property
    def available(self) -> bool:
        return self._available

    async def add(
        self,
        text: str,
        user_id: str = "global",
        agent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Add a memory. Memories are deduplicated and updated automatically by Mem0.

        Args:
            text: The memory content (natural language)
            user_id: Scope — "global" for shared, or specific user ID
            agent_id: Which operator added this (for provenance)
            metadata: Additional metadata (source, timestamp, etc.)
        """
        if not self._available:
            return None

        try:
            kwargs = {"user_id": user_id}
            if agent_id:
                kwargs["agent_id"] = agent_id
            if metadata:
                kwargs["metadata"] = metadata

            result = self._memory.add(text, **kwargs)
            logger.debug(f"[MEM0] Added memory for user={user_id}: {text[:80]}...")
            return result

        except Exception as e:
            logger.error(f"[MEM0] Failed to add memory: {e}")
            return None

    async def search(
        self,
        query: str,
        user_id: str = "global",
        top_k: int = 5,
    ) -> list:
        """
        Semantic search across memories.

        Returns list of matching memories with relevance scores.
        """
        if not self._available:
            return []

        try:
            results = self._memory.search(query, user_id=user_id, limit=top_k)
            logger.debug(
                f"[MEM0] Search '{query[:50]}...' returned {len(results.get('results', []))} results"
            )
            return results.get("results", [])

        except Exception as e:
            logger.error(f"[MEM0] Search failed: {e}")
            return []

    async def get_all(self, user_id: str = "global") -> list:
        """Get all memories for a user/scope."""
        if not self._available:
            return []

        try:
            results = self._memory.get_all(user_id=user_id)
            return results.get("results", [])

        except Exception as e:
            logger.error(f"[MEM0] get_all failed: {e}")
            return []

    async def get_context(self, user_id: str, query: str = "") -> str:
        """
        Get formatted memory context for system prompt injection.

        If query is provided, returns semantically relevant memories.
        If no query, returns all memories for the user.
        """
        if not self._available:
            return ""

        try:
            if query:
                memories = await self.search(query, user_id=user_id, top_k=5)
            else:
                memories = await self.get_all(user_id=user_id)

            if not memories:
                return ""

            lines = ["[GLOBAL MEMORY]"]
            for mem in memories:
                memory_text = mem.get("memory", "")
                if memory_text:
                    lines.append(f"- {memory_text}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"[MEM0] get_context failed: {e}")
            return ""

    async def delete(self, memory_id: str) -> bool:
        """Delete a specific memory by ID."""
        if not self._available:
            return False

        try:
            self._memory.delete(memory_id)
            logger.debug(f"[MEM0] Deleted memory {memory_id}")
            return True
        except Exception as e:
            logger.error(f"[MEM0] Delete failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Cleanup."""
        self._memory = None
        self._available = False
        logger.info("[MEM0] Disconnected")
