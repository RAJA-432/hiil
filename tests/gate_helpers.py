"""Shared fakes and builders for vajra_gate router/service tests.

Not collected by pytest (does not match test_*.py). Keeps FastAPI router
tests fast and network-free by replacing _require_chat / get_store /
get_scheduler with lightweight in-memory stand-ins.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from vajra_gate.auth import get_current_user

# ---------------------------------------------------------------------------
# Agent fakes
# ---------------------------------------------------------------------------


class FakeAgentRunner:
    def __init__(self, name: str = "researcher", role: str = "research", capabilities: list[str] | None = None) -> None:
        self.agent_id = "agent_abc123"
        self.config = SimpleNamespace(
            name=name,
            role=role,
            capabilities=list(capabilities or []),
            model_dump=lambda: {"name": name, "role": role, "capabilities": list(capabilities or [])},
        )
        self._status = "idle"
        self.virtual_files: dict[str, str] = {}
        self.added_routes: list[tuple[str, str]] = []
        self.run_input: str | None = None
        self.stopped = False

    @property
    def state(self) -> SimpleNamespace:
        return SimpleNamespace(status=self._status, model_dump=lambda: {"status": self._status})

    def add_route(self, virtual_prefix: str, real_path: str) -> None:
        self.added_routes.append((virtual_prefix, real_path))

    async def run(self, task_input: str) -> SimpleNamespace:
        self.run_input = task_input
        return SimpleNamespace(
            status="completed",
            output="agent result",
            model_dump=lambda: {"status": "completed", "output": "agent result"},
        )

    async def resume(self, decisions: list[Any]) -> SimpleNamespace:
        self.resume_decisions = decisions
        return SimpleNamespace(
            status="completed",
            output="resumed",
            model_dump=lambda: {"status": "completed", "output": "resumed"},
        )

    async def stop(self) -> None:
        self.stopped = True


# ---------------------------------------------------------------------------
# Chat fakes
# ---------------------------------------------------------------------------


class FakeHistory:
    def __init__(self, sessions: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._sessions: dict[str, list[dict[str, Any]]] = dict(sessions or {})

    async def async_list_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    async def async_list_summaries(self, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
        summaries = []
        for sid, msgs in self._sessions.items():
            first_user = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
            summaries.append({
                "session_id": sid,
                "last_ts": "",
                "message_count": len(msgs),
                "title": first_user,
            })
        summaries.sort(key=lambda s: s["last_ts"], reverse=True)
        return summaries[offset:offset + limit] if limit is not None else summaries[offset:]

    async def async_session_summaries_for(self, session_ids: list[str]) -> list[dict[str, Any]]:
        by_id = {s["session_id"]: s for s in await self.async_list_summaries()}
        return [by_id[sid] for sid in session_ids if sid in by_id]

    async def async_load_session(self, sid: str) -> list[dict[str, Any]] | None:
        return self._sessions.get(sid)

    def load_session(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._sessions.get(session_id, []))

    async def async_save_message(self, session_id: str, role: str, content: str) -> None:
        self._sessions.setdefault(session_id, []).append({"role": role, "content": content})


class FakeChat:
    def __init__(self, sessions: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.session_id = "default"
        self.messages: list[dict[str, Any]] = []
        self.history = FakeHistory(sessions)
        self.agents: dict[str, FakeAgentRunner] = {}
        self.sent_inputs: list[str] = []

    def new_session(self) -> str:
        self.session_id = "session_20260803_120000"
        self.messages = []
        return self.session_id

    async def send(self, user_input: str, **kwargs: Any) -> str:
        self.sent_inputs.append(user_input)
        return f"reply:{user_input}"

    async def semantic_search(self, query: str, namespace: str = "messages", limit: int = 5) -> list[dict[str, Any]]:
        return []

    def spawn_agent(self, config: Any) -> FakeAgentRunner:
        runner = FakeAgentRunner(
            name=config.name,
            role=config.role,
            capabilities=list(config.capabilities),
        )
        self.agents[runner.agent_id] = runner
        return runner

    def get_agent(self, agent_id: str) -> FakeAgentRunner | None:
        return self.agents.get(agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": r.agent_id,
                "name": r.config.name,
                "role": r.config.role,
                "capabilities": r.config.capabilities,
                "status": r.state.status,
            }
            for r in self.agents.values()
        ]

    async def stop_agent(self, agent_id: str) -> bool:
        runner = self.agents.get(agent_id)
        if runner is None:
            return False
        await runner.stop()
        return True


# ---------------------------------------------------------------------------
# Store / scheduler fakes
# ---------------------------------------------------------------------------


class FakeStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = {}

    def upsert(self, namespace: str, items: list[dict[str, Any]]) -> None:
        for item in items:
            key = item.get("key")
            if not key:
                continue
            self._data.setdefault(namespace, {})[key] = {
                "key": key,
                "value": item.get("value", {}),
                "namespace": namespace,
                "created_at": "t",
                "updated_at": "t",
            }

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        return self._data.get(namespace, {}).get(key)

    def get_many(self, namespace: str, keys: list[str]) -> list[dict[str, Any]]:
        ns = self._data.get(namespace, {})
        return [ns[k] for k in keys if k in ns]

    def delete(self, namespace: str, keys: list[str]) -> int:
        ns = self._data.get(namespace, {})
        deleted = 0
        for k in keys:
            if k in ns:
                del ns[k]
                deleted += 1
        return deleted

    def search(self, namespace: str, filter_: dict[str, Any] | None = None, limit: int = 10) -> list[dict[str, Any]]:
        ns = self._data.get(namespace, {})
        results = list(ns.values())
        if filter_:
            results = [r for r in results if all(r.get("value", {}).get(k) == v for k, v in filter_.items())]
        return results[:limit]

    def all_items(self, namespace: str) -> list[dict[str, Any]]:
        return list(self._data.get(namespace, {}).values())


class FakeJob:
    def __init__(self, schedule_seconds: int, task_input: str) -> None:
        self.id = "cron_abc"
        self.schedule_seconds = schedule_seconds
        self.task_input = task_input
        self.enabled = True
        self.last_run = 0.0
        self.next_run = 0.0
        self.run_count = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "schedule_seconds": self.schedule_seconds,
            "task_input": self.task_input,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
        }


class FakeScheduler:
    def __init__(self) -> None:
        self._jobs: dict[str, FakeJob] = {}
        self.started_with: Any = None

    def add(self, schedule_seconds: int, task_input: str, thread_id: str | None = None, agent_config: dict[str, Any] | None = None) -> FakeJob:
        job = FakeJob(schedule_seconds, task_input)
        self._jobs[job.id] = job
        return job

    def list_jobs(self) -> list[FakeJob]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> FakeJob | None:
        return self._jobs.get(job_id)

    def remove(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    async def start(self, chat_getter: Any) -> None:
        self.started_with = chat_getter


# ---------------------------------------------------------------------------
# TestClient builders
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def make_client(
    router: APIRouter,
    *,
    patch_target: str,
    chat: Any,
    extra_patches: list[tuple[str, Any]] | None = None,
) -> Iterator[TestClient]:
    """Build a minimal FastAPI app around ``router`` with dependencies patched.

    ``patch_target`` (e.g. ``"vajra_gate.routers.agents._require_chat"``) is
    replaced by an AsyncMock returning ``chat``. ``extra_patches`` is a list of
    ``(target, value)`` pairs patched with ``patch(target, return_value=value)``.
    """
    from unittest.mock import AsyncMock, patch

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: "tester"

    patchers = [
        patch(patch_target, AsyncMock(return_value=chat)),
        *[patch(target, return_value=value) for target, value in (extra_patches or [])],
    ]
    with contextlib.ExitStack() as stack:
        for patcher in patchers:
            stack.enter_context(patcher)
        with TestClient(app) as client:
            yield client
