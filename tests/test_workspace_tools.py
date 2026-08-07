from __future__ import annotations

import pytest

import veda_engine.config as config_module
import veda_engine.tools.workspace as workspace_module
from veda_engine.tools.workspace import grep, read_text_batch, read_text_resource


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


async def test_read_resource_returns_full_small_file(ws_root):
    out = await read_text_resource("a.txt")
    assert out == "hello a"


async def test_read_resource_truncates_large_file(ws_root, monkeypatch):
    monkeypatch.setattr(workspace_module, "_MAX_FILE_BYTES", 100)
    (ws_root / "huge.txt").write_text("y" * 10_000, encoding="utf-8")
    out = await read_text_resource("huge.txt")
    assert "y" * 100 in out
    assert "y" * 101 not in out
    assert f"[truncated at {workspace_module._MAX_FILE_BYTES} bytes]" in out


async def test_read_resource_rejects_traversal(ws_root, tmp_path):
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("TOP SECRET", encoding="utf-8")
    out = await read_text_resource("../secret.txt")
    assert "Access denied" in out
    assert "TOP SECRET" not in out


async def test_batch_large_file_truncates_via_stat(ws_root):
    big = workspace_module._MAX_FILE_BYTES + 5_000
    (ws_root / "huge.txt").write_text("z" * big, encoding="utf-8")
    out = await read_text_batch(["huge.txt"])
    assert f"[truncated at {workspace_module._MAX_FILE_BYTES} bytes]" in out
    assert "z" * (workspace_module._MAX_FILE_BYTES + 1) not in out


async def test_grep_finds_match_in_workspace_file(ws_root):
    (ws_root / "notes.txt").write_text("needle in haystack", encoding="utf-8")
    out = await grep("needle")
    assert any("notes.txt" in r and "needle" in r for r in out)


async def test_grep_skips_symlink_escaping_workspace(ws_root):
    outside = ws_root.parent / "secret.txt"
    outside.write_text("TOP SECRET", encoding="utf-8")
    link = ws_root / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    (ws_root / "plain.txt").write_text("no secrets here", encoding="utf-8")
    out = await grep("SECRET")
    assert not any("TOP SECRET" in r for r in out)
