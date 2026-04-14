# ============================================
# CHAMP V3 — Skill Creation Engine
# Harvested from: Hermes Agent (NousResearch)
#
# After complex tasks, operators autonomously
# create reusable "skills" — named procedures
# that can be recalled and improved over time.
#
# Skill lifecycle:
#   1. Task completed → skill extraction (LLM)
#   2. Skill stored with name, steps, context
#   3. Next time similar task → skill recalled
#   4. After execution → skill refined (self-improvement)
#
# Skills are per-operator (Sales learns sales skills,
# Content learns content skills) but can be shared.
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


@dataclass
class Skill:
    """A reusable procedure learned from experience."""
    id: str
    name: str               # e.g. "cold_outreach_email"
    description: str         # What this skill does
    steps: list[str]         # Ordered procedure steps
    trigger_patterns: list[str]  # When to suggest this skill
    operator_name: str       # Which operator learned it
    times_used: int = 0
    times_improved: int = 0
    effectiveness: float = 0.5  # 0.0 - 1.0, updated after use
    status: str = "draft"    # draft → active → proven → archived
    created_at: str = ""
    updated_at: str = ""


EXTRACTION_PROMPT = """\
You are analyzing a conversation where an AI operator completed a complex task.
Your job is to extract a reusable SKILL — a named procedure that could be
applied next time a similar task comes up.

OPERATOR: {operator_name}
TRANSCRIPT:
{transcript}

Return ONLY valid JSON:
{{
  "should_create_skill": true/false,
  "skill": {{
    "name": "snake_case_skill_name",
    "description": "One-line description of what this skill does",
    "steps": ["Step 1: ...", "Step 2: ...", "Step 3: ..."],
    "trigger_patterns": ["when user asks to...", "when task involves..."]
  }}
}}

Rules:
- Only create a skill if the task was COMPLEX (3+ steps) and REUSABLE
- Don't create skills for trivial tasks (greetings, simple Q&A)
- Steps should be specific enough to follow but general enough to reuse
- Trigger patterns should describe WHEN to use this skill
- Return {{"should_create_skill": false}} if nothing worth saving"""


IMPROVEMENT_PROMPT = """\
A skill was just used in a conversation. Based on how it went,
suggest improvements to make the skill better next time.

SKILL NAME: {skill_name}
CURRENT STEPS:
{current_steps}

USAGE TRANSCRIPT:
{transcript}

Return ONLY valid JSON:
{{
  "should_improve": true/false,
  "improved_steps": ["Step 1: ...", "Step 2: ..."],
  "effectiveness_delta": -0.1 to 0.1,
  "reason": "Why the change"
}}

Rules:
- Only improve if there's a clear lesson from this usage
- Keep step count similar (don't bloat the skill)
- effectiveness_delta: positive if it went well, negative if not
- Return {{"should_improve": false}} if the skill worked fine as-is"""


class SkillEngine:
    """
    Autonomous skill creation and self-improvement.

    Integrates with the learning loop:
    - LearningLoop.capture() extracts profile/lessons (existing)
    - SkillEngine.extract() creates reusable procedures (new)

    Skills are stored in Supabase and recalled when
    similar tasks arise (via trigger pattern matching).
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self.llm_url = f"{settings.litellm_base_url}/chat/completions"
        self.llm_api_key = settings.litellm_api_key

    async def connect(self) -> bool:
        if not self.settings.supabase_url or not self.settings.supabase_service_key:
            logger.info("[SKILLS] No Supabase — skill engine disabled")
            return False
        try:
            from supabase._async.client import create_client as create_async_client
            self._client = await create_async_client(
                self.settings.supabase_url,
                self.settings.supabase_service_key,
            )
            logger.info("[SKILLS] Connected")
            return True
        except Exception as e:
            logger.warning(f"[SKILLS] Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        self._client = None

    # ---- Skill Extraction (post-session) ----

    async def extract(
        self,
        operator_name: str,
        transcript: str,
        user_id: str = "anthony",
    ) -> Optional[Skill]:
        """
        Analyze a session transcript and extract a skill if warranted.
        Called at session end alongside LearningLoop.capture().
        """
        if not self._client:
            return None

        # Skip short transcripts
        if len(transcript) < 500:
            return None

        prompt = EXTRACTION_PROMPT.format(
            operator_name=operator_name,
            transcript=transcript[:4000],  # Cap to avoid token overflow
        )

        try:
            response = requests.post(
                self.llm_url,
                json={
                    "model": self.settings.default_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 800,
                },
                headers={"Authorization": f"Bearer {self.llm_api_key}"},
                timeout=30,
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            data = json.loads(content)

            if not data.get("should_create_skill"):
                logger.debug(f"[SKILLS] No skill warranted for {operator_name}")
                return None

            skill_data = data["skill"]

            # Check for duplicate skills
            existing = await self._find_similar_skill(
                operator_name, skill_data["name"]
            )
            if existing:
                logger.info(
                    f"[SKILLS] Similar skill already exists: {existing['name']}"
                )
                return None

            # Create the skill
            skill = Skill(
                id=str(uuid4()),
                name=skill_data["name"],
                description=skill_data["description"],
                steps=skill_data["steps"],
                trigger_patterns=skill_data.get("trigger_patterns", []),
                operator_name=operator_name,
                status="draft",
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

            await self._store_skill(skill)
            logger.info(
                f"[SKILLS] Created: {skill.name} for {operator_name} "
                f"({len(skill.steps)} steps)"
            )
            return skill

        except Exception as e:
            logger.error(f"[SKILLS] Extraction failed (non-fatal): {e}")
            return None

    # ---- Skill Recall (pre-turn) ----

    async def recall(
        self, operator_name: str, user_message: str
    ) -> list[Skill]:
        """
        Find skills that match the current user message.
        Returns relevant skills ordered by effectiveness.
        """
        if not self._client:
            return []

        try:
            # Fetch active/proven skills for this operator
            result = await self._client.table("operator_skills").select("*").eq(
                "operator_name", operator_name
            ).in_(
                "status", ["active", "proven"]
            ).execute()

            if not result.data:
                return []

            # Match trigger patterns against user message
            message_lower = user_message.lower()
            matched = []

            for row in result.data:
                triggers = row.get("trigger_patterns", [])
                for trigger in triggers:
                    if any(
                        word in message_lower
                        for word in trigger.lower().split()
                        if len(word) > 3
                    ):
                        matched.append(self._row_to_skill(row))
                        break

            # Sort by effectiveness (proven skills first)
            matched.sort(key=lambda s: s.effectiveness, reverse=True)
            return matched[:3]  # Max 3 suggestions per turn

        except Exception as e:
            logger.error(f"[SKILLS] Recall failed: {e}")
            return []

    def format_skills_for_prompt(self, skills: list[Skill]) -> str:
        """Format recalled skills as a system prompt section."""
        if not skills:
            return ""

        lines = ["[AVAILABLE SKILLS]"]
        for skill in skills:
            lines.append(f"\n📋 {skill.name} — {skill.description}")
            lines.append(f"   Effectiveness: {skill.effectiveness:.0%} | Used {skill.times_used}x")
            for i, step in enumerate(skill.steps, 1):
                lines.append(f"   {i}. {step}")

        return "\n".join(lines)

    # ---- Skill Improvement (post-use) ----

    async def improve(
        self, skill: Skill, usage_transcript: str
    ) -> bool:
        """
        Self-improve a skill based on how it was just used.
        Called when a skill was recalled and the session is ending.
        """
        if not self._client:
            return False

        prompt = IMPROVEMENT_PROMPT.format(
            skill_name=skill.name,
            current_steps="\n".join(
                f"{i+1}. {s}" for i, s in enumerate(skill.steps)
            ),
            transcript=usage_transcript[:3000],
        )

        try:
            response = requests.post(
                self.llm_url,
                json={
                    "model": "gemini-flash",  # Cheap model for improvement
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 600,
                },
                headers={"Authorization": f"Bearer {self.llm_api_key}"},
                timeout=20,
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            data = json.loads(content)

            # Always increment usage count
            new_times_used = skill.times_used + 1
            effectiveness_delta = float(data.get("effectiveness_delta", 0))
            new_effectiveness = max(0.0, min(1.0, skill.effectiveness + effectiveness_delta))

            update = {
                "times_used": new_times_used,
                "effectiveness": new_effectiveness,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if data.get("should_improve") and data.get("improved_steps"):
                update["steps"] = data["improved_steps"]
                update["times_improved"] = skill.times_improved + 1
                logger.info(
                    f"[SKILLS] Improved: {skill.name} | "
                    f"reason: {data.get('reason', 'n/a')}"
                )

            # Auto-promote: draft → active after 1 use, active → proven after 3
            if skill.status == "draft" and new_times_used >= 1:
                update["status"] = "active"
            elif skill.status == "active" and new_times_used >= 3 and new_effectiveness >= 0.6:
                update["status"] = "proven"

            await self._client.table("operator_skills").update(
                update
            ).eq("id", skill.id).execute()

            return True

        except Exception as e:
            logger.error(f"[SKILLS] Improvement failed: {e}")
            return False

    # ---- Storage ----

    async def _store_skill(self, skill: Skill) -> None:
        if not self._client:
            return
        await self._client.table("operator_skills").insert({
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "steps": skill.steps,
            "trigger_patterns": skill.trigger_patterns,
            "operator_name": skill.operator_name,
            "times_used": skill.times_used,
            "times_improved": skill.times_improved,
            "effectiveness": skill.effectiveness,
            "status": skill.status,
            "created_at": skill.created_at,
            "updated_at": skill.updated_at,
        }).execute()

    async def _find_similar_skill(
        self, operator_name: str, skill_name: str
    ) -> Optional[dict]:
        if not self._client:
            return None
        try:
            result = await self._client.table("operator_skills").select(
                "name"
            ).eq("operator_name", operator_name).eq(
                "name", skill_name
            ).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    def _row_to_skill(self, row: dict) -> Skill:
        return Skill(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            steps=row.get("steps", []),
            trigger_patterns=row.get("trigger_patterns", []),
            operator_name=row.get("operator_name", ""),
            times_used=row.get("times_used", 0),
            times_improved=row.get("times_improved", 0),
            effectiveness=row.get("effectiveness", 0.5),
            status=row.get("status", "draft"),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )
