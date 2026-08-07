from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from mcp_cli.services.agents.interrupts import ActionRequest, DecisionType
from mcp_cli.services.agents.middleware.base import AgentMiddleware
from mcp_cli.services.agents.permissions import FilesystemPermission

_MIDDLEWARE_REGISTRY: dict[str, type[AgentMiddleware]] = {}


def register_middleware(cls: type[AgentMiddleware]) -> type[AgentMiddleware]:
    name = cls.__name__.removesuffix("Middleware")
    name = "".join("_" + c.lower() if c.isupper() else c for c in name).lstrip("_")
    _MIDDLEWARE_REGISTRY[name] = cls
    return cls


def _resolve_middleware(mw_list: list) -> list[AgentMiddleware]:
    resolved: list[AgentMiddleware] = []
    for item in mw_list:
        if isinstance(item, AgentMiddleware):
            resolved.append(item)
        elif isinstance(item, dict):
            item = dict(item)  # shallow copy to avoid mutating original
            type_name = item.pop("type", None)
            if not type_name:
                raise ValueError(f"Middleware dict missing 'type' key: {item}")
            cls = _MIDDLEWARE_REGISTRY.get(type_name)
            if cls is None:
                raise ValueError(
                    f"Unknown middleware type '{type_name}'. "
                    f"Available: {list(_MIDDLEWARE_REGISTRY)}"
                )
            resolved.append(cls(**item))
        else:
            raise ValueError(f"Middleware must be a dict or AgentMiddleware instance, got {type(item).__name__}")
    return resolved


# ---------------------------------------------------------------------------
# Interrupt config helpers
# ---------------------------------------------------------------------------

InterruptOnValue = bool | dict[Literal["allowed_decisions"], list[DecisionType]]


def _normalize_interrupt(val: InterruptOnValue) -> dict:
    if val is True:
        return {"allowed_decisions": ["approve", "edit", "reject"]}
    if isinstance(val, dict):
        return val
    return {"allowed_decisions": ["approve", "edit", "reject"]}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class AgentConfig(BaseModel):
    """Specification for spawning a new agent."""

    name: str
    role: str
    capabilities: list[str] = Field(
        default_factory=list,
        description="Tool capability tags this agent may use (e.g. 'filesystem', 'github')",
    )
    # system_prompt should be provided for registered subagents (empty falls back to role-based default)
    system_prompt: str = ""
    model: str = "default"
    max_iterations: int = Field(default=10, ge=1, le=100)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    token_budget: int = Field(default=0, ge=0, description="Max tokens; 0 = inherit parent")

    # Human-in-the-loop: tool_name -> config
    interrupt_on: dict[str, InterruptOnValue] = Field(
        default_factory=dict,
        description="Tools that require human approval before executing, e.g. {'send_email': True} or {'add_customer': {'allowed_decisions': ['approve', 'edit', 'reject']}}",
    )

    # Per-agent memory: list of file paths (e.g. ['/AGENTS.md', '/notes.md'])
    memory_files: list[str] = Field(
        default_factory=list,
        description="File paths the agent can read/write for persistent memory",
    )

    # Filesystem permissions: allow/deny rules for file operations
    permissions: list[FilesystemPermission] = Field(
        default_factory=list,
        description="Per-operation path-based permissions for file tools",
    )

    # Tool override: when set, replaces the inherited tool set (filesystem builtins still provided)
    tools: list[Any] = Field(
        default_factory=list,
        description="OpenAI-format tool definitions that override the inherited tool set",
    )

    # Middleware pipeline
    middleware: list[Any] = Field(
        default_factory=list,
        description=(
            "Middleware instances or dict specs. "
            "Over REST, pass dicts like: "
            '{"type": "code_interpreter", "timeout": 30}'
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _resolve_middleware_specs(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mw = data.get("middleware")
            if mw and isinstance(mw, list):
                data["middleware"] = _resolve_middleware(mw)
        return data

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------

AgentPhase = Literal["IDLE", "THINKING", "DELEGATING", "EXECUTING", "REPORTING", "DONE"]

PHASES: tuple[str, ...] = ("THINKING", "DELEGATING", "EXECUTING", "REPORTING", "DONE")


class PhaseTransition(BaseModel):
    """A single task-lifecycle phase transition recorded for audit/UI."""

    phase: AgentPhase
    timestamp: datetime
    iteration: int | None = None


class AgentState(BaseModel):
    """Mutable runtime state of a single agent."""

    agent_id: str
    config: AgentConfig
    status: Literal["idle", "running", "waiting", "completed", "failed"]
    created_at: datetime
    last_active: datetime
    current_task_id: str | None = None
    result: dict[str, Any] | None = None
    total_tokens: int = 0
    error: str | None = None

    # Human-in-the-loop: non-None when agent is paused awaiting a decision
    pending_interrupt: list[ActionRequest] | None = None

    # Task lifecycle: fine-grained progress orthogonal to ``status``
    # (IDLE is the initial sentinel; only the five lifecycle phases are emitted)
    phase: AgentPhase = "IDLE"
    phase_transitions: list[PhaseTransition] = Field(default_factory=list)


class AgentResult(BaseModel):
    agent_id: str
    status: Literal["completed", "failed", "waiting"]
    output: str
    total_tokens: int
    duration_seconds: float
    tool_calls_made: int
    error: str | None = None
    pending_interrupt: list[ActionRequest] | None = None
