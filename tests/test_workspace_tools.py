from __future__ import annotations

import pytest

import veda_engine.config as config_module
import veda_engine.tools.workspace as workspace_module
from veda_engine.tools.workspace import read_text_batch


@pytest.fixture
def ws_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(workspace_module, "WORKSPACE_ROOT", tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "a.txt").write_text("hello a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("hello b", encoding="utf-8")
    (tmp_path / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    return tmp_path


async def test_happy_path_reads_multiple_files(ws_root):
    out = await read_text_batch(["a.txt", "b.txt", "src/main.py"])
    assert out == (
        "=== a.txt ===\n"
        "hello a\n"
        "\n"
        "=== b.txt ===\n"
        "hello b\n"
        "\n"
        "=== src/main.py ===\n"
        "print('hello')\n"
        "\n"
    )


async def test_missing_file_reports_inline_error(ws_root):
    out = await read_text_batch(["a.txt", "nope.txt", "b.txt"])
    assert "=== a.txt ===" in out
    assert "=== b.txt ===" in out
    assert "Resource not found: nope.txt" in out
    assert out.index("Resource not found: nope.txt") < out.index("=== b.txt ===")


async def test_path_traversal_is_denied_inline(ws_root, tmp_path):
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("TOP SECRET", encoding="utf-8")
    out = await read_text_batch(["a.txt", "../secret.txt"])
    assert "=== a.txt ===" in out
    assert "Access denied: ../secret.txt" in out
    assert "TOP SECRET" not in out


async def test_per_file_truncation(ws_root, monkeypatch):
    monkeypatch.setattr(workspace_module, "_MAX_FILE_BYTES", 10)
    (ws_root / "big.txt").write_text("x" * 100, encoding="utf-8")
    out = await read_text_batch(["big.txt"])
    assert "=== big.txt ===\n" in out
    assert "x" * 10 in out
    assert "x" * 11 not in out
    assert f"[truncated at {workspace_module._MAX_FILE_BYTES} bytes]" in out


async def test_empty_list_returns_empty_string():
    assert await read_text_batch([]) == ""


async def test_batch_file_count_cap(ws_root, monkeypatch):
    monkeypatch.setattr(workspace_module, "_MAX_BATCH_FILES", 1)
    out = await read_text_batch(["a.txt", "b.txt"])
    assert "=== a.txt ===" in out
    assert "b.txt" not in out


async def test_batch_byte_cap_truncates_output(ws_root, monkeypatch):
    monkeypatch.setattr(workspace_module, "_MAX_BATCH_BYTES", 100)
    (ws_root / "big_a.txt").write_text("A" * 40, encoding="utf-8")
    (ws_root / "big_b.txt").write_text("B" * 40, encoding="utf-8")
    out = await read_text_batch(["big_a.txt", "big_b.txt"])
    assert "=== big_a.txt ===" in out
    assert "big_b.txt" not in out
    assert f"[batch truncated at {workspace_module._MAX_BATCH_BYTES} bytes total]" in out
