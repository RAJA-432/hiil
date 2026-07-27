from __future__ import annotations

from mcp import ClientSession, types


async def list_tools(session: ClientSession) -> list[types.Tool]:
    result = await session.list_tools()
    return result.tools


async def call_tool(
    session: ClientSession, tool_name: str, tool_input: dict
) -> types.CallToolResult | None:
    return await session.call_tool(tool_name, tool_input)
