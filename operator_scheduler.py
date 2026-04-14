# ============================================
# Cocreatiq V1 — Operator Scheduler
# Operators run jobs on schedule without being asked
# Pattern: OpenFang Hands + Hermes cron
# ============================================

import logging
import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Callable, Optional, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    """A job that runs on a schedule for an operator."""
    id: str = field(default_factory=lambda: str(uuid4()))
    operator_name: str = ""
    job_name: str = ""
    description: str = ""
    schedule: str = ""  # cron-like: "every 30m", "daily 6am", "every 1h"
    callback: Optional[Callable] = None
    enabled: bool = True
    last_run: Optional[datetime] = None
    run_count: int = 0
    metadata: dict = field(default_factory=dict)


class OperatorScheduler:
    """
    Runs operator jobs on schedule.

    Examples:
    - Content operator: generate daily social posts at 6AM
    - Growth operator: check analytics every 2 hours
    - Retention operator: review churn signals daily
    - Operations operator: audit system health every 30 minutes
    """

    def __init__(self):
        self._jobs: dict[str, ScheduledJob] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register(
        self,
        operator_name: str,
        job_name: str,
        description: str,
        schedule: str,
        callback: Callable,
        metadata: dict = None,
    ) -> str:
        """Register a scheduled job for an operator."""
        job = ScheduledJob(
            operator_name=operator_name,
            job_name=job_name,
            description=description,
            schedule=schedule,
            callback=callback,
            metadata=metadata or {},
        )
        self._jobs[job.id] = job
        logger.info(f"[SCHEDULER] Registered: {operator_name}/{job_name} ({schedule})")
        return job.id

    def unregister(self, job_id: str) -> None:
        """Remove a scheduled job."""
        if job_id in self._jobs:
            job = self._jobs.pop(job_id)
            logger.info(f"[SCHEDULER] Unregistered: {job.operator_name}/{job.job_name}")

    def parse_interval_seconds(self, schedule: str) -> int:
        """Parse schedule string to seconds. Simple format."""
        s = schedule.lower().strip()
        if "every" in s:
            s = s.replace("every", "").strip()
        if s.endswith("m"):
            return int(s[:-1]) * 60
        elif s.endswith("h"):
            return int(s[:-1]) * 3600
        elif s.endswith("s"):
            return int(s[:-1])
        elif "daily" in schedule.lower():
            return 86400
        else:
            return 3600  # default 1 hour

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"[SCHEDULER] Started with {len(self._jobs)} jobs")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("[SCHEDULER] Stopped")

    async def _loop(self) -> None:
        """Main scheduler loop — checks and runs jobs."""
        while self._running:
            now = datetime.now(timezone.utc)

            for job_id, job in list(self._jobs.items()):
                if not job.enabled:
                    continue

                interval = self.parse_interval_seconds(job.schedule)

                # Check if it's time to run
                should_run = False
                if job.last_run is None:
                    should_run = True  # Never ran — run now
                else:
                    elapsed = (now - job.last_run).total_seconds()
                    if elapsed >= interval:
                        should_run = True

                if should_run:
                    try:
                        logger.info(f"[SCHEDULER] Running: {job.operator_name}/{job.job_name}")
                        if asyncio.iscoroutinefunction(job.callback):
                            await job.callback(job)
                        else:
                            job.callback(job)
                        job.last_run = now
                        job.run_count += 1
                        logger.info(f"[SCHEDULER] Completed: {job.operator_name}/{job.job_name} (run #{job.run_count})")
                    except Exception as e:
                        logger.error(f"[SCHEDULER] Failed: {job.operator_name}/{job.job_name}: {e}")

            await asyncio.sleep(30)  # Check every 30 seconds

    def get_jobs(self, operator_name: Optional[str] = None) -> list[dict]:
        """List all scheduled jobs, optionally filtered by operator."""
        jobs = []
        for job in self._jobs.values():
            if operator_name and job.operator_name != operator_name:
                continue
            jobs.append({
                "id": job.id,
                "operator": job.operator_name,
                "name": job.job_name,
                "description": job.description,
                "schedule": job.schedule,
                "enabled": job.enabled,
                "last_run": job.last_run.isoformat() if job.last_run else None,
                "run_count": job.run_count,
            })
        return jobs


# Global scheduler — singleton
scheduler = OperatorScheduler()