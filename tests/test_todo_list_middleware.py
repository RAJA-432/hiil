from __future__ import annotations

import json
from typing import Any

from mcp_cli.services.agents.middleware.todo_list import TodoListMiddleware

_VALID_STATUSES = {"pending", "in_progress", "completed"}


def _run(coro) -> Any:
    import asyncio

    return asyncio.run(coro)


def _write(mw: TodoListMiddleware, todos: list[dict[str, Any]]) -> str:
    ok, payload = _run(mw.handle_tool("write_todos", {"todos": todos}))
    assert ok is True
    assert payload is not None
    return payload


class TestTodoListMiddleware:
    def test_register_tool_schema(self) -> None:
        mw = TodoListMiddleware()
        tools = mw.get_extra_tools()
        assert len(tools) == 1

        tool = tools[0]
        assert tool["type"] == "function"
        fn = tool["function"]
        assert fn["name"] == "write_todos"

        params = fn["parameters"]
        assert params["type"] == "object"
        todos = params["properties"]["todos"]
        assert todos["type"] == "array"
        items = todos["items"]
        assert "id" in items["properties"]
        assert items["properties"]["id"]["type"] == "integer"
        assert "title" in items["properties"]
        assert items["properties"]["title"]["type"] == "string"
        status = items["properties"]["status"]
        assert status["type"] == "string"
        assert set(status["enum"]) == _VALID_STATUSES

    def test_write_todos_replaces_list(self) -> None:
        mw = TodoListMiddleware()
        payload = _write(
            mw,
            [
                {"id": 1, "title": "Research", "status": "pending"},
                {"id": 2, "title": "Draft", "status": "in_progress"},
            ],
        )
        data = json.loads(payload)
        assert data["ok"] is True
        assert data["count"] == 2
        assert len(data["todos"]) == 2

        snapshot = mw.snapshot()
        assert len(snapshot) == 2
        assert [t["title"] for t in snapshot] == ["Research", "Draft"]

    def test_write_todos_normalizes_status(self) -> None:
        mw = TodoListMiddleware()
        _write(mw, [{"id": 1, "title": "Weird", "status": "bogus"}])
        snapshot = mw.snapshot()
        assert len(snapshot) == 1
        assert snapshot[0]["status"] == "pending"

    def test_write_todos_normalizes_id_and_title(self) -> None:
        mw = TodoListMiddleware()
        _write(mw, [{"id": "7", "title": 42, "status": "in_progress"}])
        snapshot = mw.snapshot()
        assert snapshot[0]["id"] == 7
        assert snapshot[0]["title"] == "42"

    def test_write_todos_truncates_over_max(self) -> None:
        mw = TodoListMiddleware(max_items=3)
        todos = [
            {"id": i, "title": f"Task {i}", "status": "pending"} for i in range(1, 6)
        ]
        payload = _write(mw, todos)
        assert json.loads(payload)["count"] == 3
        assert len(mw.snapshot()) == 3

    def test_get_todos(self) -> None:
        mw = TodoListMiddleware()
        _write(
            mw,
            [
                {"id": 1, "title": "Research", "status": "pending"},
                {"id": 2, "title": "Draft", "status": "in_progress"},
            ],
        )
        ok, payload = _run(mw.handle_tool("get_todos", {}))
        assert ok is True
        assert payload is not None
        data = json.loads(payload)
        assert [t["title"] for t in data["todos"]] == ["Research", "Draft"]

    def test_before_run_injects_plan_into_system(self) -> None:
        mw = TodoListMiddleware()
        _write(mw, [{"id": 1, "title": "Research", "status": "pending"}])
        result = mw.before_run([{"role": "system", "content": "Base"}])
        assert result[0]["role"] == "system"
        assert "## Task Plan" in result[0]["content"]
        assert "Research" in result[0]["content"]

    def test_before_run_no_todos_unchanged(self) -> None:
        mw = TodoListMiddleware()
        result = mw.before_run([{"role": "system", "content": "Base"}])
        assert result[0]["content"] == "Base"

    def test_before_run_creates_system_if_missing(self) -> None:
        mw = TodoListMiddleware()
        _write(mw, [{"id": 1, "title": "Research", "status": "pending"}])
        result = mw.before_run([{"role": "user", "content": "hi"}])
        assert result[0]["role"] == "system"
        assert "## Task Plan" in result[0]["content"]

    def test_update_status(self) -> None:
        mw = TodoListMiddleware()
        _write(mw, [{"id": 1, "title": "Research", "status": "pending"}])
        assert mw.update_status(1, "completed") is True
        assert mw.snapshot()[0]["status"] == "completed"
        assert mw.update_status(99, "completed") is False

    def test_update_status_rejects_invalid_status(self) -> None:
        mw = TodoListMiddleware()
        _write(mw, [{"id": 1, "title": "Research", "status": "pending"}])
        assert mw.update_status(1, "bogus") is False
        assert mw.snapshot()[0]["status"] == "pending"

    def test_unknown_tool_unhandled(self) -> None:
        mw = TodoListMiddleware()
        assert _run(mw.handle_tool("foo", {})) == (False, None)

    def test_snapshot_returns_copy(self) -> None:
        mw = TodoListMiddleware()
        _write(mw, [{"id": 1, "title": "Research", "status": "pending"}])
        snapshot = mw.snapshot()
        snapshot[0]["title"] = "Mutated"
        assert mw.snapshot()[0]["title"] == "Research"
