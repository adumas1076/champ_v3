# ============================================
# CHAMP V3 — Self Mode Models
# Brick 8: Data models for Goal Card, Result Pack,
# SubTask, and Run State.
# ============================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4


class RunStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    FIXING = "fixing"
    PACKAGING = "packaging"
    LEARNING = "learning"
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class SubTaskAction(str, Enum):
    LLM_GENERATE = "llm_generate"
    FILE_WRITE = "file_write"
    COMMAND_RUN = "command_run"
    BROWSER_ACTION = "browser_action"


class SubTaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class GoalCard:
    """Parsed Goal Card with 9 fields + metadata."""
    objective: str
    problem: str
    solution: str
    stack: str
    constraints: str
    approval: str
    deliverables: str
    context_assets: str
    success_checks: str
    # Metadata
    goal_id: str = ""
    project_id: str = ""
    priority: str = "P1"
    risk_level: str = "low"

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "project_id": self.project_id,
            "priority": self.priority,
            "risk_level": self.risk_level,
            "objective": self.objective,
            "problem": self.problem,
            "solution": self.solution,
            "stack": self.stack,
            "constraints": self.constraints,
            "approval": self.approval,
            "deliverables": self.deliverables,
            "context_assets": self.context_assets,
            "success_checks": self.success_checks,
        }

    def to_prompt(self) -> str:
        """Format as readable text for LLM prompts."""
        return (
            f"GOAL CARD ({self.goal_id})\n"
            f"1) OBJECTIVE: {self.objective}\n"
            f"2) PROBLEM: {self.problem}\n"
            f"3) SOLUTION: {self.solution}\n"
            f"4) STACK: {self.stack}\n"
            f"5) CONSTRAINTS: {self.constraints}\n"
            f"6) APPROVAL: {self.approval}\n"
            f"7) DELIVERABLES: {self.deliverables}\n"
            f"8) CONTEXT/ASSETS: {self.context_assets}\n"
            f"9) SUCCESS CHECKS: {self.success_checks}\n"
        )


@dataclass
class SubTask:
    """A single step in the execution plan."""
    id: str
    order: int
    description: str
    action: str
    params: dict = field(default_factory=dict)
    status: str = SubTaskStatus.PENDING.value
    output: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order": self.order,
            "description": self.description,
            "action": self.action,
            "params": self.params,
            "status": self.status,
            "output": self.output,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubTask":
        return cls(
            id=data.get("id", f"st-{uuid4().hex[:6]}"),
            order=data.get("order", 0),
            description=data.get("description", ""),
            action=data.get("action", "llm_generate"),
            params=data.get("params", {}),
            status=data.get("status", SubTaskStatus.PENDING.value),
            output=data.get("output", ""),
            error=data.get("error"),
        )


@dataclass
class ResultPack:
    """Output format — 7 fields + metadata."""
    goal_id: str
    project_id: str
    run_id: str
    status: str
    deliverables: str = ""
    decisions_made: str = ""
    issues_hit: str = ""
    next_actions: str = ""
    time_cost: str = ""
    evidence: str = ""

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "status": self.status,
            "deliverables": self.deliverables,
            "decisions_made": self.decisions_made,
            "issues_hit": self.issues_hit,
            "next_actions": self.next_actions,
            "time_cost": self.time_cost,
            "evidence": self.evidence,
        }

    def to_text(self) -> str:
        """Format as readable Result Pack."""
        return (
            f"RESULT PACK v1.0\n"
            f"(goal_id: {self.goal_id} | project_id: {self.project_id} | run_id: {self.run_id})\n\n"
            f"1) STATUS\n- {self.status}\n\n"
            f"2) DELIVERABLES\n{self.deliverables}\n\n"
            f"3) DECISIONS MADE\n{self.decisions_made}\n\n"
            f"4) ISSUES HIT\n{self.issues_hit}\n\n"
            f"5) NEXT ACTIONS\n{self.next_actions}\n\n"
            f"6) TIME + COST\n{self.time_cost}\n\n"
            f"7) EVIDENCE\n{self.evidence}\n"
        )
