# ============================================
# CHAMP V3 — Self Mode Heartbeat
# Brick 8: Scheduled loop that checks for
# queued Goal Cards and executes them.
# Runs every 30 minutes by default.
# ============================================

import asyncio
import logging
from typing import Optional

from brain.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 30 * 60  # 30 minutes


class Heartbeat:
    """
    Scheduled heartbeat that polls for queued Self Mode runs.

    Pattern: asyncio background task that:
    1. Checks self_mode_runs for status='queued'
    2. Picks up the oldest queued run
    3. Executes it via SelfModeEngine
    4. Sleeps until next interval
    """

    def __init__(
        self,
        settings: Settings,
        memory=None,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ):
        self.settings = settings
        self.memory = memory
        self.interval = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the heartbeat background loop."""
        if self._running:
            logger.warning("[HEARTBEAT] Already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            f"[HEARTBEAT] Started — checking every {self.interval}s"
        )

    async def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[HEARTBEAT] Stopped")

    async def _loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HEARTBEAT] Tick failed: {e}")

            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break

    async def _tick(self) -> None:
        """Single heartbeat tick — check for and execute queued runs."""
        if not self.memory:
            return

        try:
            queued = await self.memory.get_queued_self_mode_runs()
        except Exception as e:
            logger.error(f"[HEARTBEAT] Failed to fetch queued runs: {e}")
            return

        if not queued:
            logger.debug("[HEARTBEAT] No queued runs")
            return

        logger.info(f"[HEARTBEAT] Found {len(queued)} queued run(s)")

        for run_data in queued:
            run_id = run_data.get("id")
            goal_card_data = run_data.get("goal_card")

            if not goal_card_data:
                logger.warning(
                    f"[HEARTBEAT] Run {run_id} has no goal_card data"
                )
                continue

            try:
                # Import here to avoid circular imports
                from self_mode.engine import SelfModeEngine

                engine = SelfModeEngine(
                    self.settings, memory=self.memory
                )
                goal_text = self._goal_card_to_text(goal_card_data)

                logger.info(f"[HEARTBEAT] Executing run {run_id}")
                await engine.run(goal_text, run_id=run_id)
                logger.info(f"[HEARTBEAT] Run {run_id} completed")

            except Exception as e:
                logger.error(f"[HEARTBEAT] Run {run_id} failed: {e}")
                try:
                    await self.memory.update_self_mode_run_status(
                        run_id, "failed"
                    )
                except Exception:
                    pass

    def _goal_card_to_text(self, data: dict) -> str:
        """Reconstruct Goal Card text from stored dict."""
        goal_id = data.get("goal_id", "unknown")
        project_id = data.get("project_id", "champ_v3")
        meta = f"(goal_id: {goal_id} | project_id: {project_id})"
        return (
            f"GOAL CARD v1.0\n{meta}\n\n"
            f"1) OBJECTIVE\n- {data.get('objective', '')}\n\n"
            f"2) PROBLEM\n- {data.get('problem', '')}\n\n"
            f"3) SOLUTION\n- {data.get('solution', '')}\n\n"
            f"4) STACK\n- {data.get('stack', '')}\n\n"
            f"5) CONSTRAINTS\n- {data.get('constraints', '')}\n\n"
            f"6) APPROVAL\n- {data.get('approval', '')}\n\n"
            f"7) DELIVERABLES\n- {data.get('deliverables', '')}\n\n"
            f"8) CONTEXT / ASSETS\n- {data.get('context_assets', '')}\n\n"
            f"9) SUCCESS CHECKS\n- {data.get('success_checks', '')}\n"
        )

    @property
    def is_running(self) -> bool:
        return self._running
