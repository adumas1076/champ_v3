"""
Skill Self-Improvement — Detects user corrections during skill execution
and auto-updates SKILL.md.

Harvested from: Claude Code source (skillImprovement.ts)
Pattern: Every 5 user messages, a background LLM analyzes the conversation
for corrections/preferences. If found, rewrites the SKILL.md with
improvements baked in.

Our addition: Logs improvements to DDO (ddo_optimizations table) and
connects to mem_lessons for cross-skill pattern learning.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

logger = logging.getLogger("cocreatiq.skills.improvement")

# Analyze for improvements every N user messages
TURN_BATCH_SIZE = 5


@dataclass
class SkillUpdate:
    """A single improvement to apply to a skill."""
    section: str      # Which step/section to modify (or "new step")
    change: str       # What to add/modify
    reason: str       # Which user message prompted this


DETECTION_PROMPT = """You are analyzing a conversation where a user is executing a skill (a repeatable process).
Your job: identify if the user's recent messages contain preferences, requests, or corrections that should be permanently added to the skill definition for future runs.

<skill_definition>
{skill_content}
</skill_definition>

<recent_messages>
{recent_messages}
</recent_messages>

Look for:
- Requests to add, change, or remove steps: "can you also ask me X", "please do Y too", "don't do Z"
- Preferences about how steps should work: "ask me about energy levels", "note the time", "use a casual tone"
- Corrections: "no, do X instead", "always use Y", "make sure to..."
- Quality standards: "this isn't good enough", "needs to be more specific", "too verbose"

Ignore:
- Routine conversation that doesn't generalize (one-time answers, chitchat)
- Things the skill already does
- Context-specific details that won't apply to other runs

Output a JSON array inside <updates> tags.
Each item: {{"section": "which step/section to modify or 'new step'", "change": "what to add/modify", "reason": "which user message prompted this"}}.
Output <updates>[]</updates> if no updates are needed."""


APPLY_PROMPT = """You are editing a skill definition file. Apply the following improvements to the skill.

<current_skill_file>
{current_content}
</current_skill_file>

<improvements>
{update_list}
</improvements>

Rules:
- Integrate the improvements naturally into the existing structure
- Preserve frontmatter (--- block) exactly as-is
- Preserve the overall format and style
- Do not remove existing content unless an improvement explicitly replaces it
- Add new rules under the relevant step's **Rules**: section
- Add new steps in logical order
- Output the complete updated file inside <updated_file> tags"""


def detect_improvements(
    skill_content: str,
    recent_messages: list[str],
) -> list[SkillUpdate]:
    """Analyze recent messages for skill improvements.

    Harvested from Claude Code: skillImprovement.ts buildMessages()

    In production, this calls an LLM with the DETECTION_PROMPT.
    Returns list of SkillUpdate objects.

    Args:
        skill_content: The current SKILL.md content
        recent_messages: Recent user messages (last TURN_BATCH_SIZE)

    Returns:
        List of detected improvements (empty if none found)
    """
    if not recent_messages:
        return []

    # Format the prompt
    prompt = DETECTION_PROMPT.format(
        skill_content=skill_content,
        recent_messages="\n\n---\n\n".join(recent_messages),
    )

    # TODO: Call LLM (Haiku — fast + cheap) with this prompt
    # response = await query_model(prompt, model="haiku")
    # Parse <updates> tag from response
    # Return list of SkillUpdate objects

    logger.debug(f"[SKILL IMPROVEMENT] Would analyze {len(recent_messages)} messages")
    return []


def apply_improvements(
    skill_file_path: str,
    updates: list[SkillUpdate],
) -> bool:
    """Apply detected improvements to a SKILL.md file.

    Harvested from Claude Code: skillImprovement.ts applySkillImprovement()

    Reads current file, calls LLM to rewrite with improvements,
    saves updated file.

    Args:
        skill_file_path: Path to the SKILL.md file
        updates: List of improvements to apply

    Returns:
        True if file was updated, False otherwise
    """
    if not updates:
        return False

    path = Path(skill_file_path)
    if not path.exists():
        logger.error(f"Skill file not found: {skill_file_path}")
        return False

    current_content = path.read_text(encoding="utf-8")
    update_list = "\n".join(f"- {u.section}: {u.change}" for u in updates)

    # Format the apply prompt
    prompt = APPLY_PROMPT.format(
        current_content=current_content,
        update_list=update_list,
    )

    # TODO: Call LLM with this prompt
    # response = await query_model(prompt, model="haiku", temperature=0)
    # Extract <updated_file> tag
    # Write to file

    logger.info(
        f"[SKILL IMPROVEMENT] Would apply {len(updates)} updates to {skill_file_path}"
    )

    # TODO: Log to DDO
    # INSERT INTO ddo_optimizations (pattern_type, finding, action_taken, source)
    # VALUES ('skill_improvement', '{updates}', 'auto-updated SKILL.md', 'skill_improvement')

    return False  # Will return True once LLM wiring is in


class SkillImprovementTracker:
    """Tracks user messages during skill execution and triggers improvement detection.

    Harvested from Claude Code: createSkillImprovementHook()

    Usage:
        tracker = SkillImprovementTracker(skill_content, skill_file_path)

        # During skill execution, feed user messages:
        tracker.add_user_message("no, do X instead")
        tracker.add_user_message("also ask about Y")

        # Every TURN_BATCH_SIZE messages, check for improvements:
        updates = tracker.check_for_improvements()
        if updates:
            tracker.apply(updates)
    """

    def __init__(self, skill_content: str, skill_file_path: str):
        self.skill_content = skill_content
        self.skill_file_path = skill_file_path
        self._messages: list[str] = []
        self._last_analyzed_count = 0

    def add_user_message(self, message: str) -> None:
        """Add a user message to the tracking buffer."""
        if message.strip():
            self._messages.append(message)

    def should_check(self) -> bool:
        """Whether enough messages have accumulated to check for improvements."""
        return len(self._messages) - self._last_analyzed_count >= TURN_BATCH_SIZE

    def check_for_improvements(self) -> list[SkillUpdate]:
        """Check recent messages for skill improvements.

        Only analyzes messages since last check.
        """
        if not self.should_check():
            return []

        recent = self._messages[self._last_analyzed_count:]
        self._last_analyzed_count = len(self._messages)

        return detect_improvements(self.skill_content, recent)

    def apply(self, updates: list[SkillUpdate]) -> bool:
        """Apply detected improvements to the skill file."""
        success = apply_improvements(self.skill_file_path, updates)
        if success:
            # Reload skill content after update
            self.skill_content = Path(self.skill_file_path).read_text(encoding="utf-8")
        return success
