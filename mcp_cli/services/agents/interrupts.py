from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


DecisionType = Literal["approve", "edit", "reject", "respond"]


class ActionRequest(BaseModel):
    name: str
    args: dict[str, Any]
    allowed_decisions: list[DecisionType] = Field(default=["approve", "edit", "reject"])


class InterruptRequest(BaseModel):
    action_requests: list[ActionRequest]


class ResumeDecision(BaseModel):
    type: DecisionType
    edited_action: dict[str, Any] | None = None
    message: str | None = None


class AgentInterrupt(Exception):
    def __init__(
        self,
        action_requests: list[ActionRequest],
    ):
        self.action_requests = action_requests
        super().__init__(f"Agent interrupted: {len(action_requests)} action(s) pending approval")
