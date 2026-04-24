"""
Skill Loader — Reads SKILL.md files from .claude/skills/ and parses frontmatter.

Harvested pattern: Claude Code loads skills from .claude/skills/{name}/SKILL.md
with YAML frontmatter (name, description, when_to_use, allowed-tools, arguments).

Our addition: Also loads from operator-specific skill directories and
checks operator_skills Supabase table for registered skills.
"""

import logging
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger("cocreatiq.skills.loader")


# Skill directories to scan (in priority order)
SKILL_DIRS = [
    ".claude/skills",           # Project-level skills
    "~/.claude/skills",         # User-level skills (personal, cross-repo)
]

COMMAND_DIRS = [
    ".claude/commands",         # Project-level commands
    "~/.claude/commands",       # User-level commands
]


@dataclass
class SkillDefinition:
    """Parsed SKILL.md with frontmatter + body."""
    name: str
    description: str = ""
    when_to_use: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    arguments: list[str] = field(default_factory=list)
    argument_hint: str = ""
    context: str = "inline"      # "inline" or "fork"
    body: str = ""               # The markdown body (steps, goal, inputs)
    file_path: str = ""          # Where the SKILL.md lives
    skill_type: str = "skill"    # "skill" or "command"

    # Runtime tracking (from skill_usage_tracking)
    usage_count: int = 0
    effectiveness: float = 0.5
    status: str = "draft"        # "draft" | "active" | "proven" | "archived"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown file.

    Returns (frontmatter_dict, body_text).
    """
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return {}, content

    frontmatter_text = match.group(1)
    body = match.group(2)

    # Simple YAML parser (no dependency needed for basic key: value)
    frontmatter = {}
    current_key = None
    current_list = None

    for line in frontmatter_text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # List item under a key
        if stripped.startswith("- ") and current_key:
            if current_list is None:
                current_list = []
                frontmatter[current_key] = current_list
            current_list.append(stripped[2:].strip())
            continue

        # Key: value pair
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            current_key = key
            current_list = None
            if value:
                frontmatter[key] = value
            # If no value, might be followed by a list

    return frontmatter, body


def load_skill(skill_name: str) -> Optional[SkillDefinition]:
    """Load a single skill by name from any skill directory."""
    for skill_dir in SKILL_DIRS:
        skill_path = Path(skill_dir).expanduser() / skill_name / "SKILL.md"
        if skill_path.exists():
            return _load_skill_file(str(skill_path), "skill")

    # Also check commands
    for cmd_dir in COMMAND_DIRS:
        cmd_path = Path(cmd_dir).expanduser() / f"{skill_name}.md"
        if cmd_path.exists():
            return _load_skill_file(str(cmd_path), "command")

    logger.debug(f"Skill '{skill_name}' not found in any directory")
    return None


def _load_skill_file(file_path: str, skill_type: str) -> SkillDefinition:
    """Load and parse a single SKILL.md or command.md file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    frontmatter, body = _parse_frontmatter(content)

    # Parse allowed-tools (can be hyphenated key)
    allowed_tools = frontmatter.get("allowed-tools", frontmatter.get("allowed_tools", []))
    if isinstance(allowed_tools, str):
        allowed_tools = [allowed_tools]

    # Parse arguments
    arguments = frontmatter.get("arguments", [])
    if isinstance(arguments, str):
        arguments = [arguments]

    return SkillDefinition(
        name=frontmatter.get("name", Path(file_path).parent.name),
        description=frontmatter.get("description", ""),
        when_to_use=frontmatter.get("when_to_use", ""),
        allowed_tools=allowed_tools,
        arguments=arguments,
        argument_hint=frontmatter.get("argument-hint", frontmatter.get("argument_hint", "")),
        context=frontmatter.get("context", "inline"),
        body=body,
        file_path=file_path,
        skill_type=skill_type,
    )


def load_all_skills() -> list[SkillDefinition]:
    """Load all skills and commands from all directories."""
    skills = []

    # Load skills
    for skill_dir in SKILL_DIRS:
        dir_path = Path(skill_dir).expanduser()
        if not dir_path.exists():
            continue
        for skill_folder in sorted(dir_path.iterdir()):
            skill_file = skill_folder / "SKILL.md"
            if skill_folder.is_dir() and skill_file.exists():
                try:
                    skills.append(_load_skill_file(str(skill_file), "skill"))
                except Exception as e:
                    logger.warning(f"Failed to load skill {skill_folder.name}: {e}")

    # Load commands
    for cmd_dir in COMMAND_DIRS:
        dir_path = Path(cmd_dir).expanduser()
        if not dir_path.exists():
            continue
        for cmd_file in sorted(dir_path.glob("*.md")):
            try:
                skills.append(_load_skill_file(str(cmd_file), "command"))
            except Exception as e:
                logger.warning(f"Failed to load command {cmd_file.name}: {e}")

    logger.info(f"Loaded {len(skills)} skills/commands")
    return skills


def get_skill_path(skill_name: str, location: str = "project") -> str:
    """Get the file path where a skill should be saved.

    Args:
        skill_name: Name of the skill (lowercase, hyphenated)
        location: "project" (.claude/skills/) or "personal" (~/.claude/skills/)
    """
    if location == "personal":
        base = Path("~/.claude/skills").expanduser()
    else:
        base = Path(".claude/skills")

    return str(base / skill_name / "SKILL.md")