from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mcp_cli.services.agents.memory import AgentMemoryStore, MemoryScope
from mcp_cli.services.agents.middleware.memory import MemoryMiddleware


def _run(coro) -> Any:
    return asyncio.run(coro)


def test_build_memory_block_empty() -> None:
    mw = MemoryMiddleware(memory_files=["/AGENTS.md"])
    assert mw.build_memory_block() == ""


def test_inject_memory_into_system_prompt() -> None:
    mw = MemoryMiddleware(memory_files=["/AGENTS.md"])
    mw._loaded = {"/AGENTS.md": "Use type annotations"}
    messages = [{"role": "system", "content": "Base prompt"}]
    result = mw.before_run(messages)
    assert result[0]["role"] == "system"
    assert "<agent_memory>" in result[0]["content"]
    assert "Use type annotations" in result[0]["content"]


def test_inject_no_duplicate_block() -> None:
    mw = MemoryMiddleware(memory_files=["/AGENTS.md"])
    mw._loaded = {"/AGENTS.md": "content"}
    messages = [{"role": "system", "content": "Base"}]
    first = mw.before_run(messages)
    second = mw.before_run(first)
    assert second[0]["content"].count("<agent_memory>") == 1


def test_load_memory_from_store(tmp_path: Path) -> None:
    store = AgentMemoryStore(tmp_path)
    store.write("agent_1", "/AGENTS.md", "ruff for linting")

    mw = MemoryMiddleware(memory_files=["/AGENTS.md"])
    loaded = _run(mw.load_memory("agent_1", store))
    assert loaded == {"/AGENTS.md": "ruff for linting"}


def test_persist_memory_writes_to_store(tmp_path: Path) -> None:
    store = AgentMemoryStore(tmp_path)
    mw = MemoryMiddleware(memory_files=["/AGENTS.md"], memory_store=store)
    _run(mw.persist_memory("agent_1", "/AGENTS.md", "updated rules"))
    assert store.read("agent_1", "/AGENTS.md") == "updated rules"


def test_memory_scope_namespace_segments() -> None:
    assert MemoryScope.user_in_workspace("acme", "u_123").namespace == ("memory", "acme", "u_123")
    assert MemoryScope.user("u_123").namespace == ("memory", "u_123")
    assert MemoryScope.workspace("acme").namespace == ("memory", "acme")
    assert MemoryScope.assistant("a_1").namespace == ("memory", "a_1")
    assert MemoryScope.assistant_user("a_1", "u_123").namespace == ("memory", "a_1", "u_123")


def test_memory_scope_equality() -> None:
    assert MemoryScope.user_in_workspace("acme", "u_123") == MemoryScope.user_in_workspace("acme", "u_123")
    assert MemoryScope.user("u_123") != MemoryScope.user_in_workspace("acme", "u_123")


def test_namespace_isolation_between_users(tmp_path: Path) -> None:
    store = AgentMemoryStore(tmp_path)
    scope_a = MemoryScope.user("u_a").namespace
    scope_b = MemoryScope.user("u_b").namespace
    store.write("agent_1", "/AGENTS.md", "prefs for A", namespace=scope_a)
    store.write("agent_1", "/AGENTS.md", "prefs for B", namespace=scope_b)
    assert store.read("agent_1", "/AGENTS.md", namespace=scope_a) == "prefs for A"
    assert store.read("agent_1", "/AGENTS.md", namespace=scope_b) == "prefs for B"


def test_middleware_loads_from_namespace(tmp_path: Path) -> None:
    store = AgentMemoryStore(tmp_path)
    scope = MemoryScope.user("u_123")
    store.write("agent_1", "/AGENTS.md", "workspace convention", namespace=scope.namespace)

    mw = MemoryMiddleware(
        memory_files=["/AGENTS.md"],
        memory_store=store,
        memory_scope=scope,
    )
    loaded = _run(mw.load_memory("agent_1"))
    assert loaded == {"/AGENTS.md": "workspace convention"}
