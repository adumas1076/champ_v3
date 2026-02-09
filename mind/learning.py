# ============================================
# CHAMP V3 — Learning Loop
# Brick 6: Runs at session end to extract
# preferences, lessons, and patterns from
# the conversation transcript via LLM analysis.
# ============================================

import json
import logging
from typing import Optional

import requests

from brain.config import Settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT_TEMPLATE = """\
You are analyzing a conversation transcript between a user (Anthony) and an AI assistant (Champ).
Your job is to extract learnings that should be remembered for future sessions.

Return ONLY valid JSON with exactly these fields:
{{
  "profile_updates": [
    {{"key": "string", "value": "string", "category": "string", "confidence": "high|medium|low"}}
  ],
  "lesson_matches": ["string snippets that match known patterns"],
  "new_lessons": [
    {{"lesson": "string", "tags": ["string"]}}
  ]
}}

Rules:
- profile_updates: User preferences, facts, or settings discovered (e.g., "preferred_editor": "VS Code")
- lesson_matches: Short phrases that echo known patterns (for incrementing existing lessons)
- new_lessons: New reusable patterns worth remembering (e.g., "User prefers brick-wall build approach")
- If nothing to extract, return empty arrays for all fields.
- Be selective — only extract things that would genuinely help in future sessions.
- Do NOT extract trivial or one-time things (e.g., "user asked about weather").

TRANSCRIPT:
{transcript}
"""


class LearningLoop:
    """
    Post-session learning extraction.

    Called when a session ends. Fetches the transcript,
    sends it to an LLM for analysis, and writes extracted
    learnings back to Supabase memory tables.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_url = f"{settings.litellm_base_url}/chat/completions"
        self.llm_api_key = settings.litellm_api_key
        self.default_model = settings.default_model

    async def capture(self, conversation_id: str, memory) -> None:
        """
        Main entry point. Called at session end.

        1. Fetch transcript
        2. Skip if too short
        3. Extract via LLM
        4. Write to memory tables
        """
        try:
            # 1. Fetch transcript
            messages = await memory.get_recent_messages(
                conversation_id, limit=50
            )

            # 2. Skip short conversations
            if len(messages) < 3:
                logger.info(
                    f"Learning skip: only {len(messages)} messages "
                    f"in {conversation_id}"
                )
                return

            # 3. Extract via LLM
            extraction = await self._extract(messages)
            if not extraction:
                return

            # 4. Write results
            profile_updates = extraction.get("profile_updates", [])
            lesson_matches = extraction.get("lesson_matches", [])
            new_lessons = extraction.get("new_lessons", [])

            if profile_updates:
                await self._write_profile_updates(memory, profile_updates)

            if lesson_matches:
                await self._match_existing_lessons(memory, lesson_matches)

            if new_lessons:
                await self._write_new_lessons(memory, new_lessons)

            logger.info(
                f"Learning captured for {conversation_id}: "
                f"{len(profile_updates)} profile, "
                f"{len(lesson_matches)} matches, "
                f"{len(new_lessons)} new lessons"
            )

        except Exception as e:
            logger.error(f"Learning capture failed (non-fatal): {e}")

    async def _extract(self, messages: list[dict]) -> Optional[dict]:
        """Send transcript to LLM for extraction. Returns parsed JSON."""
        transcript = self._format_transcript(messages)
        prompt = EXTRACTION_PROMPT_TEMPLATE.format(transcript=transcript)

        payload = {
            "model": self.default_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1000,
        }

        try:
            response = requests.post(
                self.llm_url,
                json=payload,
                headers={"Authorization": f"Bearer {self.llm_api_key}"},
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON from response (handle markdown code blocks)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]
            content = content.strip()

            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"Learning LLM returned invalid JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Learning LLM call failed: {e}")
            return None

    def _format_transcript(self, messages: list[dict]) -> str:
        """Format messages into readable transcript."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    async def _write_profile_updates(
        self, memory, updates: list[dict]
    ) -> None:
        """Upsert profile entries into mem_profile."""
        for entry in updates:
            try:
                await memory.upsert_profile(
                    user_id="anthony",
                    key=entry.get("key", ""),
                    value=entry.get("value", ""),
                    category=entry.get("category", "general"),
                    confidence=entry.get("confidence", "medium"),
                )
            except Exception as e:
                logger.error(f"Profile upsert failed for {entry}: {e}")

    async def _match_existing_lessons(
        self, memory, matches: list[str]
    ) -> None:
        """Increment times_seen for lessons matching these snippets."""
        for snippet in matches:
            try:
                await memory.increment_lesson(
                    user_id="anthony",
                    lesson_substring=snippet,
                )
            except Exception as e:
                logger.error(f"Lesson increment failed for '{snippet}': {e}")

    async def _write_new_lessons(
        self, memory, lessons: list[dict]
    ) -> None:
        """Insert new draft lessons into mem_lessons."""
        for lesson in lessons:
            try:
                await memory.insert_lesson(
                    user_id="anthony",
                    lesson=lesson.get("lesson", ""),
                    tags=lesson.get("tags", []),
                )
            except Exception as e:
                logger.error(f"New lesson insert failed for {lesson}: {e}")
