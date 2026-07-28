from __future__ import annotations

from mcp_cli.services.agents.interrupts import (
    ActionRequest,
    AgentInterruptError,
    InterruptRequest,
    ResumeDecision,
)


class TestActionRequest:
    def test_default_allowed_decisions(self):
        req = ActionRequest(name="send_email", args={"to": "a@b.com"})
        assert req.allowed_decisions == ["approve", "edit", "reject"]

    def test_custom_allowed_decisions(self):
        req = ActionRequest(
            name="delete_user",
            args={"user_id": 42},
            allowed_decisions=["approve", "reject"],
        )
        assert req.allowed_decisions == ["approve", "reject"]


class TestResumeDecision:
    def test_minimal(self):
        d = ResumeDecision(type="approve")
        assert d.type == "approve"
        assert d.edited_action is None
        assert d.message is None

    def test_with_edited_action(self):
        d = ResumeDecision(type="edit", edited_action={"name": "write_file", "args": {"path": "/x.txt"}})
        assert d.type == "edit"
        assert d.edited_action["name"] == "write_file"

    def test_with_message(self):
        d = ResumeDecision(type="reject", message="Not needed")
        assert d.message == "Not needed"


class TestInterruptRequest:
    def test_action_requests_list(self):
        reqs = [ActionRequest(name="tool_a", args={}), ActionRequest(name="tool_b", args={})]
        ir = InterruptRequest(action_requests=reqs)
        assert len(ir.action_requests) == 2


class TestAgentInterruptError:
    def test_exception_with_requests(self):
        reqs = [ActionRequest(name="rm_rf", args={})]
        exc = AgentInterruptError(action_requests=reqs)
        assert exc.action_requests is reqs
        assert "pending approval" in str(exc)

    def test_exception_multiple_requests(self):
        reqs = [
            ActionRequest(name="tool_a", args={}),
            ActionRequest(name="tool_b", args={}),
        ]
        exc = AgentInterruptError(action_requests=reqs)
        assert "2 action(s)" in str(exc)
