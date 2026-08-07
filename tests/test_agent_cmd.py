from __future__ import annotations

import asyncio
from types import SimpleNamespace

import mcp_cli.commands.agent as agent_module
from mcp_cli.services.agents import SUBAGENT_REGISTRY


class _FakeRunner:
    agent_id = "agent_test"

    def __init__(self, config):
        self.config = config

    async def run(self, task: str) -> SimpleNamespace:
        return SimpleNamespace(status="completed", output=f"OUTPUT:{task}")


class _FakeChat:
    def __init__(self):
        self.spawned: list[_FakeRunner] = []

    def spawn_agent(self, config, bus=None) -> _FakeRunner:
        runner = _FakeRunner(config)
        self.spawned.append(runner)
        return runner


def _run(coro):
    return asyncio.run(coro)


def test_agents_lists_registered_subagents():
    chat = _FakeChat()
    out = _run(agent_module.handle_agent_cmd(chat, "agents", "", None))
    assert out.startswith("Registered subagents:")
    for name in SUBAGENT_REGISTRY:
        assert name in out
    assert "capabilities:" in out


def test_agents_lists_memory_files():
    chat = _FakeChat()
    out = _run(agent_module.handle_agent_cmd(chat, "agents", "", None))
    assert "memory:" in out


def test_run_spawns_and_returns_output():
    chat = _FakeChat()
    out = _run(agent_module.handle_agent_cmd(chat, "run", "quote-reviewer hello there", None))
    assert "Running subagent 'quote-reviewer'" in out
    assert "OUTPUT:hello there" in out
    assert len(chat.spawned) == 1
    assert chat.spawned[0].config is SUBAGENT_REGISTRY["quote-reviewer"]


def test_run_requires_two_parts():
    chat = _FakeChat()
    out = _run(agent_module.handle_agent_cmd(chat, "run", "quote-reviewer", None))
    assert out == "Usage: /agent run <name> <task>"
    out = _run(agent_module.handle_agent_cmd(chat, "run", "", None))
    assert out == "Usage: /agent run <name> <task>"
    assert not chat.spawned


def test_run_unknown_subagent():
    chat = _FakeChat()
    out = _run(agent_module.handle_agent_cmd(chat, "run", "nope task", None))
    assert "Unknown subagent 'nope'" in out
    assert not chat.spawned


def test_unknown_registered_subcmd():
    chat = _FakeChat()
    out = _run(agent_module.handle_agent_cmd(chat, "bogus", "x y", None))
    assert out == "Unknown agent sub-command: bogus."
