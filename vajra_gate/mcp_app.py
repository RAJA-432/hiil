"""
MCP-over-HTTP — wraps hiil's API as MCP tools mounted under ``/mcp``.

Exposes:
- ``hiil_chat`` — send a message, get a reply
- ``hiil_list_threads`` — list all threads/sessions
- ``hiil_get_thread`` — get messages in a thread
- ``hiil_list_agents`` — list running agents
- ``hiil_create_agent`` — spawn a new agent
- ``hiil_run_agent`` — run an agent with input
- Resources for per-skill output schemas (``output-schema://{skill_id}``)
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from vajra_gate.schemas.output_schemas import SKILL_OUTPUT_SCHEMAS

mcp = FastMCP("hiil-mcp")

_CHAT_REF: dict[str, Any] = {}


def set_chat(chat: Any) -> None:
    _CHAT_REF["chat"] = chat


def _chat():
    c = _CHAT_REF.get("chat")
    if c is None:
        raise RuntimeError("Chat not initialized")
    return c


@mcp.tool()
async def hiil_chat(message: str) -> str:
    """Send a message to the hiil assistant and get a reply.

    Args:
        message: The message to send.
    """
    chat = _chat()
    result = await chat.send(message)
    return result


@mcp.tool()
async def hiil_list_threads() -> str:
    """List all conversation threads."""
    import json
    chat = _chat()
    sids = await chat.history.async_list_sessions()
    return json.dumps({"threads": sids}, indent=2)


@mcp.resource("output-schema://{skill_id}")
async def get_output_schema_resource(skill_id: str) -> str:
    """JSON Schema for a skill's expected LLM output format.

    Args:
        skill_id: The skill identifier (e.g. ``data-analyst``, ``code-reviewer``).
    """
    import json
    schema = SKILL_OUTPUT_SCHEMAS.get(skill_id)
    if schema is None:
        raise ValueError(f"No output schema for skill '{skill_id}'")
    return json.dumps(schema.model_dump(), indent=2)


@mcp.resource("output-schema://list")
async def list_output_schemas_resource() -> str:
    """List all available output schemas with their skill IDs."""
    import json
    return json.dumps({
        "schemas": [s.model_dump() for s in SKILL_OUTPUT_SCHEMAS.values()]
    }, indent=2)


@mcp.tool()
async def hiil_get_thread(thread_id: str) -> str:
    """Get all messages in a thread.

    Args:
        thread_id: The thread/session ID.
    """
    import json
    chat = _chat()
    msgs = await chat.history.async_load_session(thread_id)
    if msgs is None:
        return json.dumps({"error": f"Thread '{thread_id}' not found"})
    return json.dumps({"thread_id": thread_id, "messages": msgs}, indent=2)


@mcp.tool()
async def hiil_list_agents() -> str:
    """List all spawned agents and their statuses."""
    import json
    chat = _chat()
    agents = chat.list_agents()
    return json.dumps({"agents": agents}, indent=2)


@mcp.tool()
async def hiil_create_agent(name: str, role: str, capabilities: list[str] | None = None) -> str:
    """Create a new subagent.

    Args:
        name: Human-readable name for the agent.
        role: Role description (e.g. 'data analyst').
        capabilities: Tool capability tags (e.g. ['sqlite', 'read']).
    """
    import json

    from mcp_cli.services.agents import AgentConfig
    chat = _chat()
    config = AgentConfig(
        name=name,
        role=role,
        capabilities=capabilities or [],
    )
    runner = chat.spawn_agent(config)
    return json.dumps({
        "agent_id": runner.agent_id,
        "name": config.name,
        "role": config.role,
        "status": runner.state.status,
    }, indent=2)


@mcp.tool()
async def hiil_run_agent(agent_id: str, task: str) -> str:
    """Run an agent with a task input.

    Args:
        agent_id: The agent ID to run.
        task: The task description for the agent.
    """
    import json
    chat = _chat()
    runner = chat.get_agent(agent_id)
    if runner is None:
        return json.dumps({"error": f"Agent '{agent_id}' not found"})
    result = await runner.run(task)
    return json.dumps({
        "agent_id": agent_id,
        "status": result.status,
        "output": result.output[:500],
        "tool_calls": result.tool_calls_made,
        "duration": result.duration_seconds,
    }, indent=2)
