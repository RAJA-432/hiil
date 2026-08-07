from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

import vajra_gate.state as _state

logger = logging.getLogger("vajra_gate.crons")

_SEND_TIMEOUT = 300.0

_CRON_NAMESPACE = "crons"


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

    def to_storage(self) -> dict[str, Any]:
        """Serialize with full fields for durable persistence."""
        return {
            "id": self.id,
            "schedule_seconds": self.schedule_seconds,
            "task_input": self.task_input,
            "thread_id": self.thread_id,
            "agent_config": self.agent_config,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
        }

    def to_dict(self) -> dict[str, Any]:
        """API-facing view; task_input is truncated for display."""
        data = self.to_storage()
        data["task_input"] = (self.task_input or "")[:100]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CronJob:
        return cls(
            id=str(data["id"]),
            schedule_seconds=int(data["schedule_seconds"]),
            task_input=str(data["task_input"] or ""),
            thread_id=data.get("thread_id"),
            agent_config=data.get("agent_config"),
            last_run=float(data.get("last_run", 0.0)),
            next_run=float(data.get("next_run", 0.0)),
            run_count=int(data.get("run_count", 0)),
            enabled=bool(data.get("enabled", True)),
        )


class CronScheduler:
    """Scheduled jobs with durable persistence.

    Jobs are mirrored to the ``crons`` namespace of the shared KVStore on every
    ``add``/``remove`` and restored on first access, so scheduled tasks survive
    a gateway restart.
    """

    def __init__(self, store: Any = None):
        self._jobs: dict[str, CronJob] = {}
        self._task: asyncio.Task | None = None
        self._store = store

    def _kvstore(self) -> Any:
        if self._store is None:
            from vajra_gate.store import get_store
            self._store = get_store()
        return self._store

    def _load_persisted(self) -> None:
        """Restore jobs from the KVStore on first access (idempotent)."""
        if self._jobs:
            return
        try:
            items = self._kvstore().all_items(_CRON_NAMESPACE)
        except Exception:
            logger.warning("Failed to load persisted cron jobs", exc_info=True)
            return
        for item in items:
            value = item.get("value") or {}
            try:
                job = CronJob.from_dict(value)
            except (KeyError, TypeError, ValueError):
                logger.warning("Skipping invalid persisted cron job %s", item.get("key"))
                continue
            if job.id not in self._jobs:
                self._jobs[job.id] = job

    def _persist_job(self, job: CronJob) -> None:
        try:
            self._kvstore().upsert(_CRON_NAMESPACE, [{"key": job.id, "value": job.to_storage()}])
        except Exception:
            logger.warning("Failed to persist cron job %s", job.id, exc_info=True)

    def _remove_persisted(self, job_id: str) -> None:
        try:
            self._kvstore().delete(_CRON_NAMESPACE, [job_id])
        except Exception:
            logger.warning("Failed to remove persisted cron job %s", job_id, exc_info=True)

    def add(self, schedule_seconds: int, task_input: str,
            thread_id: str | None = None,
            agent_config: dict[str, Any] | None = None) -> CronJob:
        self._load_persisted()
        job = CronJob(
            id=f"cron_{uuid.uuid4().hex[:12]}",
            schedule_seconds=schedule_seconds,
            task_input=task_input,
            thread_id=thread_id,
            agent_config=agent_config,
            next_run=time.time() + schedule_seconds,
        )
        self._jobs[job.id] = job
        self._persist_job(job)
        logger.info("Cron %s: every %ss — %s", job.id, schedule_seconds, task_input[:60])
        return job

    def remove(self, job_id: str) -> bool:
        self._load_persisted()
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._remove_persisted(job_id)
            return True
        return False

    def list_jobs(self) -> list[CronJob]:
        self._load_persisted()
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> CronJob | None:
        self._load_persisted()
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
                msgs: Any = None
                if job.thread_id:
                    chat = await _state._get_pool().get(job.thread_id)
                    msgs = await chat.history.async_load_session(job.thread_id)
                async with chat.lock:
                    if msgs is not None:
                        chat.session_id = job.thread_id
                        chat.messages = msgs
                    sendable = getattr(chat, "_chat", chat)
                    await asyncio.wait_for(
                        sendable.send(job.task_input),
                        timeout=_SEND_TIMEOUT,
                    )
                job.run_count += 1
                logger.info("Cron %s: ran successfully (count=%s)", job.id, job.run_count)
            except TimeoutError:
                logger.warning("Cron %s: run timed out after %ss", job.id, _SEND_TIMEOUT)
            except Exception:
                logger.exception("Cron %s: run failed", job.id)
            finally:
                job.last_run = now
                job.next_run = now + job.schedule_seconds
                self._persist_job(job)


_GLOBAL_SCHEDULER = CronScheduler()


def get_scheduler() -> CronScheduler:
    return _GLOBAL_SCHEDULER
