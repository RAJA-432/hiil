from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_cli.services.agents.models import (
    AgentConfig,
    AgentResult,
    AgentState,
    _normalize_interrupt,
)
from mcp_cli.services.agents.permissions import FilesystemPermission


class TestNormalizeInterrupt:
    def test_true_returns_default(self):
        assert _normalize_interrupt(True) == {"allowed_decisions": ["approve", "edit", "reject"]}

    def test_dict_passthrough(self):
        val = {"allowed_decisions": ["approve"]}
        assert _normalize_interrupt(val) is val

    def test_false_like(self):
        assert _normalize_interrupt(False) == {"allowed_decisions": ["approve", "edit", "reject"]}


class TestAgentConfig:
    def test_minimal_config(self):
        cfg = AgentConfig(name="helper", role="assistant")
        assert cfg.name == "helper"
        assert cfg.role == "assistant"
        assert cfg.max_iterations == 10
        assert cfg.timeout_seconds == 300
        assert cfg.token_budget == 0
        assert cfg.memory_files == []
        assert cfg.permissions == []
        assert cfg.middleware == []

    def test_with_all_fields(self):
        perm = FilesystemPermission(operations=["read"], paths=["/tmp/*"], mode="allow")
        cfg = AgentConfig(
            name="coder",
            role="developer",
            capabilities=["filesystem"],
            system_prompt="Be helpful",
            model="gpt-4",
            max_iterations=20,
            timeout_seconds=600,
            token_budget=4000,
            interrupt_on={"write_file": True},
            memory_files=["/AGENTS.md"],
            permissions=[perm],
        )
        assert cfg.capabilities == ["filesystem"]
        assert cfg.interrupt_on == {"write_file": True}
        assert cfg.permissions == [perm]

    def test_max_iterations_clamp(self):
        with pytest.raises(ValidationError):
            AgentConfig(name="x", role="y", max_iterations=0)
        with pytest.raises(ValidationError):
            AgentConfig(name="x", role="y", max_iterations=101)

    def test_timeout_clamp(self):
        with pytest.raises(ValidationError):
            AgentConfig(name="x", role="y", timeout_seconds=0)
        with pytest.raises(ValidationError):
            AgentConfig(name="x", role="y", timeout_seconds=3601)

    def test_token_budget_negative(self):
        with pytest.raises(ValidationError):
            AgentConfig(name="x", role="y", token_budget=-1)


class TestAgentState:
    def test_minimal_state(self):
        cfg = AgentConfig(name="a", role="b")
        state = AgentState(
            agent_id="ag_1",
            config=cfg,
            status="idle",
            created_at="2025-01-01T00:00:00",
            last_active="2025-01-01T00:00:00",
        )
        assert state.agent_id == "ag_1"
        assert state.status == "idle"
        assert state.pending_interrupt is None
        assert state.error is None

    def test_with_interrupt(self):
        from mcp_cli.services.agents.interrupts import ActionRequest

        cfg = AgentConfig(name="a", role="b")
        req = ActionRequest(name="write_file", args={"path": "/x.txt"})
        state = AgentState(
            agent_id="ag_1",
            config=cfg,
            status="waiting",
            created_at="2025-01-01T00:00:00",
            last_active="2025-01-01T00:00:00",
            pending_interrupt=[req],
        )
        assert state.pending_interrupt == [req]

    def test_status_literals(self):
        cfg = AgentConfig(name="a", role="b")
        for s in ("idle", "running", "waiting", "completed", "failed"):
            state = AgentState(
                agent_id="x", config=cfg, status=s,
                created_at="2025-01-01T00:00:00",
                last_active="2025-01-01T00:00:00",
            )
            assert state.status == s

    def test_invalid_status(self):
        cfg = AgentConfig(name="a", role="b")
        with pytest.raises(ValidationError):
            AgentState(
                agent_id="x", config=cfg, status="unknown",
                created_at="2025-01-01T00:00:00",
                last_active="2025-01-01T00:00:00",
            )


class TestAgentResult:
    def test_minimal_result(self):
        r = AgentResult(
            agent_id="ag_1",
            status="completed",
            output="done",
            total_tokens=100,
            duration_seconds=1.5,
            tool_calls_made=3,
        )
        assert r.error is None
        assert r.pending_interrupt is None

    def test_with_error(self):
        r = AgentResult(
            agent_id="ag_1",
            status="failed",
            output="",
            total_tokens=50,
            duration_seconds=0.5,
            tool_calls_made=0,
            error="Something broke",
        )
        assert r.error == "Something broke"

    def test_status_literals(self):
        for s in ("completed", "failed", "waiting"):
            r = AgentResult(
                agent_id="x", status=s, output="", total_tokens=0,
                duration_seconds=0, tool_calls_made=0,
            )
            assert r.status == s

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            AgentResult(
                agent_id="x", status="idle", output="", total_tokens=0,
                duration_seconds=0, tool_calls_made=0,
            )
