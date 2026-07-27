from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mcp_cli.services.agents.memory import AgentMemoryStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        yield AgentMemoryStore(tmp)


def test_write_and_read(store):
    store.write("agent_1", "/notes.md", "hello world")
    assert store.read("agent_1", "/notes.md") == "hello world"


def test_read_nonexistent(store):
    assert store.read("agent_1", "/ghost.md") is None


def test_write_creates_parent_dirs(store):
    store.write("agent_2", "/deep/nested/file.txt", "content")
    assert store.read("agent_2", "/deep/nested/file.txt") == "content"


def test_delete_existing(store):
    store.write("agent_1", "/tmp.txt", "delete me")
    assert store.delete("agent_1", "/tmp.txt") is True
    assert store.read("agent_1", "/tmp.txt") is None


def test_delete_nonexistent(store):
    assert store.delete("agent_1", "/ghost.txt") is False


def test_list_files_returns_sorted(store):
    store.write("agent_x", "/a.txt", "aaa")
    store.write("agent_x", "/b.txt", "bbb")
    files = store.list_files("agent_x")
    assert len(files) == 2
    assert files[0]["path"] == "a.txt"


def test_list_files_empty_for_unknown_agent(store):
    assert store.list_files("ghost") == []


def test_load_all_returns_existing(store):
    store.write("a1", "/mem.md", "memory content")
    result = store.load_all("a1", ["/mem.md", "/nonexistent.md"])
    assert result == {"/mem.md": "memory content"}


def test_load_all_empty_when_none_exist(store):
    result = store.load_all("a1", ["/a.md", "/b.md"])
    assert result == {}


def test_snapshot_hashes(store):
    store.write("a1", "/x.md", "data")
    hashes = store.snapshot_hashes("a1", ["/x.md", "/y.md"])
    assert hashes["/x.md"] == hash("data")
    assert hashes["/y.md"] == 0


def test_path_traversal_blocked(store):
    with pytest.raises(ValueError, match="Path traversal"):
        store._agent_path("agent_1", "../../etc/passwd")


def test_different_agents_isolated(store):
    store.write("alice", "/note.md", "alice data")
    store.write("bob", "/note.md", "bob data")
    assert store.read("alice", "/note.md") == "alice data"
    assert store.read("bob", "/note.md") == "bob data"
