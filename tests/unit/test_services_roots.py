from __future__ import annotations

from pathlib import Path

from mcp_cli.services.roots import RootsManager


def test_add_root(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    assert len(mgr.roots) == 1
    assert mgr.roots[0] == tmp_path.resolve()


def test_add_root_duplicate_is_silent(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    mgr.add_root(str(tmp_path))
    assert len(mgr.roots) == 1


def test_add_root_non_existent():
    mgr = RootsManager()
    p = str(Path.cwd() / "_nonexistent_dir_for_test")
    mgr.add_root(p)
    assert len(mgr.roots) == 1


def test_init_with_roots(tmp_path):
    mgr = RootsManager(roots=[str(tmp_path)])
    assert len(mgr.roots) == 1


def test_init_with_empty_roots():
    mgr = RootsManager()
    assert mgr.roots == []


def test_init_with_none():
    mgr = RootsManager(roots=None)
    assert mgr.roots == []


def test_roots_returns_copy(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    roots_copy = mgr.roots
    roots_copy.clear()
    assert len(mgr.roots) == 1


def test_list_roots(tmp_path):
    (tmp_path / "sub").mkdir()
    mgr = RootsManager(roots=[str(tmp_path)])
    result = mgr.list_roots()
    assert len(result) == 1
    assert result[0]["path"] == str(tmp_path.resolve())
    assert result[0]["name"] == tmp_path.name


def test_is_path_allowed_inside_root(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    assert mgr.is_path_allowed(tmp_path / "sub" / "file.txt") is True


def test_is_path_allowed_root_itself(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    assert mgr.is_path_allowed(tmp_path) is True


def test_is_path_allowed_outside_root(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    outside = tmp_path.parent / "other"
    assert mgr.is_path_allowed(outside) is False


def test_is_path_allowed_multiple_roots(tmp_path):
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    mgr = RootsManager(roots=[str(d1), str(d2)])
    assert mgr.is_path_allowed(d1 / "x.txt") is True
    assert mgr.is_path_allowed(d2 / "y.txt") is True
    assert mgr.is_path_allowed(tmp_path / "c" / "z.txt") is False


def test_enforce_path_allowed(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    assert mgr.enforce_path(tmp_path / "file.txt") is None


def test_enforce_path_denied(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    err = mgr.enforce_path(tmp_path.parent / "other" / "file.txt", tool_name="write_file")
    assert err is not None
    assert "[denied]" in err
    assert "write_file" in err


def test_enforce_path_no_roots():
    mgr = RootsManager()
    err = mgr.enforce_path("/some/path")
    assert err is not None
    assert "(none configured)" in err


def test_inspect_tool_args_allowed(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    err = mgr.inspect_tool_args("write_file", {"path": str(tmp_path / "out.txt")})
    assert err is None


def test_inspect_tool_args_denied(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    err = mgr.inspect_tool_args("write_file", {"path": str(tmp_path.parent / "out.txt")})
    assert err is not None
    assert "[denied]" in err


def test_inspect_tool_args_non_path_tool():
    mgr = RootsManager()
    err = mgr.inspect_tool_args("get_weather", {"location": "NYC"})
    assert err is None


def test_inspect_tool_args_list_paths(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    paths = [str(tmp_path / "a.txt"), str(tmp_path / "b.txt")]
    err = mgr.inspect_tool_args("read_multiple_files", {"paths": paths})
    assert err is None


def test_inspect_tool_args_list_denied(tmp_path):
    mgr = RootsManager()
    mgr.add_root(str(tmp_path))
    paths = [str(tmp_path / "a.txt"), str(tmp_path.parent / "bad.txt")]
    err = mgr.inspect_tool_args("read_multiple_files", {"paths": paths})
    assert err is not None
    assert "[denied]" in err


def test_extract_paths_with_path_key():
    candidates = RootsManager._extract_paths("write_file", {"path": "/tmp/test.txt"})
    assert len(candidates) == 1
    assert candidates[0] == ("path", "/tmp/test.txt")


def test_extract_paths_with_list():
    items = ["/a.txt", "/b.txt"]
    candidates = RootsManager._extract_paths("read_multiple_files", {"paths": items})
    assert len(candidates) == 2


def test_extract_paths_ignores_empty():
    candidates = RootsManager._extract_paths("write_file", {"path": ""})
    assert len(candidates) == 0


def test_extract_paths_ignores_non_path_tool():
    candidates = RootsManager._extract_paths("get_weather", {"location": "NYC"})
    assert len(candidates) == 0


def test_extract_paths_source_dest_keys():
    candidates = RootsManager._extract_paths("move_file", {"source": "/a.txt", "dest": "/b.txt"})
    keys = {k for k, _ in candidates}
    assert "source" in keys
    assert "dest" in keys


def test_extract_paths_root_key():
    candidates = RootsManager._extract_paths("search_files", {"root": "/search"})
    assert len(candidates) == 1
    assert candidates[0][0] == "root"
