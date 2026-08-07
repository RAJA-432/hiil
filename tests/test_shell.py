from __future__ import annotations

import asyncio
import sys

import pytest

import veda_engine.config as config_module
import veda_engine.tools.shell as shell_module
from veda_engine.tools.shell import run_command


@pytest.fixture
def ws_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(shell_module, "WORKSPACE_ROOT", tmp_path)
    return tmp_path


async def test_echo_hello(ws_root):
    out = await run_command("echo hello")
    assert "hello" in out


async def test_non_zero_exit_reports_code_and_stderr(ws_root):
    out = await run_command(
        'python -c "import sys; sys.stderr.write(\'boom\'); sys.exit(3)"'
    )
    assert "[exit code 3]" in out
    assert "boom" in out


async def test_timeout_kills_and_marks(ws_root):
    out = await run_command('python -c "import time; time.sleep(10)"', timeout=1)
    assert "[timeout]" in out


async def test_cwd_traversal_is_denied(ws_root):
    out = await run_command("echo hi", cwd="../")
    assert "[denied]" in out


async def test_dangerous_pattern_is_denied(ws_root):
    out = await run_command("rm -rf /")
    assert "[denied]" in out


@pytest.mark.parametrize("command", [
    "rm --recursive --force .",
    "rm -r -f *",
    "rd /q /s .",
    "rm -rf ~",
    "cd C:\\Users\\rajas && rd . /s /q",
    "del /s /q C:\\*",
    "mkfs.ext4 /dev/sda",
    "shutdown -h now",
    "Remove-Item -Recurse -Force .",
])
async def test_destructive_verbs_are_denied(ws_root, command):
    out = await run_command(command)
    assert "[denied]" in out


@pytest.mark.parametrize("command", [
    "echo a; echo b",
    "echo a && echo b",
    "echo a || echo b",
    "echo a | cat",
    "echo a & echo b",
])
async def test_command_chaining_is_denied(ws_root, command):
    out = await run_command(command)
    assert "[denied]" in out


async def test_cd_escaping_workspace_is_denied(ws_root):
    out = await run_command("cd ..")
    assert "[denied]" in out


async def test_cd_absolute_path_is_denied(ws_root):
    out = await run_command("cd C:\\Users")
    assert "[denied]" in out


async def test_redirect_escaping_workspace_is_denied(ws_root):
    out = await run_command("echo hi > ..\\evil.txt")
    assert "[denied]" in out


async def test_redirect_inside_workspace_is_allowed(ws_root):
    out = await run_command("echo hi > out.txt")
    assert "[denied]" not in out
    assert "hi" in (ws_root / "out.txt").read_text(encoding="utf-8")


async def test_cd_within_workspace_is_allowed(ws_root):
    (ws_root / "sub").mkdir()
    out = await run_command("cd sub")
    assert "[denied]" not in out


async def test_output_truncation_marker(ws_root, monkeypatch):
    monkeypatch.setattr(shell_module, "_OUTPUT_CAP_BYTES", 16)
    out = await run_command('python -c "print(\'x\' * 100)"')
    assert "[output truncated at 16 bytes]" in out


async def test_cwd_not_directory_reports_error(ws_root):
    out = await run_command("echo hi", cwd="nope")
    assert "[error] cwd is not a directory: nope" in out


async def test_generic_error_returns_error_prefix(ws_root, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(shell_module, "_await_exit", boom)
    out = await run_command("echo hi")
    assert out == "[error] kaboom"


async def test_await_exit_kills_process_tree_on_timeout():
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import time; time.sleep(30)",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    timed_out = await shell_module._await_exit(proc, 1)
    assert timed_out is True
    assert proc.returncode is not None
