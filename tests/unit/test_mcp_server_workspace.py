import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_server.tools.workspace import glob, grep, read_text_resource, search_resources


@pytest.mark.asyncio
async def test_search_resources_finds_main_py():
    results = await search_resources("main.py")
    assert "main.py" in results or any("main" in r for r in results)


@pytest.mark.asyncio
async def test_search_resources_empty_query():
    results = await search_resources("")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_resources_no_match():
    results = await search_resources("zzzzzzzzzzzzz_nonexistent_zzzzzzzzzzz")
    assert results == []


@pytest.mark.asyncio
async def test_read_text_resource_existing():
    content = await read_text_resource("pyproject.toml")
    assert "[project]" in content


@pytest.mark.asyncio
async def test_read_text_resource_not_found():
    result = await read_text_resource("nonexistent_file_xyz.txt")
    assert "not found" in result


@pytest.mark.asyncio
async def test_read_text_resource_path_traversal_blocked():
    result = await read_text_resource("../etc/passwd")
    assert "denied" in result or "not found" in result


def _make_files(tmp: Path, files: dict[str, str]):
    for name, content in files.items():
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, "utf-8")


@pytest.mark.asyncio
async def test_glob_finds_py_files():
    results = await glob("*.py")
    assert "main.py" in results
    assert "webui.py" in results or "mcp_server.py" in results


@pytest.mark.asyncio
async def test_glob_recursive():
    results = await glob("**/*.py")
    assert any("mcp_cli" in r for r in results)
    assert len(results) > 10


@pytest.mark.asyncio
async def test_glob_no_match():
    assert await glob("*.nonexistent_ext_xyz") == []


@pytest.mark.asyncio
async def test_grep_finds_def():
    results = await grep("def ", "*.py")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_grep_respects_glob():
    py_results = await grep("def ", "*.py")
    md_results = await grep("def ", "*.md")
    assert len(py_results) > len(md_results)


@pytest.mark.asyncio
async def test_grep_no_match():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_files(tmp, {"hello.txt": "hello world"})
        with patch("mcp_server.tools.workspace.WORKSPACE_ROOT", tmp):
            assert await grep("zzz_nonexistent_zzz") == []


@pytest.mark.asyncio
async def test_grep_invalid_regex():
    results = await grep("[invalid")
    assert "Invalid regex" in results[0]


@pytest.mark.asyncio
async def test_glob_and_grep_on_known_files():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_files(tmp, {
            "src/main.py": "def foo():\n    pass\n",
            "src/utils.py": "def bar():\n    return 42\n",
            "README.md": "# Project\n",
        })
        with patch("mcp_server.tools.workspace.WORKSPACE_ROOT", tmp):
            assert set(await glob("*.md")) == {"README.md"}
            py_files = set(await glob("**/*.py"))
            assert "src/main.py" in py_files or "src\\main.py" in py_files
            assert "src/utils.py" in py_files or "src\\utils.py" in py_files
            assert len(py_files) == 2
            assert await glob("*.rs") == []
            results = await grep("def ", "*.py")
            assert len(results) == 2
            assert await grep("nonexistent") == []


@pytest.mark.asyncio
async def test_glob_empty_pattern():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with patch("mcp_server.tools.workspace.WORKSPACE_ROOT", tmp):
            assert await glob("") == []


@pytest.mark.asyncio
async def test_glob_path_traversal():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "safe.txt").write_text("ok", "utf-8")
        with patch("mcp_server.tools.workspace.WORKSPACE_ROOT", tmp):
            assert await glob("../*") == []


@pytest.mark.asyncio
async def test_glob_caps_at_200():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for i in range(250):
            (tmp / f"file_{i}.txt").write_text(str(i), "utf-8")
        with patch("mcp_server.tools.workspace.WORKSPACE_ROOT", tmp):
            assert len(await glob("*")) == 200


@pytest.mark.asyncio
async def test_grep_handles_binary_content():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "binary.bin").write_bytes(b"\x00\x01\x02\xff\xfe")
        (tmp / "text.txt").write_text("hello world", "utf-8")
        with patch("mcp_server.tools.workspace.WORKSPACE_ROOT", tmp):
            results = await grep("hello")
            assert len(results) == 1


@pytest.mark.asyncio
async def test_grep_handles_binary_in_same_file():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "mixed.bin").write_bytes(b"abc\x00def\nline2\n")
        with patch("mcp_server.tools.workspace.WORKSPACE_ROOT", tmp):
            results = await grep("line2")
            assert len(results) == 1


@pytest.mark.asyncio
async def test_grep_caps_at_200():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "big.txt").write_text("\n".join(f"match line {i}" for i in range(250)), "utf-8")
        with patch("mcp_server.tools.workspace.WORKSPACE_ROOT", tmp):
            assert len(await grep("match")) == 200


@pytest.mark.asyncio
async def test_read_text_resource_directory_path():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sub = tmp / "subdir"
        sub.mkdir()
        with patch("mcp_server.tools.workspace.WORKSPACE_ROOT", tmp):
            result = await read_text_resource("subdir")
            assert "not found" in result


@pytest.mark.asyncio
async def test_search_resources_returns_at_most_50():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for i in range(100):
            (tmp / f"match_{i}.txt").write_text("", "utf-8")
        with patch("mcp_server.tools.workspace.WORKSPACE_ROOT", tmp):
            assert len(await search_resources("match")) <= 50
