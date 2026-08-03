from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from mcp_cli.config import load_settings
from mcp_cli.services.discovery import DiscoveryTracker
from mcp_cli.services.roots import RootsManager
from mcp_cli.services.tool_router import ToolRouter
from mcp_cli.services.tool_runner import ToolRunner


class _FakeBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeCallResult:
    def __init__(self, text: str = "tool output"):
        self.content = [_FakeBlock(text)]


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, args: dict[str, Any]) -> _FakeCallResult:
        self.calls.append((name, args))
        return _FakeCallResult(f"result from {name}")


class _FakeCall:
    def __init__(self, name: str, args: str = "{}", call_id: str = "call_1"):
        self.id = call_id
        self.function = SimpleNamespace(name=name, arguments=args)


class _FakeStrClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        self.calls.append((name, args))
        return f"result from {name}"


def _runner(
    mode: str = "off",
    *,
    names: tuple[str, ...] = ("write_file",),
) -> tuple[ToolRunner, _FakeClient, DiscoveryTracker]:
    client = _FakeClient()
    tracker = DiscoveryTracker(mode)
    runner = ToolRunner(
        tools_by_name={name: {"client": client} for name in names},
        roots_manager=RootsManager(["."]),
        discovery=tracker,
    )
    return runner, client, tracker


def _router(
    mode: str = "off",
    *,
    names: tuple[str, ...] = ("write_file", "read_text_resource"),
) -> tuple[ToolRouter, _FakeStrClient, DiscoveryTracker]:
    client = _FakeStrClient()
    tracker = DiscoveryTracker(mode)
    router = ToolRouter(
        tools_by_name={name: {"client": client} for name in names},
        clients={"filesystem": client},
        capabilities=["filesystem"],
        discovery=tracker,
    )
    return router, client, tracker


async def test_off_mode_write_to_unseen_path_executes_normally():
    runner, client, _ = _runner("off")
    results = await runner.execute_tool_calls([_FakeCall("write_file", '{"path": "unseen.txt"}')])
    assert client.calls == [("write_file", {"path": "unseen.txt"})]
    assert "result from write_file" in results[0]["content"]
    assert "[discovery]" not in results[0]["content"]


async def test_block_mode_write_to_unseen_path_is_short_circuited():
    runner, client, _ = _runner("block")
    results = await runner.execute_tool_calls([_FakeCall("write_file", '{"path": "unseen.txt"}')])
    assert client.calls == []
    assert "[discovery]" in results[0]["content"]
    assert "unseen.txt" in results[0]["content"]


async def test_block_mode_read_then_write_same_path_allowed():
    runner, client, _ = _runner("block", names=("write_file", "read_text_resource"))
    await runner.execute_tool_calls([_FakeCall("read_text_resource", '{"path": "notes.txt"}')])
    results = await runner.execute_tool_calls([_FakeCall("write_file", '{"path": "notes.txt"}')])
    assert client.calls[-1] == ("write_file", {"path": "notes.txt"})
    assert "result from write_file" in results[0]["content"]
    assert "[discovery]" not in results[0]["content"]


async def test_block_mode_edit_document_blocked_until_read():
    runner, client, _ = _runner("block", names=("edit_document", "read_document"))
    blocked = await runner.execute_tool_calls([_FakeCall("edit_document", '{"doc_id": "notes.md"}')])
    assert client.calls == []
    assert "[discovery]" in blocked[0]["content"]

    await runner.execute_tool_calls([_FakeCall("read_document", '{"doc_id": "notes.md"}')])
    allowed = await runner.execute_tool_calls([_FakeCall("edit_document", '{"doc_id": "notes.md"}')])
    assert client.calls[-1] == ("edit_document", {"doc_id": "notes.md"})
    assert "[discovery]" not in allowed[0]["content"]


async def test_warn_mode_executes_but_annotates_result():
    runner, client, _ = _runner("warn")
    results = await runner.execute_tool_calls([_FakeCall("write_file", '{"path": "unseen.txt"}')])
    assert client.calls == [("write_file", {"path": "unseen.txt"})]
    assert "result from write_file" in results[0]["content"]
    assert "[discovery]" in results[0]["content"]


async def test_router_block_mode_write_to_unseen_path_short_circuits():
    router, client, _ = _router("block")
    result = await router.call_tool("write_file", {"path": "unseen.txt"})
    assert client.calls == []
    assert "[discovery]" in result
    assert "unseen.txt" in result


async def test_router_block_mode_read_then_write_same_path_allowed():
    router, client, _ = _router("block")
    await router.call_tool("read_text_resource", {"path": "notes.txt"})
    result = await router.call_tool("write_file", {"path": "notes.txt"})
    assert client.calls[-1] == ("write_file", {"path": "notes.txt"})
    assert result == "result from write_file"
    assert "[discovery]" not in result


async def test_router_warn_mode_executes_but_annotates_result():
    router, client, _ = _router("warn")
    result = await router.call_tool("write_file", {"path": "unseen.txt"})
    assert client.calls == [("write_file", {"path": "unseen.txt"})]
    assert result.startswith("[discovery]")
    assert "result from write_file" in result


async def test_router_off_mode_identical_to_current():
    router, client, _ = _router("off")
    result = await router.call_tool("write_file", {"path": "unseen.txt"})
    assert client.calls == [("write_file", {"path": "unseen.txt"})]
    assert result == "result from write_file"
    assert "[discovery]" not in result


def test_record_dedupes_and_normalizes_path_keys():
    tracker = DiscoveryTracker("block")
    tracker.record("read_text_resource", {"path": "src/foo.txt"})
    tracker.record("read_text_resource", {"path": "src/./foo.txt"})
    tracker.record("read_text_resource", {"path": "./src/foo.txt"})
    assert len(tracker.observed) == 1
    assert tracker.check("write_file", {"path": "src/foo.txt"}) is None


def test_pattern_and_doc_id_keys_recorded_as_is():
    tracker = DiscoveryTracker("block")
    tracker.record("grep", {"pattern": "TODO"})
    tracker.record("glob", {"pattern": "**/*.py"})
    tracker.record("search_resources", {"query": "report"})
    tracker.record("read_document", {"doc_id": "docs/plan.md"})
    assert tracker.observed == {"TODO", "**/*.py", "report", "docs/plan.md"}


def test_invalid_mode_rejected():
    with pytest.raises(ValueError, match="discovery"):
        DiscoveryTracker("banana")


def test_load_settings_parses_discovery_guard(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("settings:\n  provider: ollama\n  model: m\n  api_key: ''\n  discovery_guard: warn\n")
    settings, _ = load_settings(str(cfg))
    assert settings.discovery_guard == "warn"


def test_load_settings_rejects_invalid_discovery_guard(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("settings:\n  provider: ollama\n  model: m\n  api_key: ''\n  discovery_guard: nah\n")
    with pytest.raises(ValueError, match="discovery_guard"):
        load_settings(str(cfg))
