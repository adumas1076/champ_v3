# ============================================
# CHAMP V3 — Self Mode Engine
# Brick 8: Autonomous execution loop.
# Receives Goal Card → Plans → Executes →
# Reviews → Fixes → Packages → Learns → Delivers
# ============================================

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

import requests

from brain.config import Settings
from hands.router import (
    browse as hands_browse,
    browser_screenshot as hands_screenshot,
    fill_form as hands_fill_form,
)
from self_mode.models import (
    GoalCard,
    ResultPack,
    RunStatus,
    SubTask,
    SubTaskAction,
    SubTaskStatus,
)
from self_mode.parser import GoalCardParser
from self_mode.safety import SafetyRails

logger = logging.getLogger(__name__)

# Step indices for state persistence
STEPS = {
    "receive": 0,
    "plan": 1,
    "approve": 2,
    "execute": 3,
    "review": 4,
    "fix": 5,
    "package": 6,
    "learn": 7,
    "deliver": 8,
}

MAX_FIX_RETRIES = 3

PLANNING_PROMPT = """\
You are Champ's Self Mode planner. Given a Goal Card, break it into ordered subtasks.

Each subtask must be one of these actions:
- "llm_generate": Use LLM to generate content (code, text, config). \
Params: {{"prompt": "detailed instructions for what to generate", "output_file": "filename.ext"}}
- "file_write": Write literal content to a file. \
Params: {{"file_path": "filename.ext", "content": "the literal content"}}
- "command_run": Run a shell command. \
Params: {{"command": "the command to run"}}
- "browser_action": Browse a URL, take a screenshot, or fill a web form. \
Params: {{"browser_command": "browse|screenshot|fill_form", "url": "https://...", \
"fields": [{{"selector": "css selector", "value": "text to type"}}], "submit_selector": "css selector"}}

Return ONLY valid JSON — an array of subtask objects:
[
  {{
    "id": "st-001",
    "order": 1,
    "description": "What this step does",
    "action": "llm_generate",
    "params": {{...}}
  }}
]

Rules:
- Keep it minimal — fewest steps to achieve the objective
- Respect constraints from the Goal Card
- For code generation, include detailed requirements in params.prompt
- Platform is Windows — use python (not python3), use appropriate commands
- Order matters — later steps can depend on earlier outputs
- Include a verification step if the goal has testable outputs

GOAL CARD:
{goal_card}"""

REVIEW_PROMPT = """\
You are Champ's Self Mode reviewer. Check if the execution results satisfy the success checks.

GOAL CARD SUCCESS CHECKS:
{success_checks}

EXECUTION RESULTS:
{execution_results}

Return ONLY valid JSON:
{{
  "passed": true or false,
  "checks": [
    {{"check": "description of what was checked", "passed": true or false, "detail": "evidence"}}
  ],
  "summary": "Overall assessment in one sentence"
}}"""

FIX_PROMPT = """\
You are Champ's Self Mode fixer. The review found failures. Generate fix subtasks.

ORIGINAL GOAL CARD:
{goal_card}

FAILED CHECKS:
{failed_checks}

PREVIOUS EXECUTION RESULTS:
{execution_results}

Return ONLY valid JSON -- an array of fix subtasks (same format as planning):
[
  {{
    "id": "fix-001",
    "order": 1,
    "description": "What to fix",
    "action": "llm_generate|file_write|command_run|browser_action",
    "params": {{...}}
  }}
]

Focus only on what failed. Don't redo things that passed."""


class SelfModeEngine:
    """
    Autonomous execution engine.

    Loop: Receive → Plan → Approve → Execute → Review → Fix → Package → Learn → Deliver
    """

    def __init__(self, settings: Settings, memory=None):
        self.settings = settings
        self.memory = memory
        self.llm_url = f"{settings.litellm_base_url}/chat/completions"
        self.llm_api_key = settings.litellm_api_key
        self.default_model = settings.default_model
        self.safety = SafetyRails()
        self.output_dir = (
            Path(settings.persona_dir).parent / "output" / "self_mode"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        goal_card_text: str,
        dry_run: bool = False,
        run_id: Optional[str] = None,
    ) -> ResultPack:
        """
        Main entry point. Execute a Goal Card end-to-end.

        Args:
            goal_card_text: Raw Goal Card text
            dry_run: If True, plan only — no execution
            run_id: Optional existing run_id to resume
        """
        start_time = time.time()
        errors_seen: list[str] = []

        # ---- STEP 0: RECEIVE ----
        logger.info("[SELF MODE] Step 0: RECEIVE")
        goal_card = GoalCardParser.parse(goal_card_text)
        if not goal_card.goal_id:
            goal_card.goal_id = f"GC-{uuid4().hex[:8].upper()}"
        if not goal_card.project_id:
            goal_card.project_id = "champ_v3"

        run_id = run_id or (
            f"RUN-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
            f"-{uuid4().hex[:6]}"
        )

        await self._save_run(
            run_id, goal_card, step=STEPS["receive"],
            status=RunStatus.PLANNING.value, subtasks=[],
        )

        # ---- STEP 1: PLAN ----
        logger.info("[SELF MODE] Step 1: PLAN")
        try:
            subtasks = await self._plan(goal_card)
        except Exception as e:
            logger.error(f"[SELF MODE] Planning failed: {e}")
            await self._save_run(
                run_id, goal_card, step=STEPS["plan"],
                status=RunStatus.FAILED.value, subtasks=[],
            )
            return ResultPack(
                goal_id=goal_card.goal_id,
                project_id=goal_card.project_id,
                run_id=run_id,
                status="Failed",
                deliverables="None -- planning failed",
                decisions_made="N/A",
                issues_hit=f"Planning error: {e}",
                next_actions="Fix the goal card or retry",
                time_cost=f"Wall time: {time.time() - start_time:.1f}s",
                evidence=str(e),
            )

        await self._save_run(
            run_id, goal_card, step=STEPS["plan"],
            status=RunStatus.PLANNING.value, subtasks=subtasks,
        )

        # ---- DRY RUN EXIT ----
        if dry_run:
            logger.info("[SELF MODE] Dry run -- returning plan only")
            return ResultPack(
                goal_id=goal_card.goal_id,
                project_id=goal_card.project_id,
                run_id=run_id,
                status="DryRun",
                deliverables="Plan only -- no execution",
                decisions_made=f"Planned {len(subtasks)} subtasks",
                issues_hit="N/A (dry run)",
                next_actions="\n".join(
                    f"- [{st.order}] {st.description}" for st in subtasks
                ),
                time_cost=(
                    f"Wall time: {time.time() - start_time:.1f}s "
                    f"(planning only)"
                ),
                evidence="Dry run -- no execution evidence",
            )

        # ---- STEP 2: APPROVE ----
        logger.info("[SELF MODE] Step 2: APPROVE")
        if self._needs_approval(goal_card):
            await self._save_run(
                run_id, goal_card, step=STEPS["approve"],
                status=RunStatus.AWAITING_APPROVAL.value, subtasks=subtasks,
            )
            return ResultPack(
                goal_id=goal_card.goal_id,
                project_id=goal_card.project_id,
                run_id=run_id,
                status="Blocked",
                deliverables="Awaiting approval",
                decisions_made="Plan requires human approval before execution",
                issues_hit="N/A",
                next_actions="Approve or reject the plan",
                time_cost=f"Wall time: {time.time() - start_time:.1f}s",
                evidence="Plan generated, awaiting sign-off",
            )

        # ---- STEP 3: EXECUTE ----
        logger.info("[SELF MODE] Step 3: EXECUTE")
        await self._save_run(
            run_id, goal_card, step=STEPS["execute"],
            status=RunStatus.EXECUTING.value, subtasks=subtasks,
        )

        execution_log: list[str] = []
        for st in subtasks:
            # Safety check
            violation = self.safety.check_subtask(st, goal_card)
            if violation:
                st.status = SubTaskStatus.SKIPPED.value
                st.error = f"Safety violation: {violation}"
                execution_log.append(
                    f"[SKIPPED] {st.description}: {violation}"
                )
                continue

            st.status = SubTaskStatus.IN_PROGRESS.value
            try:
                output = await self._execute_subtask(st, goal_card)
                st.status = SubTaskStatus.COMPLETED.value
                if len(output) > 2000:
                    logger.warning(
                        f"[SELF MODE] Output truncated from {len(output)} "
                        f"to 2000 chars for: {st.description}"
                    )
                st.output = output[:2000]
                execution_log.append(f"[OK] {st.description}")
            except Exception as e:
                st.status = SubTaskStatus.FAILED.value
                st.error = str(e)
                execution_log.append(f"[FAIL] {st.description}: {e}")

                # Stop condition: same error twice
                error_sig = str(e)[:100]
                if error_sig in errors_seen:
                    logger.warning(
                        "[SELF MODE] Stop condition: same error twice"
                    )
                    await self._save_run(
                        run_id, goal_card, step=STEPS["execute"],
                        status=RunStatus.BLOCKED.value, subtasks=subtasks,
                    )
                    return ResultPack(
                        goal_id=goal_card.goal_id,
                        project_id=goal_card.project_id,
                        run_id=run_id,
                        status="Blocked",
                        deliverables=self._collect_deliverables(subtasks),
                        decisions_made="Execution halted — repeated error",
                        issues_hit=(
                            f"Same error occurred twice:\n{error_sig}\n\n"
                            f"Option A: Retry with different approach\n"
                            f"Option B: Escalate to human"
                        ),
                        next_actions="Human decision required",
                        time_cost=(
                            f"Wall time: {time.time() - start_time:.1f}s | "
                            f"Model: {self.default_model}"
                        ),
                        evidence="\n".join(execution_log),
                    )
                errors_seen.append(error_sig)

        # ---- STEP 4: REVIEW ----
        logger.info("[SELF MODE] Step 4: REVIEW")
        await self._save_run(
            run_id, goal_card, step=STEPS["review"],
            status=RunStatus.REVIEWING.value, subtasks=subtasks,
        )
        review = await self._review(goal_card, subtasks, execution_log)

        # ---- STEP 5: FIX (if needed) ----
        retry_count = 0
        while not review.get("passed", False) and retry_count < MAX_FIX_RETRIES:
            retry_count += 1
            logger.info(
                f"[SELF MODE] Step 5: FIX (attempt {retry_count}"
                f"/{MAX_FIX_RETRIES})"
            )
            await self._save_run(
                run_id, goal_card, step=STEPS["fix"],
                status=RunStatus.FIXING.value, subtasks=subtasks,
            )

            fix_tasks = await self._generate_fixes(
                goal_card, review, subtasks, execution_log
            )
            for ft in fix_tasks:
                violation = self.safety.check_subtask(ft, goal_card)
                if violation:
                    ft.status = SubTaskStatus.SKIPPED.value
                    ft.error = f"Safety violation: {violation}"
                    continue
                try:
                    output = await self._execute_subtask(ft, goal_card)
                    ft.status = SubTaskStatus.COMPLETED.value
                    ft.output = output[:2000]
                    execution_log.append(f"[FIX-OK] {ft.description}")
                except Exception as e:
                    ft.status = SubTaskStatus.FAILED.value
                    ft.error = str(e)
                    execution_log.append(
                        f"[FIX-FAIL] {ft.description}: {e}"
                    )

            subtasks.extend(fix_tasks)
            review = await self._review(goal_card, subtasks, execution_log)

        # ---- STEP 6: PACKAGE ----
        logger.info("[SELF MODE] Step 6: PACKAGE")
        final_status = "Complete" if review.get("passed") else "Partial"
        elapsed = time.time() - start_time
        tool_calls = len(
            [s for s in subtasks if s.status == SubTaskStatus.COMPLETED.value]
        )

        result_pack = ResultPack(
            goal_id=goal_card.goal_id,
            project_id=goal_card.project_id,
            run_id=run_id,
            status=final_status,
            deliverables=self._collect_deliverables(subtasks),
            decisions_made=self._collect_decisions(subtasks),
            issues_hit=self._collect_issues(subtasks, review),
            next_actions=self._collect_next_actions(review),
            time_cost=(
                f"Wall time: {elapsed:.0f}s | "
                f"Model: {self.default_model} | "
                f"Tool calls: {tool_calls}"
            ),
            evidence=self._collect_evidence(
                subtasks, review, execution_log
            ),
        )

        await self._save_run(
            run_id, goal_card, step=STEPS["package"],
            status=RunStatus.PACKAGING.value, subtasks=subtasks,
            result_pack=result_pack,
        )

        # ---- STEP 7: LEARN ----
        logger.info("[SELF MODE] Step 7: LEARN")
        await self._learn(goal_card, result_pack, subtasks, run_id)

        # ---- STEP 8: DELIVER ----
        logger.info("[SELF MODE] Step 8: DELIVER")
        await self._save_run(
            run_id, goal_card, step=STEPS["deliver"],
            status=result_pack.status.lower(), subtasks=subtasks,
            result_pack=result_pack,
        )

        # Write Result Pack to file
        result_file = self.output_dir / f"{run_id}_result.txt"
        result_file.write_text(result_pack.to_text(), encoding="utf-8")
        logger.info(f"[SELF MODE] Result Pack saved to {result_file}")

        return result_pack

    # ---- Resume from Checkpoint ----

    async def resume(self, run_id: str) -> ResultPack:
        """
        Resume a run from its persisted state.
        Loads goal_card + subtasks from DB, determines resume point,
        and continues from the appropriate step.
        """
        if not self.memory:
            raise RuntimeError("Cannot resume without memory (Supabase)")

        db_record = await self.memory.get_self_mode_run(run_id)
        if not db_record:
            raise ValueError(f"Run {run_id} not found in database")

        # Reconstruct GoalCard
        gc = db_record.get("goal_card", {})
        goal_card = GoalCard(
            objective=gc.get("objective", ""),
            problem=gc.get("problem", ""),
            solution=gc.get("solution", ""),
            stack=gc.get("stack", ""),
            constraints=gc.get("constraints", ""),
            approval=gc.get("approval", ""),
            deliverables=gc.get("deliverables", ""),
            context_assets=gc.get("context_assets", ""),
            success_checks=gc.get("success_checks", ""),
            goal_id=gc.get("goal_id", ""),
            project_id=gc.get("project_id", "champ_v3"),
            priority=gc.get("priority", "P1"),
            risk_level=gc.get("risk_level", "low"),
        )

        # Reconstruct subtasks
        subtasks = [
            SubTask.from_dict(s)
            for s in db_record.get("subtasks", [])
        ]

        current_step = db_record.get("current_step", 0)
        status = db_record.get("status", "")

        logger.info(
            f"[SELF MODE] Resuming {run_id} from "
            f"step={current_step}, status={status}"
        )

        start_time = time.time()
        errors_seen: list[str] = []

        # If awaiting_approval, approval is now granted -- skip to execute
        if status == RunStatus.AWAITING_APPROVAL.value:
            current_step = STEPS["execute"]

        # Determine entry point
        if current_step <= STEPS["execute"]:
            return await self._run_from_execute(
                run_id, goal_card, subtasks, start_time, errors_seen,
            )
        elif current_step <= STEPS["fix"]:
            return await self._run_from_review(
                run_id, goal_card, subtasks, start_time, errors_seen,
            )
        else:
            return await self._run_from_package(
                run_id, goal_card, subtasks, start_time,
            )

    async def _run_from_execute(
        self, run_id: str, goal_card: GoalCard,
        subtasks: list[SubTask], start_time: float,
        errors_seen: list[str],
    ) -> ResultPack:
        """Execute pending subtasks, then review+fix+package+learn+deliver."""
        logger.info("[SELF MODE] Step 3: EXECUTE (resume)")
        await self._save_run(
            run_id, goal_card, step=STEPS["execute"],
            status=RunStatus.EXECUTING.value, subtasks=subtasks,
        )

        execution_log: list[str] = []

        # Rebuild log from already-completed subtasks
        for st in subtasks:
            if st.status == SubTaskStatus.COMPLETED.value:
                execution_log.append(f"[OK] {st.description} (prior)")
            elif st.status == SubTaskStatus.FAILED.value:
                execution_log.append(
                    f"[FAIL] {st.description}: {st.error} (prior)"
                )
            elif st.status == SubTaskStatus.SKIPPED.value:
                execution_log.append(
                    f"[SKIPPED] {st.description}: {st.error} (prior)"
                )

        # Execute only pending subtasks
        for st in subtasks:
            if st.status != SubTaskStatus.PENDING.value:
                continue

            violation = self.safety.check_subtask(st, goal_card)
            if violation:
                st.status = SubTaskStatus.SKIPPED.value
                st.error = f"Safety violation: {violation}"
                execution_log.append(
                    f"[SKIPPED] {st.description}: {violation}"
                )
                continue

            st.status = SubTaskStatus.IN_PROGRESS.value
            try:
                output = await self._execute_subtask(st, goal_card)
                st.status = SubTaskStatus.COMPLETED.value
                if len(output) > 2000:
                    logger.warning(
                        f"[SELF MODE] Output truncated from {len(output)} "
                        f"to 2000 chars for: {st.description}"
                    )
                st.output = output[:2000]
                execution_log.append(f"[OK] {st.description}")
            except Exception as e:
                st.status = SubTaskStatus.FAILED.value
                st.error = str(e)
                execution_log.append(f"[FAIL] {st.description}: {e}")

                error_sig = str(e)[:100]
                if error_sig in errors_seen:
                    logger.warning(
                        "[SELF MODE] Stop: same error twice (resume)"
                    )
                    await self._save_run(
                        run_id, goal_card, step=STEPS["execute"],
                        status=RunStatus.BLOCKED.value, subtasks=subtasks,
                    )
                    return ResultPack(
                        goal_id=goal_card.goal_id,
                        project_id=goal_card.project_id,
                        run_id=run_id,
                        status="Blocked",
                        deliverables=self._collect_deliverables(subtasks),
                        decisions_made="Execution halted — repeated error",
                        issues_hit=f"Same error twice:\n{error_sig}",
                        next_actions="Human decision required",
                        time_cost=(
                            f"Wall time: {time.time() - start_time:.1f}s"
                        ),
                        evidence="\n".join(execution_log),
                    )
                errors_seen.append(error_sig)

        return await self._run_from_review(
            run_id, goal_card, subtasks, start_time,
            errors_seen, execution_log,
        )

    async def _run_from_review(
        self, run_id: str, goal_card: GoalCard,
        subtasks: list[SubTask], start_time: float,
        errors_seen: list[str],
        execution_log: list[str] | None = None,
    ) -> ResultPack:
        """Review + fix loop, then package+learn+deliver."""
        if execution_log is None:
            execution_log = [
                f"[{'OK' if st.status == 'completed' else 'FAIL'}] "
                f"{st.description}"
                for st in subtasks
                if st.status in ("completed", "failed")
            ]

        logger.info("[SELF MODE] Step 4: REVIEW (resume)")
        await self._save_run(
            run_id, goal_card, step=STEPS["review"],
            status=RunStatus.REVIEWING.value, subtasks=subtasks,
        )
        review = await self._review(goal_card, subtasks, execution_log)

        # Derive retry count from existing fix subtasks
        existing_fixes = len(set(
            st.id.split("-")[1] for st in subtasks
            if st.id.startswith("fix-")
        )) if any(st.id.startswith("fix-") for st in subtasks) else 0
        retry_count = existing_fixes

        while (
            not review.get("passed", False)
            and retry_count < MAX_FIX_RETRIES
        ):
            retry_count += 1
            logger.info(
                f"[SELF MODE] Step 5: FIX (attempt {retry_count}"
                f"/{MAX_FIX_RETRIES}) (resume)"
            )
            await self._save_run(
                run_id, goal_card, step=STEPS["fix"],
                status=RunStatus.FIXING.value, subtasks=subtasks,
            )

            fix_tasks = await self._generate_fixes(
                goal_card, review, subtasks, execution_log
            )
            for ft in fix_tasks:
                violation = self.safety.check_subtask(ft, goal_card)
                if violation:
                    ft.status = SubTaskStatus.SKIPPED.value
                    ft.error = f"Safety violation: {violation}"
                    continue
                try:
                    output = await self._execute_subtask(ft, goal_card)
                    ft.status = SubTaskStatus.COMPLETED.value
                    ft.output = output[:2000]
                    execution_log.append(f"[FIX-OK] {ft.description}")
                except Exception as e:
                    ft.status = SubTaskStatus.FAILED.value
                    ft.error = str(e)
                    execution_log.append(
                        f"[FIX-FAIL] {ft.description}: {e}"
                    )

            subtasks.extend(fix_tasks)
            review = await self._review(
                goal_card, subtasks, execution_log
            )

        return await self._run_from_package(
            run_id, goal_card, subtasks, start_time,
            review, execution_log,
        )

    async def _run_from_package(
        self, run_id: str, goal_card: GoalCard,
        subtasks: list[SubTask], start_time: float,
        review: dict | None = None,
        execution_log: list[str] | None = None,
    ) -> ResultPack:
        """Package + learn + deliver."""
        if review is None:
            review = {
                "passed": True, "checks": [],
                "summary": "Resumed after packaging",
            }
        if execution_log is None:
            execution_log = []

        logger.info("[SELF MODE] Step 6: PACKAGE (resume)")
        final_status = "Complete" if review.get("passed") else "Partial"
        elapsed = time.time() - start_time
        tool_calls = len(
            [s for s in subtasks
             if s.status == SubTaskStatus.COMPLETED.value]
        )

        result_pack = ResultPack(
            goal_id=goal_card.goal_id,
            project_id=goal_card.project_id,
            run_id=run_id,
            status=final_status,
            deliverables=self._collect_deliverables(subtasks),
            decisions_made=self._collect_decisions(subtasks),
            issues_hit=self._collect_issues(subtasks, review),
            next_actions=self._collect_next_actions(review),
            time_cost=(
                f"Wall time: {elapsed:.0f}s | "
                f"Model: {self.default_model} | "
                f"Tool calls: {tool_calls}"
            ),
            evidence=self._collect_evidence(
                subtasks, review, execution_log
            ),
        )

        await self._save_run(
            run_id, goal_card, step=STEPS["package"],
            status=RunStatus.PACKAGING.value, subtasks=subtasks,
            result_pack=result_pack,
        )

        logger.info("[SELF MODE] Step 7: LEARN (resume)")
        await self._learn(goal_card, result_pack, subtasks, run_id)

        logger.info("[SELF MODE] Step 8: DELIVER (resume)")
        await self._save_run(
            run_id, goal_card, step=STEPS["deliver"],
            status=result_pack.status.lower(), subtasks=subtasks,
            result_pack=result_pack,
        )

        result_file = self.output_dir / f"{run_id}_result.txt"
        result_file.write_text(result_pack.to_text(), encoding="utf-8")
        logger.info(f"[SELF MODE] Result Pack saved to {result_file}")

        return result_pack

    # ---- Core Steps ----

    async def _plan(self, goal_card: GoalCard) -> list[SubTask]:
        """Ask Brain to break the goal into subtasks."""
        prompt = PLANNING_PROMPT.format(goal_card=goal_card.to_prompt())
        raw = await self._llm_call(prompt)
        parsed = self._parse_json_response(raw)
        if not isinstance(parsed, list):
            raise ValueError(f"Planning returned non-list: {type(parsed)}")

        subtasks = []
        for i, item in enumerate(parsed):
            item.setdefault("id", f"st-{i + 1:03d}")
            item.setdefault("order", i + 1)
            subtasks.append(SubTask.from_dict(item))

        logger.info(f"[SELF MODE] Planned {len(subtasks)} subtasks")
        return subtasks

    async def _execute_subtask(
        self, st: SubTask, goal_card: GoalCard
    ) -> str:
        """Execute a single subtask based on its action type."""
        action = st.action
        params = st.params

        if action == SubTaskAction.LLM_GENERATE.value:
            return await self._action_llm_generate(params, goal_card)
        elif action == SubTaskAction.FILE_WRITE.value:
            return self._action_file_write(params)
        elif action == SubTaskAction.COMMAND_RUN.value:
            return self._action_command_run(params)
        elif action == SubTaskAction.BROWSER_ACTION.value:
            return await self._action_browser(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _action_llm_generate(
        self, params: dict, goal_card: GoalCard
    ) -> str:
        """Generate content via LLM and optionally write to file."""
        prompt = params.get("prompt", "")
        if not prompt:
            raise ValueError("llm_generate requires a 'prompt' param")

        full_prompt = (
            f"You are generating content for an autonomous task.\n"
            f"Goal: {goal_card.objective}\n"
            f"Constraints: {goal_card.constraints}\n\n"
            f"TASK:\n{prompt}\n\n"
            f"Return ONLY the raw content (code, text, etc). "
            f"No markdown fences unless the content IS markdown."
        )

        content = await self._llm_call(full_prompt)
        content = self._strip_code_fences(content)

        output_file = params.get("output_file")
        if output_file:
            file_path = self.output_dir / output_file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"[SELF MODE] Generated file: {file_path}")
            return (
                f"Generated and wrote to {file_path} ({len(content)} chars)"
            )

        return content

    def _action_file_write(self, params: dict) -> str:
        """Write literal content to a file."""
        file_path = params.get("file_path", "")
        content = params.get("content", "")
        if not file_path:
            raise ValueError("file_write requires 'file_path' param")

        path = self.output_dir / file_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {path}"

    def _action_command_run(self, params: dict) -> str:
        """Run a shell command and return output."""
        command = params.get("command", "")
        if not command:
            raise ValueError("command_run requires 'command' param")

        violation = self.safety.check_command(command)
        if violation:
            raise PermissionError(f"Command blocked: {violation}")

        working_dir = params.get("working_dir", str(self.output_dir))
        if not Path(working_dir).is_absolute():
            working_dir = str(self.output_dir / working_dir)

        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"  # Fix Windows cp1252 issues
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=working_dir,
                env=env,
            )
            output = result.stdout
            if result.returncode != 0:
                output += f"\nSTDERR:\n{result.stderr}"
                raise RuntimeError(
                    f"Command failed (exit {result.returncode}): "
                    f"{result.stderr[:500]}"
                )
            return output[:5000]
        except subprocess.TimeoutExpired:
            raise TimeoutError(
                f"Command timed out after 120s: {command}"
            )

    async def _action_browser(self, params: dict) -> str:
        """Execute a browser action via the Hands bridge."""
        browser_command = params.get("browser_command", "browse")
        url = params.get("url", "")
        if not url:
            raise ValueError("browser_action requires a 'url' param")

        # Safety: check domain allowlist
        if not self.safety._is_allowed_domain(url):
            raise PermissionError(
                f"Domain not in allowlist for browser_action: {url}"
            )

        if browser_command == "browse":
            result = await hands_browse(url)
            if not result.get("ok"):
                raise RuntimeError(
                    f"Browse failed: {result.get('error', 'Unknown')}"
                )
            title = result.get("title", "No title")
            text = result.get("text", "")[:2000]
            return (
                f"Browsed: {title}\n"
                f"URL: {result.get('url', url)}\n"
                f"Content:\n{text}"
            )

        elif browser_command == "screenshot":
            result = await hands_screenshot(url)
            if not result.get("ok"):
                raise RuntimeError(
                    f"Screenshot failed: {result.get('error', 'Unknown')}"
                )
            return (
                f"Screenshot saved: {result.get('path', 'unknown')}\n"
                f"Page: {result.get('title', 'No title')}"
            )

        elif browser_command == "fill_form":
            fields = params.get("fields", [])
            submit_selector = params.get("submit_selector")
            if not fields:
                raise ValueError(
                    "fill_form requires 'fields' param "
                    "(list of {selector, value})"
                )
            result = await hands_fill_form(url, fields, submit_selector)
            if not result.get("ok"):
                raise RuntimeError(
                    f"Form fill failed: {result.get('error', 'Unknown')}"
                )
            filled = result.get("fields_filled", [])
            return (
                f"Form filled on {result.get('title', url)}: "
                f"{len(filled)} fields"
            )

        else:
            raise ValueError(
                f"Unknown browser_command: {browser_command}. "
                f"Use 'browse', 'screenshot', or 'fill_form'."
            )

    async def _review(
        self, goal_card: GoalCard, subtasks: list[SubTask],
        execution_log: list[str],
    ) -> dict:
        """Ask Brain to review execution results against success checks."""
        exec_summary = "\n".join(execution_log)
        for st in subtasks:
            if st.output:
                exec_summary += (
                    f"\n\n--- Output of '{st.description}' ---\n"
                    f"{st.output[:1000]}"
                )

        prompt = REVIEW_PROMPT.format(
            success_checks=goal_card.success_checks,
            execution_results=exec_summary,
        )
        try:
            raw = await self._llm_call(prompt)
            parsed = self._parse_json_response(raw)
            if not isinstance(parsed, dict):
                return {
                    "passed": False, "checks": [],
                    "summary": "Review returned non-dict",
                }
            return parsed
        except Exception as e:
            logger.error(f"[SELF MODE] Review failed: {e}")
            return {
                "passed": False, "checks": [],
                "summary": f"Review parse failed: {e}",
            }

    async def _generate_fixes(
        self, goal_card: GoalCard, review: dict,
        subtasks: list[SubTask], execution_log: list[str],
    ) -> list[SubTask]:
        """Generate fix subtasks for failed checks."""
        failed = [
            c for c in review.get("checks", []) if not c.get("passed")
        ]
        if not failed:
            return []

        prompt = FIX_PROMPT.format(
            goal_card=goal_card.to_prompt(),
            failed_checks=json.dumps(failed, indent=2),
            execution_results="\n".join(execution_log),
        )
        raw = await self._llm_call(prompt)
        parsed = self._parse_json_response(raw)
        if not isinstance(parsed, list):
            return []

        fix_tasks = []
        base_order = max((s.order for s in subtasks), default=0)
        for i, item in enumerate(parsed):
            item.setdefault("id", f"fix-{i + 1:03d}")
            item.setdefault("order", base_order + i + 1)
            fix_tasks.append(SubTask.from_dict(item))

        return fix_tasks

    async def _learn(
        self, goal_card: GoalCard, result_pack: ResultPack,
        subtasks: list[SubTask], run_id: str,
    ) -> None:
        """Extract lessons and healing entries from this run."""
        if not self.memory:
            return

        try:
            from mind.healing import HealingLoop  # noqa: F401

            # Store healing entries for failures
            for st in subtasks:
                if st.status == SubTaskStatus.FAILED.value and st.error:
                    await self.memory.insert_healing(
                        user_id="anthony",
                        error_type="self_mode_task_failure",
                        severity="medium",
                        trigger_context=(
                            f"Goal: {goal_card.goal_id}, "
                            f"Task: {st.description}"
                        ),
                        prevention_rule=f"Check: {st.error[:200]}",
                    )

            # Store lessons about decisions made
            if result_pack.decisions_made:
                await self.memory.insert_lesson(
                    user_id="anthony",
                    lesson=(
                        f"Self Mode ({goal_card.goal_id}): "
                        f"{result_pack.decisions_made[:300]}"
                    ),
                    tags=["self_mode", goal_card.goal_id],
                )

            logger.info(f"[SELF MODE] Learning captured for {run_id}")
        except Exception as e:
            logger.error(f"[SELF MODE] Learning failed (non-fatal): {e}")

    def _needs_approval(self, goal_card: GoalCard) -> bool:
        """Check if the goal card requires human approval."""
        approval_text = goal_card.approval.lower()
        auto_indicators = [
            "none", "auto", "no approval", "auto-execute", "auto-run",
        ]
        return not any(ind in approval_text for ind in auto_indicators)

    # ---- Helpers ----

    async def _llm_call(self, prompt: str) -> str:
        """
        Make an LLM call. Tries LiteLLM first, falls back to direct
        Anthropic API if LiteLLM is unavailable or returns an error.
        """
        # Try LiteLLM first
        try:
            payload = {
                "model": self.default_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4000,
            }
            response = requests.post(
                self.llm_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.llm_api_key}",
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as litellm_err:
            logger.warning(
                f"[SELF MODE] LiteLLM failed ({litellm_err}), "
                f"trying direct Anthropic fallback..."
            )

        # Fallback: direct Anthropic API
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not anthropic_key:
            raise RuntimeError(
                "LiteLLM unavailable and no ANTHROPIC_API_KEY set"
            )

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                json={
                    "model": "claude-sonnet-4-5-20250929",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                },
                headers={
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=90,
            )
            response.raise_for_status()
            data = response.json()
            # Anthropic Messages API returns content as array
            content_blocks = data.get("content", [])
            text_parts = [
                b["text"] for b in content_blocks
                if b.get("type") == "text"
            ]
            return "".join(text_parts)
        except Exception as e:
            logger.error(f"[SELF MODE] Direct Anthropic call failed: {e}")
            raise

    def _parse_json_response(self, text: str) -> dict | list:
        """Parse JSON from LLM response, handling code fences."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        text = text.strip()
        return json.loads(text)

    def _strip_code_fences(self, text: str) -> str:
        """Remove markdown code fences from generated content."""
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3].rstrip()
        return text

    def _collect_deliverables(self, subtasks: list[SubTask]) -> str:
        lines = []
        for st in subtasks:
            if st.status == SubTaskStatus.COMPLETED.value and st.output:
                lines.append(f"- {st.description}: {st.output[:200]}")
        return "\n".join(lines) if lines else "No deliverables produced"

    def _collect_decisions(self, subtasks: list[SubTask]) -> str:
        decisions = []
        for st in subtasks:
            if (
                st.action == SubTaskAction.LLM_GENERATE.value
                and st.status == SubTaskStatus.COMPLETED.value
            ):
                decisions.append(f"- Generated: {st.description}")
        return "\n".join(decisions) if decisions else "No major decisions"

    def _collect_issues(
        self, subtasks: list[SubTask], review: dict
    ) -> str:
        lines = []
        for st in subtasks:
            if st.error:
                lines.append(f"- {st.description}: {st.error[:200]}")
        for check in review.get("checks", []):
            if not check.get("passed"):
                lines.append(
                    f"- Review: {check.get('check', '?')}: "
                    f"{check.get('detail', '')}"
                )
        return "\n".join(lines) if lines else "No issues"

    def _collect_next_actions(self, review: dict) -> str:
        if review.get("passed"):
            return "- None — all checks passed"
        failed = [
            c for c in review.get("checks", []) if not c.get("passed")
        ]
        if failed:
            return "\n".join(
                f"- Fix: {c.get('check', '?')}" for c in failed
            )
        return "- Review output manually"

    def _collect_evidence(
        self, subtasks: list[SubTask], review: dict,
        execution_log: list[str],
    ) -> str:
        parts = ["Execution log:"]
        parts.extend(execution_log[:20])
        parts.append(f"\nReview: {review.get('summary', 'N/A')}")
        for check in review.get("checks", []):
            status = "PASS" if check.get("passed") else "FAIL"
            parts.append(f"  [{status}] {check.get('check', '?')}")
        return "\n".join(parts)

    async def _save_run(
        self, run_id: str, goal_card: GoalCard, step: int,
        status: str, subtasks: list[SubTask],
        result_pack: Optional[ResultPack] = None,
    ) -> None:
        """Persist run state to Supabase."""
        if not self.memory:
            return
        try:
            await self.memory.upsert_self_mode_run(
                run_id=run_id,
                goal_card=goal_card.to_dict(),
                current_step=step,
                subtasks=[s.to_dict() for s in subtasks],
                result_pack=result_pack.to_dict() if result_pack else None,
                status=status,
            )
        except Exception as e:
            logger.error(f"[SELF MODE] Save run failed (non-fatal): {e}")
