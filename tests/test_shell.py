from __future__ import annotations

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


async def test_output_truncation_marker(ws_root, monkeypatch):
    monkeypatch.setattr(shell_module, "_OUTPUT_CAP_BYTES", 16)
    out = await run_command('python -c "print(\'x\' * 100)"')
    assert "[output truncated at 16 bytes]" in out
