from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger("vajra_gate.crons")


@dataclass
class CronJob:
    id: str
    schedule_seconds: int
    task_input: str
    thread_id: str | None = None
    agent_config: dict[str, Any] | None = None
    last_run: float = 0.0
    next_run: float = 0.0
    run_count: int = 0
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "schedule_seconds": self.schedule_seconds,
            "task_input": self.task_input[:100],
            "thread_id": self.thread_id,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
        }


class CronScheduler:
    """Simple in-memory cron scheduler. Checks every 30s for due jobs."""

    def __init__(self):
        self._jobs: dict[str, CronJob] = {}
        self._task: asyncio.Task | None = None

    def add(self, schedule_seconds: int, task_input: str,
            thread_id: str | None = None,
            agent_config: dict[str, Any] | None = None) -> CronJob:
        job = CronJob(
            id=f"cron_{uuid.uuid4().hex[:12]}",
            schedule_seconds=schedule_seconds,
            task_input=task_input,
            thread_id=thread_id,
            agent_config=agent_config,
            next_run=time.time() + schedule_seconds,
        )
        self._jobs[job.id] = job
        logger.info("Cron %s: every %ss — %s", job.id, schedule_seconds, task_input[:60])
        return job

    def remove(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def list_jobs(self) -> list[CronJob]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> CronJob | None:
        return self._jobs.get(job_id)

    async def start(self, chat_getter: Any) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop(chat_getter))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, RuntimeError):
                pass
            self._task = None

    async def _run_loop(self, chat_getter: Any) -> None:
        while True:
            try:
                await self._tick(chat_getter)
            except Exception:
                logger.exception("Cron tick failed")
            await asyncio.sleep(30)

    async def _tick(self, chat_getter: Any) -> None:
        now = time.time()
        due = [j for j in self._jobs.values() if j.enabled and j.next_run <= now]
        for job in due:
            try:
                chat = await chat_getter()
                if job.thread_id:
                    msgs = await chat.history.async_load_session(job.thread_id)
                    if msgs is not None:
                        chat.session_id = job.thread_id
                        chat.messages = msgs
                await chat.send(job.task_input)
                job.run_count += 1
                logger.info("Cron %s: ran successfully (count=%s)", job.id, job.run_count)
            except Exception:
                logger.exception("Cron %s: run failed", job.id)
            finally:
                job.last_run = now
                job.next_run = now + job.schedule_seconds


_GLOBAL_SCHEDULER = CronScheduler()


def get_scheduler() -> CronScheduler:
    return _GLOBAL_SCHEDULER
