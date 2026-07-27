from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from mcp_cli.services.agents.backend import VirtualBackend


@pytest.fixture
def backend():
    return VirtualBackend()


def test_can_handle_file_tools(backend):
    assert backend.can_handle("read_file") is True
    assert backend.can_handle("write_file") is True
    assert backend.can_handle("edit_file") is True
    assert backend.can_handle("list_directory") is True
    assert backend.can_handle("search_files") is True
    assert backend.can_handle("move_file") is True
    assert backend.can_handle("copy_file") is True
    assert backend.can_handle("get_file_info") is True
    assert backend.can_handle("create_directory") is True
    assert backend.can_handle("read_multiple_files") is True
    assert backend.can_handle("directory_tree") is True


def test_cannot_handle_non_file_tools(backend):
    assert backend.can_handle("get_weather") is False
    assert backend.can_handle("send_email") is False
    assert backend.can_handle("") is False


def test_write_and_read_virtual(backend):
    result = backend.handle_tool("write_file", {"path": "/tmp/hello.txt", "content": "world"})
    assert "Written to virtual path" in result
    result = backend.handle_tool("read_file", {"path": "/tmp/hello.txt"})
    assert result == "world"


def test_read_nonexistent_virtual(backend):
    result = backend.handle_tool("read_file", {"path": "/ghost.txt"})
    assert "File not found" in result


def test_read_multiple_files(backend):
    backend.handle_tool("write_file", {"path": "/a.txt", "content": "111"})
    backend.handle_tool("write_file", {"path": "/b.txt", "content": "222"})
    result = backend.handle_tool("read_multiple_files", {"paths": ["/a.txt", "/b.txt"]})
    assert "--- /a.txt ---" in result
    assert "111" in result
    assert "--- /b.txt ---" in result
    assert "222" in result


def test_edit_file_virtual(backend):
    backend.handle_tool("write_file", {"path": "/note.txt", "content": "hello world"})
    result = backend.handle_tool("edit_file", {"path": "/note.txt", "oldString": "hello", "newString": "hi"})
    assert "Edited virtual path" in result
    content = backend.handle_tool("read_file", {"path": "/note.txt"})
    assert content == "hi world"


def test_edit_file_old_string_not_found(backend):
    result = backend.handle_tool("edit_file", {"path": "/note.txt", "oldString": "nope", "newString": "x"})
    assert "oldString not found" in result


def test_list_directory(backend):
    backend.handle_tool("write_file", {"path": "/data/a.txt", "content": "aaa"})
    backend.handle_tool("write_file", {"path": "/data/b.txt", "content": "bbb"})
    result = backend.handle_tool("list_directory", {"path": "/data/"})
    entries = json.loads(result)
    names = [e["name"] for e in entries]
    assert "a.txt" in names
    assert "b.txt" in names


def test_get_file_info_virtual(backend):
    backend.handle_tool("write_file", {"path": "/info.txt", "content": "12345"})
    result = backend.handle_tool("get_file_info", {"path": "/info.txt"})
    info = json.loads(result)
    assert info["size"] == 5
    assert info["type"] == "file"


def test_get_file_info_not_found(backend):
    result = backend.handle_tool("get_file_info", {"path": "/nope.txt"})
    assert "Not found" in result


def test_move_file_virtual(backend):
    backend.handle_tool("write_file", {"path": "/src.txt", "content": "move me"})
    result = backend.handle_tool("move_file", {"source": "/src.txt", "dest": "/dst.txt"})
    assert "Moved virtual" in result
    assert backend.get_file("/src.txt") is None
    assert backend.get_file("/dst.txt") == "move me"


def test_copy_file_virtual(backend):
    backend.handle_tool("write_file", {"path": "/src.txt", "content": "copy me"})
    result = backend.handle_tool("copy_file", {"source": "/src.txt", "dest": "/cpy.txt"})
    assert "Copied virtual" in result
    assert backend.get_file("/src.txt") == "copy me"
    assert backend.get_file("/cpy.txt") == "copy me"


def test_search_files(backend):
    backend.handle_tool("write_file", {"path": "/docs/readme.md", "content": "# Readme"})
    backend.handle_tool("write_file", {"path": "/docs/notes.txt", "content": "notes"})
    result = backend.handle_tool("search_files", {"pattern": "*.md", "root": "/docs/"})
    matches = json.loads(result)
    assert "readme.md" in str(matches)


def test_create_directory_virtual_no_route(backend):
    result = backend.handle_tool("create_directory", {"path": "/newdir/"})
    assert "add a route" in result


def test_add_route_writes_to_real_fs(backend):
    with tempfile.TemporaryDirectory() as tmp:
        backend.add_route("/out/", tmp)
        result = backend.handle_tool("write_file", {"path": "/out/test.txt", "content": "real"})
        assert "Written to" in result
        written = Path(tmp) / "test.txt"
        assert written.read_text(encoding="utf-8") == "real"


def test_route_resolved_read(backend):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "existing.txt").write_text("persisted", encoding="utf-8")
        backend.add_route("/out/", tmp)
        result = backend.handle_tool("read_file", {"path": "/out/existing.txt"})
        assert result == "persisted"


def test_list_virtual_paths(backend):
    backend.handle_tool("write_file", {"path": "/a.txt", "content": "1"})
    backend.handle_tool("write_file", {"path": "/b.txt", "content": "2"})
    assert backend.list_virtual_paths() == ["/a.txt", "/b.txt"]


def test_unknown_tool_returns_none(backend):
    assert backend.handle_tool("unknown_tool", {}) is None


def test_files_property(backend):
    backend.handle_tool("write_file", {"path": "/x.txt", "content": "val"})
    assert backend.files == {"/x.txt": "val"}
