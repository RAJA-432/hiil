from __future__ import annotations

import pytest

from mcp_cli.services.agents.backend import VirtualBackend


class TestDeleteFile:
    def test_can_handle_delete_tools(self):
        backend = VirtualBackend()
        assert backend.can_handle("delete_file")
        assert backend.can_handle("delete_directory")

    def test_delete_virtual_file(self):
        backend = VirtualBackend()
        backend.handle_tool("write_file", {"path": "/tmp/a.txt", "content": "hi"})
        out = backend.handle_tool("delete_file", {"path": "/tmp/a.txt"})
        assert "Deleted virtual path" in out
        assert "/tmp/a.txt" not in backend.files

    def test_delete_missing_virtual_file(self):
        backend = VirtualBackend()
        out = backend.handle_tool("delete_file", {"path": "/tmp/nope.txt"})
        assert "File not found" in out

    def test_delete_routed_file(self, tmp_path):
        backend = VirtualBackend()
        backend.add_route("/out/", tmp_path)
        target = tmp_path / "notes.txt"
        target.write_text("data", encoding="utf-8")
        out = backend.handle_tool("delete_file", {"path": "/out/notes.txt"})
        assert "Deleted" in out
        assert not target.exists()

    def test_delete_directory_virtual_removes_nested(self):
        backend = VirtualBackend()
        backend.handle_tool("write_file", {"path": "/proj/a.txt", "content": "1"})
        backend.handle_tool("write_file", {"path": "/proj/sub/b.txt", "content": "2"})
        backend.handle_tool("write_file", {"path": "/other/c.txt", "content": "3"})
        out = backend.handle_tool("delete_directory", {"path": "/proj"})
        assert "2 files" in out
        assert "/proj/a.txt" not in backend.files
        assert "/proj/sub/b.txt" not in backend.files
        assert "/other/c.txt" in backend.files

    def test_delete_directory_routed(self, tmp_path):
        backend = VirtualBackend()
        backend.add_route("/out/", tmp_path)
        d = tmp_path / "sub"
        d.mkdir()
        (d / "x.txt").write_text("x", encoding="utf-8")
        out = backend.handle_tool("delete_directory", {"path": "/out/sub"})
        assert "Deleted directory" in out
        assert not d.exists()

    def test_delete_directory_missing_virtual(self):
        backend = VirtualBackend()
        out = backend.handle_tool("delete_directory", {"path": "/gone"})
        assert "Directory not found" in out

    def test_delete_file_rejects_directory(self, tmp_path):
        backend = VirtualBackend()
        backend.add_route("/out/", tmp_path)
        d = tmp_path / "dir"
        d.mkdir()
        out = backend.handle_tool("delete_file", {"path": "/out/dir"})
        assert "use delete_directory" in out
        assert d.exists()

    @pytest.mark.parametrize("tool", ["delete_file", "delete_directory"])
    def test_unknown_tool_passthrough(self, tool):
        backend = VirtualBackend()
        assert not backend.can_handle("some_other_tool")
