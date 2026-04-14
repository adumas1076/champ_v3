# ============================================
# CHAMP V3 — Dual-Peer User Modeling
# Harvested from: Hermes Agent (NousResearch)
# Inspired by: Honcho dialectic framework
#
# Two "peers" observe every conversation:
#   1. USER PEER — builds a model of who the user is
#   2. AI PEER   — builds a model of who the operator is
#
# Both evolve over time through observation.
# The user model helps operators understand Anthony
# (and future users) deeply. The AI model helps
# operators develop authentic identity over sessions.
#
# Stored in Supabase. No external Honcho dependency.
# ============================================

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import requests

from brain.config import Settings

logger = logging.getLogger(__name__)

# Dynamic reasoning levels — scale effort with message complexity
REASONING_LEVELS = {
    "minimal": "Extract only explicit facts. No inference.",
    "low": "Extract facts and simple preferences.",
    "medium": "Extract facts, preferences, and communication patterns.",
    "high": "Deep analysis: motivations, thinking style, decision patterns, emotional state.",
}


@dataclass
class PeerObservation:
    """A single observation from a peer about a conversation turn."""
    peer_type: str       # "user" or "ai"
    observation: str     # The extracted insight
    confidence: float    # 0.0 - 1.0
    category: str        # "fact", "preference", "pattern", "identity", "style"
    timestamp: str = ""


class UserModeling:
    """
    Dual-peer user modeling system.

    The user peer builds understanding of:
    - Communication style (formal/casual, verbose/terse)
    - Decision patterns (data-driven, intuition-based, etc.)
    - Domain expertise (what they know, what's new to them)
    - Emotional patterns (frustration triggers, energy states)
    - Preferences (tools, formats, workflows)

    The AI peer builds self-understanding of:
    - Which responses landed well
    - Which approaches the user rejected
    - What persona traits feel authentic vs forced
    - How the operator's voice evolves
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self.llm_url = f"{settings.litellm_base_url}/chat/completions"
        self.llm_api_key = settings.litellm_api_key

    async def connect(self) -> bool:
        """Initialize Supabase client for user modeling storage."""
        if not self.settings.supabase_url or not self.settings.supabase_service_key:
            logger.info("[USER_MODEL] No Supabase — user modeling disabled")
            return False

        try:
            from supabase._async.client import create_client as create_async_client
            self._client = await create_async_client(
                self.settings.supabase_url,
                self.settings.supabase_service_key,
            )
            logger.info("[USER_MODEL] Connected")
            return True
        except Exception as e:
            logger.warning(f"[USER_MODEL] Connection failed (non-fatal): {e}")
            return False

    async def disconnect(self) -> None:
        self._client = None

    # ---- Observation (called after each turn) ----

    async def observe(
        self,
        user_id: str,
        operator_name: str,
        user_message: str,
        assistant_response: str,
        session_id: str = "",
    ) -> None:
        """
        Observe a conversation turn and update both peer models.
        Called asynchronously after each response (non-blocking).

        Uses dynamic reasoning: short messages get minimal analysis,
        longer/complex messages get deeper analysis.
        """
        if not self._client:
            return

        # Determine reasoning level based on message complexity
        level = self._select_reasoning_level(user_message)

        try:
            observations = await self._extract_observations(
                user_id, operator_name, user_message,
                assistant_response, level,
            )

            if observations:
                await self._store_observations(user_id, operator_name, observations)
                await self._update_representations(user_id, operator_name)

        except Exception as e:
            logger.error(f"[USER_MODEL] Observation failed (non-fatal): {e}")

    def _select_reasoning_level(self, message: str) -> str:
        """Scale reasoning effort with message complexity."""
        length = len(message)
        if length < 80:
            return "minimal"
        elif length < 200:
            return "low"
        elif length < 500:
            return "medium"
        else:
            return "high"

    async def _extract_observations(
        self,
        user_id: str,
        operator_name: str,
        user_message: str,
        assistant_response: str,
        level: str,
    ) -> list[PeerObservation]:
        """Use LLM to extract observations from a conversation turn."""
        level_instruction = REASONING_LEVELS.get(level, REASONING_LEVELS["low"])

        prompt = f"""\
Analyze this conversation turn between a user and an AI operator.
Extract observations about BOTH the user and the AI.

Reasoning level: {level} — {level_instruction}

USER MESSAGE:
{user_message}

AI RESPONSE:
{assistant_response[:1000]}

Return ONLY valid JSON array:
[
  {{
    "peer_type": "user|ai",
    "observation": "what you noticed",
    "confidence": 0.0-1.0,
    "category": "fact|preference|pattern|identity|style"
  }}
]

Rules:
- For "user" peer: what does this reveal about the user?
- For "ai" peer: what does this reveal about how the AI is performing?
- Skip trivial observations. Only extract what's useful for future turns.
- At "minimal" level, return 0-1 observations. At "high", return 2-4.
- Return [] if nothing notable."""

        try:
            response = requests.post(
                self.llm_url,
                json={
                    "model": "gemini-flash",  # Cheap model for observation
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 500,
                },
                headers={"Authorization": f"Bearer {self.llm_api_key}"},
                timeout=15,
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            raw = json.loads(content)
            return [
                PeerObservation(
                    peer_type=obs["peer_type"],
                    observation=obs["observation"],
                    confidence=float(obs.get("confidence", 0.5)),
                    category=obs.get("category", "pattern"),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                for obs in raw
                if obs.get("peer_type") in ("user", "ai")
            ]

        except Exception as e:
            logger.warning(f"[USER_MODEL] Extraction failed: {e}")
            return []

    async def _store_observations(
        self, user_id: str, operator_name: str, observations: list[PeerObservation]
    ) -> None:
        """Store observations in Supabase."""
        if not self._client:
            return

        for obs in observations:
            try:
                await self._client.table("user_model_observations").insert({
                    "id": str(uuid4()),
                    "user_id": user_id,
                    "operator_name": operator_name,
                    "peer_type": obs.peer_type,
                    "observation": obs.observation,
                    "confidence": obs.confidence,
                    "category": obs.category,
                    "created_at": obs.timestamp or datetime.now(timezone.utc).isoformat(),
                }).execute()
            except Exception as e:
                logger.error(f"[USER_MODEL] Store failed: {e}")

    async def _update_representations(
        self, user_id: str, operator_name: str
    ) -> None:
        """
        Rebuild the user and AI representations from observations.
        Called after new observations are stored.

        Representations are compact summaries (< 600 chars each)
        suitable for system prompt injection.
        """
        if not self._client:
            return

        for peer_type in ("user", "ai"):
            try:
                # Fetch recent observations (last 50)
                result = await self._client.table("user_model_observations").select(
                    "observation, confidence, category"
                ).eq("user_id", user_id).eq(
                    "peer_type", peer_type
                ).order(
                    "created_at", desc=True
                ).limit(50).execute()

                if not result.data:
                    continue

                # Build representation from observations
                representation = self._synthesize_representation(
                    peer_type, result.data
                )

                # Upsert representation
                await self._client.table("user_model_representations").upsert(
                    {
                        "user_id": user_id,
                        "operator_name": operator_name,
                        "peer_type": peer_type,
                        "representation": representation,
                        "observation_count": len(result.data),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    on_conflict="user_id,operator_name,peer_type",
                ).execute()

            except Exception as e:
                logger.error(f"[USER_MODEL] Representation update failed: {e}")

    def _synthesize_representation(
        self, peer_type: str, observations: list[dict]
    ) -> str:
        """
        Build a compact representation from observations.
        Groups by category, keeps high-confidence observations.
        Target: < 600 chars for prompt injection.
        """
        by_category: dict[str, list[str]] = {}
        for obs in observations:
            cat = obs.get("category", "pattern")
            conf = obs.get("confidence", 0.5)
            if conf < 0.3:
                continue  # Skip low-confidence
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(obs["observation"])

        lines = []
        for cat, items in by_category.items():
            # Deduplicate similar observations (keep unique-ish ones)
            unique = list(dict.fromkeys(items))[:5]  # Max 5 per category
            for item in unique:
                lines.append(f"- [{cat}] {item}")

        # Truncate to ~600 chars
        result = "\n".join(lines)
        if len(result) > 600:
            result = result[:597] + "..."

        return result

    # ---- Retrieval (for snapshot and prefetch) ----

    async def get_user_representation(self, user_id: str) -> str:
        """Get the current user peer representation."""
        return await self._get_representation(user_id, "user")

    async def get_ai_representation(self, user_id: str) -> str:
        """Get the current AI peer representation."""
        return await self._get_representation(user_id, "ai")

    async def _get_representation(self, user_id: str, peer_type: str) -> str:
        if not self._client:
            return ""
        try:
            result = await self._client.table("user_model_representations").select(
                "representation"
            ).eq("user_id", user_id).eq("peer_type", peer_type).limit(1).execute()

            if result.data:
                return result.data[0].get("representation", "")
            return ""
        except Exception as e:
            logger.error(f"[USER_MODEL] Get representation failed: {e}")
            return ""

    async def get_dynamic_context(self, user_id: str, message: str) -> str:
        """
        Get dynamic context based on current message.
        Used by the prefetcher for query-specific context.
        """
        # For now, return the latest user representation
        # Future: semantic search over observations matching the message
        return await self.get_user_representation(user_id)
