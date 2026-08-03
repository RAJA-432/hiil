from __future__ import annotations

from pathlib import Path

from mcp_cli.services.agents.memory import AgentMemoryStore


def _counting_read(monkeypatch):
    calls = [0]
    real_read_text = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        calls[0] += 1
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    return calls


def test_snapshot_hashes_reuses_cached_hash(tmp_path, monkeypatch):
    store = AgentMemoryStore(tmp_path)
    store.write("agent_1", "notes.txt", "hello world")
    calls = _counting_read(monkeypatch)

    first = store.snapshot_hashes("agent_1", ["notes.txt"])
    assert calls[0] == 1
    second = store.snapshot_hashes("agent_1", ["notes.txt"])
    assert calls[0] == 1
    assert first == second


def test_snapshot_hashes_rereads_after_write(tmp_path, monkeypatch):
    store = AgentMemoryStore(tmp_path)
    store.write("agent_1", "notes.txt", "v1")
    calls = _counting_read(monkeypatch)

    h1 = store.snapshot_hashes("agent_1", ["notes.txt"])
    store.write("agent_1", "notes.txt", "v2")
    h2 = store.snapshot_hashes("agent_1", ["notes.txt"])
    assert calls[0] == 2
    assert h1["notes.txt"] != h2["notes.txt"]


def test_snapshot_hashes_missing_file_returns_zero(tmp_path):
    store = AgentMemoryStore(tmp_path)
    assert store.snapshot_hashes("agent_1", ["missing.txt"]) == {"missing.txt": 0}


def test_delete_invalidates_cache(tmp_path, monkeypatch):
    store = AgentMemoryStore(tmp_path)
    store.write("agent_1", "notes.txt", "hello")
    calls = _counting_read(monkeypatch)

    store.snapshot_hashes("agent_1", ["notes.txt"])
    assert store.delete("agent_1", "notes.txt") is True
    result = store.snapshot_hashes("agent_1", ["notes.txt"])
    assert calls[0] == 1
    assert result["notes.txt"] == 0


def test_snapshot_hashes_reuses_after_delete_and_recreate(tmp_path, monkeypatch):
    store = AgentMemoryStore(tmp_path)
    store.write("agent_1", "notes.txt", "hello")
    calls = _counting_read(monkeypatch)

    store.snapshot_hashes("agent_1", ["notes.txt"])
    store.delete("agent_1", "notes.txt")
    store.write("agent_1", "notes.txt", "recreated")
    result = store.snapshot_hashes("agent_1", ["notes.txt"])
    assert calls[0] == 2
    assert result["notes.txt"] == hash("recreated")
