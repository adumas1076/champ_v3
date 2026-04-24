"""
Cocreatiq Skill Engine — The system that makes skills alive.

Three systems harvested from Claude Code source (Dr. Frankenstein):
1. Skillify — auto-capture any session into a reusable skill
2. Skill Improvement — detect corrections during execution, auto-update SKILL.md
3. Skill Usage Tracking — count + recency ranking with 7-day half-life decay

Plus Cocreatiq-original:
4. Skill Change Detector — file watcher, hot-reloads skills when edited
5. Skill Auto-Detection — notices when a process repeats 3+ times, suggests skillify

Skills live in: .claude/skills/{name}/SKILL.md
Commands live in: .claude/commands/{name}.md
Engine lives in: content_engine/skills/

Skills are BORN from work (skillify), RAISED by corrections (improvement),
and PROVEN by results (DDO tracking). They self-improve automatically.
"""

from .skill_loader import load_skill, load_all_skills, get_skill_path
from .skill_usage_tracking import record_skill_usage, get_skill_usage_score