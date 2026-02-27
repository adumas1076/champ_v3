# ============================================
# CHAMP V3 — Goal Card Parser
# Brick 8: Validates and parses Goal Card text
# into structured GoalCard objects.
# ============================================

import logging
import re

from self_mode.models import GoalCard

logger = logging.getLogger(__name__)

# Field labels that must appear in a valid Goal Card
FIELD_LABELS = [
    ("objective", r"1\)\s*OBJECTIVE"),
    ("problem", r"2\)\s*PROBLEM"),
    ("solution", r"3\)\s*SOLUTION"),
    ("stack", r"4\)\s*STACK"),
    ("constraints", r"5\)\s*CONSTRAINTS"),
    ("approval", r"6\)\s*APPROVAL"),
    ("deliverables", r"7\)\s*DELIVERABLES"),
    ("context_assets", r"8\)\s*CONTEXT\s*/?\s*ASSETS"),
    ("success_checks", r"9\)\s*SUCCESS\s*CHECKS"),
]

METADATA_PATTERN = re.compile(
    r"goal_id:\s*(?P<goal_id>[\w\-]+)"
    r".*?project_id:\s*(?P<project_id>[\w\-]+)"
    r"(?:.*?priority:\s*(?P<priority>P\d))?"
    r"(?:.*?risk_level:\s*(?P<risk_level>\w+))?",
    re.IGNORECASE | re.DOTALL,
)


class GoalCardParser:
    """Parses raw Goal Card text into a validated GoalCard object."""

    @staticmethod
    def parse(text: str) -> GoalCard:
        """
        Parse a Goal Card from text.

        Raises ValueError if required fields are missing or empty.
        """
        if not text or not text.strip():
            raise ValueError("Goal Card text is empty")

        # Extract metadata from header
        metadata = GoalCardParser._extract_metadata(text)

        # Extract each numbered field
        fields = GoalCardParser._extract_fields(text)

        # Validate all 9 fields present
        missing = [name for name, _ in FIELD_LABELS if name not in fields]
        if missing:
            raise ValueError(f"Goal Card missing fields: {', '.join(missing)}")

        # Validate no empty fields
        empty = [name for name in fields if not fields[name].strip()]
        if empty:
            raise ValueError(f"Goal Card has empty fields: {', '.join(empty)}")

        return GoalCard(
            objective=fields["objective"].strip(),
            problem=fields["problem"].strip(),
            solution=fields["solution"].strip(),
            stack=fields["stack"].strip(),
            constraints=fields["constraints"].strip(),
            approval=fields["approval"].strip(),
            deliverables=fields["deliverables"].strip(),
            context_assets=fields["context_assets"].strip(),
            success_checks=fields["success_checks"].strip(),
            goal_id=metadata.get("goal_id", ""),
            project_id=metadata.get("project_id", ""),
            priority=metadata.get("priority", "P1"),
            risk_level=metadata.get("risk_level", "low"),
        )

    @staticmethod
    def _extract_metadata(text: str) -> dict:
        """Extract goal_id, project_id, priority, risk_level from header."""
        match = METADATA_PATTERN.search(text)
        if not match:
            return {}
        result = {}
        for key in ("goal_id", "project_id", "priority", "risk_level"):
            val = match.group(key)
            if val:
                result[key] = val
        return result

    @staticmethod
    def _extract_fields(text: str) -> dict:
        """Extract the 9 numbered fields from Goal Card text."""
        fields = {}
        patterns = [
            (name, re.compile(regex, re.IGNORECASE))
            for name, regex in FIELD_LABELS
        ]

        # Find start positions of each field
        positions = []
        for name, pattern in patterns:
            match = pattern.search(text)
            if match:
                positions.append((name, match.end()))

        # Sort by position in text
        positions.sort(key=lambda x: x[1])

        # Extract content between consecutive field labels
        for i, (name, start) in enumerate(positions):
            if i + 1 < len(positions):
                next_name, _ = positions[i + 1]
                # Find start of next field label to use as boundary
                next_pattern = [p for n, p in patterns if n == next_name][0]
                next_match = next_pattern.search(text)
                end = next_match.start() if next_match else len(text)
            else:
                end = len(text)

            content = text[start:end].strip()
            # Remove leading dash, colon, or em-dash
            content = re.sub(r"^[\s:—\-]*", "", content)
            fields[name] = content

        return fields

    @staticmethod
    def validate(goal_card: GoalCard) -> list[str]:
        """Return list of validation warnings (empty = valid)."""
        warnings = []
        if not goal_card.goal_id:
            warnings.append("Missing goal_id — will be auto-generated")
        if not goal_card.project_id:
            warnings.append("Missing project_id — will default to 'champ_v3'")
        if len(goal_card.objective) < 10:
            warnings.append("Objective seems too short")
        if len(goal_card.success_checks) < 10:
            warnings.append("Success checks seem too brief")
        return warnings
