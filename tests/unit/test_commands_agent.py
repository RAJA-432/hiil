import os
import shutil
from unittest.mock import AsyncMock

import pytest

from mcp_cli.commands.agent import handle_agent_cmd


@pytest.fixture
def agent_dir(tmp_path):
    path = tmp_path / ".claude"
    path.mkdir(exist_ok=True)
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield str(path)
    os.chdir(old_cwd)
    if path.exists():
        shutil.rmtree(str(path))


@pytest.mark.asyncio
async def test_create_agent(agent_dir):
    prompt = AsyncMock(return_value="y")
    reply = await handle_agent_cmd(None, "create", "test_agent", prompt)
    assert "created successfully" in reply
    assert os.path.isdir(".claude/agents/agent_test_agent")
    assert os.path.isfile(".claude/agents/agent_test_agent/plan.json")


@pytest.mark.asyncio
async def test_create_agent_missing_name():
    reply = await handle_agent_cmd(None, "create", "", AsyncMock())
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_create_duplicate(agent_dir):
    os.makedirs(".claude/agents/agent_dup", exist_ok=True)
    prompt = AsyncMock(return_value="y")
    reply = await handle_agent_cmd(None, "create", "dup", prompt)
    assert "already exists" in reply


@pytest.mark.asyncio
async def test_list_no_agents(agent_dir):
    reply = await handle_agent_cmd(None, "list", "", AsyncMock())
    assert "No agents" in reply


@pytest.mark.asyncio
async def test_list_with_agents(agent_dir):
    os.makedirs(".claude/agents/agent_foo", exist_ok=True)
    os.makedirs(".claude/agents/agent_bar", exist_ok=True)
    reply = await handle_agent_cmd(None, "list", "", AsyncMock())
    assert "foo" in reply
    assert "bar" in reply


@pytest.mark.asyncio
async def test_search_no_query():
    reply = await handle_agent_cmd(None, "search", "agent_name", AsyncMock())
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_search_no_output(agent_dir):
    os.makedirs(".claude/agents/agent_s1", exist_ok=True)
    reply = await handle_agent_cmd(None, "search", "s1 query", AsyncMock())
    assert "has no output.log" in reply


@pytest.mark.asyncio
async def test_search_with_matches(agent_dir):
    os.makedirs(".claude/agents/agent_s2", exist_ok=True)
    with open(".claude/agents/agent_s2/output.log", "w") as f:
        f.write("line one\nline two error\nline three\n")
    reply = await handle_agent_cmd(None, "search", "s2 error", AsyncMock())
    assert "2:" in reply


@pytest.mark.asyncio
async def test_pause_no_agent():
    reply = await handle_agent_cmd(None, "pause", "", AsyncMock())
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_pause_nonexistent(agent_dir):
    reply = await handle_agent_cmd(None, "pause", "ghost", AsyncMock())
    assert "does not exist" in reply


@pytest.mark.asyncio
async def test_pause_cancelled(agent_dir):
    os.makedirs(".claude/agents/agent_p1", exist_ok=True)
    prompt = AsyncMock(return_value="n")
    reply = await handle_agent_cmd(None, "pause", "p1", prompt)
    assert "cancelled" in reply


@pytest.mark.asyncio
async def test_pause_success(agent_dir):
    os.makedirs(".claude/agents/agent_p2", exist_ok=True)
    os.makedirs(".claude/agents/agent_p2/interrupted", exist_ok=True)
    prompt = AsyncMock(return_value="y")
    reply = await handle_agent_cmd(None, "pause", "p2", prompt)
    assert "paused" in reply.lower()
    assert os.path.isfile(".claude/agents/agent_p2/interrupted/paused.flag")


@pytest.mark.asyncio
async def test_approve_not_paused(agent_dir):
    os.makedirs(".claude/agents/agent_a1", exist_ok=True)
    reply = await handle_agent_cmd(None, "approve", "a1", AsyncMock())
    assert "not paused" in reply


@pytest.mark.asyncio
async def test_approve_success(agent_dir):
    os.makedirs(".claude/agents/agent_a2/interrupted", exist_ok=True)
    with open(".claude/agents/agent_a2/interrupted/paused.flag", "w") as f:
        f.write("paused")
    prompt = AsyncMock(return_value="y")
    reply = await handle_agent_cmd(None, "approve", "a2", prompt)
    assert "approved" in reply.lower()
    assert not os.path.isfile(".claude/agents/agent_a2/interrupted/paused.flag")


@pytest.mark.asyncio
async def test_reject_success(agent_dir):
    os.makedirs(".claude/agents/agent_r1/interrupted", exist_ok=True)
    with open(".claude/agents/agent_r1/interrupted/paused.flag", "w") as f:
        f.write("paused")
    prompt = AsyncMock(side_effect=["bad reason", "y"])
    reply = await handle_agent_cmd(None, "reject", "r1", prompt)
    assert "rejected" in reply.lower()


@pytest.mark.asyncio
async def test_unknown_subcommand():
    reply = await handle_agent_cmd(None, "unknown", "", AsyncMock())
    assert "Unknown" in reply
