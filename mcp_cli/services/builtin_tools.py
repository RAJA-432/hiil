from __future__ import annotations

import contextlib
import contextvars
from typing import Any, Callable

from mcp_cli.services.agents.models import AgentConfig
from mcp_cli.services.agents.subagents import GENERAL_PURPOSE, SUBAGENT_REGISTRY
from mcp_cli.services.logging import get_logger

logger = get_logger("builtin_tools")

_MAX_RESULT_CHARS = 4000
_MAX_DELEGATION_DEPTH = 3

_delegation_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "delegation_depth", default=0
)


def _clip(text: str, limit: int = _MAX_RESULT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _resolve_config(
    agent_name: str, role: str, capabilities: list[str],
) -> AgentConfig | None:
    if agent_name:
        config = SUBAGENT_REGISTRY.get(agent_name)
        if config is not None:
            return config
        if not role:
            return GENERAL_PURPOSE
        return None
    if role:
        return AgentConfig(
            name=role.strip().replace(" ", "-").lower(),
            role=role,
            capabilities=[str(c) for c in capabilities],
        )
    return GENERAL_PURPOSE


def _agent_error(agent_name: str) -> str:
    if agent_name:
        available = ", ".join(sorted(SUBAGENT_REGISTRY))
        return f"[error] Unknown subagent '{agent_name}'. Available agents: {available}"
    return "[error] Either 'agent' (registered subagent) or 'role' (dynamic subagent) is required."


@contextlib.asynccontextmanager
async def _push_depth():
    token = _delegation_depth.set(_delegation_depth.get() + 1)
    try:
        yield
    finally:
        _delegation_depth.reset(token)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def _delegate_task(chat: Any, args: dict[str, Any]) -> str:
    agent_name = (args.get("agent") or "").strip()
    task = (args.get("task") or "").strip()
    role = (args.get("role") or "").strip()
    capabilities = args.get("capabilities") or []

    if not task:
        return "[error] delegate_task requires a non-empty 'task'."
    config = _resolve_config(agent_name, role, capabilities)
    if config is None:
        return _agent_error(agent_name)
    if _delegation_depth.get() >= _MAX_DELEGATION_DEPTH:
        return f"[error] delegation depth exceeded ({_MAX_DELEGATION_DEPTH})."

    async with _push_depth():
        runner = chat.spawn_agent(config)
        logger.info(
            "Delegating task to subagent '%s' (%s)", config.name, runner.agent_id,
        )
        result = await runner.run(task)

    status = getattr(result, "status", "completed")
    output = getattr(result, "output", "") or ""
    return (
        f"[delegated to {config.name} ({getattr(runner, 'agent_id', '')})] "
        f"status={status}\n{_clip(output)}"
    )


async def _delegate_parallel(chat: Any, args: dict[str, Any]) -> str:
    delegations = args.get("delegations") or []
    if not delegations:
        return "[error] delegate_parallel requires a non-empty 'delegations' list."
    if _delegation_depth.get() >= _MAX_DELEGATION_DEPTH:
        return f"[error] delegation depth exceeded ({_MAX_DELEGATION_DEPTH})."

    items: list[tuple[AgentConfig, str]] = []
    labels: list[str] = []
    for d in delegations:
        if not isinstance(d, dict):
            return "[error] Each delegation must be an object with a 'task'."
        agent_name = (d.get("agent") or "").strip()
        task = (d.get("task") or "").strip()
        role = (d.get("role") or "").strip()
        capabilities = d.get("capabilities") or []
        if not task:
            return "[error] Each delegation requires a non-empty 'task'."
        config = _resolve_config(agent_name, role, capabilities)
        if config is None:
            return _agent_error(agent_name)
        items.append((config, task))
        labels.append(config.name)

    async with _push_depth():
        results = await chat.parallel_spawn(items)

    parts: list[str] = []
    for (config, _task), (agent_id, result) in zip(items, results):
        status = getattr(result, "status", "completed")
        output = getattr(result, "output", "") or ""
        parts.append(
            f"[delegated to {config.name} ({agent_id})] status={status}\n{_clip(output)}"
        )
    return "\n\n---\n\n".join(parts)


_HANDLERS: dict[str, Callable[[Any, dict[str, Any]], Any]] = {
    "delegate_task": _delegate_task,
    "delegate_parallel": _delegate_parallel,
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_AGENT_REF_PROPERTIES: dict[str, Any] = {
    "agent": {
        "type": "string",
        "description": (
            "Name of a registered subagent to delegate to (e.g. 'chinook-analyst'). "
            "Required unless 'role' is provided."
        ),
    },
    "task": {"type": "string", "description": "The task to delegate to the subagent."},
    "role": {
        "type": "string",
        "description": "Optional role to create a one-off dynamic subagent (used when 'agent' is omitted).",
    },
    "capabilities": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Tool capabilities for a dynamic subagent (e.g. 'sqlite', 'read').",
    },
}

BUILTIN_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {    "delegate_task": {
        "type": "function",
        "function": {
            "name": "delegate_task",
            "description": (
                "Delegate a task to a subagent and return its result. The subagent runs "
                "with its own system prompt, memory files, and capability-filtered tools. "
                "Use when a task fits a specialized subagent better than the current agent."
            ),
            "parameters": {
                "type": "object",
                "properties": dict(_AGENT_REF_PROPERTIES),
                "required": ["task"],
            },
        },
    },
    "delegate_parallel": {
        "type": "function",
        "function": {
            "name": "delegate_parallel",
            "description": (
                "Delegate multiple tasks to subagents concurrently. Use for independent "
                "work that can be fanned out (e.g. one researcher per newsletter genre). "
                "Returns each subagent's result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "delegations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": dict(_AGENT_REF_PROPERTIES),
                            "required": ["task"],
                        },
                        "description": "List of tasks to delegate in parallel.",
                    },
                },
                "required": ["delegations"],
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Client + registry
# ---------------------------------------------------------------------------

_DELEGATE_TOOLS = frozenset(BUILTIN_TOOL_SCHEMAS)


class BuiltinToolClient:
    """MCP-shaped client that dispatches builtin tools to in-process handlers.

    Exposes ``script`` so ``ToolRouter`` can tag builtin tools with a
    ``"builtin"`` capability, and ``call_tool`` so both ``ToolRunner`` (main
    chat) and ``ToolRouter`` (subagents) can execute them without a server.
    """

    script = "builtin"

    def __init__(self, chat: Any):
        self._chat = chat

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        handler = _HANDLERS.get(name)
        if handler is None:
            return f"[error] Unknown builtin tool '{name}'."
        try:
            return await handler(self._chat, args)
        except Exception as exc:
            logger.exception("builtin tool '%s' failed", name)
            return f"[error] builtin tool '{name}' failed: {exc}"


class BuiltinTools:
    """Registers builtin (non-MCP) tools into a chat's tool registry."""

    def __init__(self, chat: Any):
        self._chat = chat
        self._client = BuiltinToolClient(chat)

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return list(BUILTIN_TOOL_SCHEMAS.values())

    def register(self, tools_by_name: dict[str, dict[str, Any]]) -> None:
        for name, schema in BUILTIN_TOOL_SCHEMAS.items():
            tools_by_name[name] = {"client": self._client, "openai": schema}
