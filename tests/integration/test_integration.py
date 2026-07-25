from __future__ import annotations

import pytest
from mcp import types

from mcp_client import MCPClient
from tests.harness import load_cases, assert_mcp_result, run_mcp_setup, run_mcp_teardown

CASES = load_cases("mcp_server_tests.json")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
async def test_mcp_server(case, mcp_server_available):
    action = case["action"]
    saved = run_mcp_setup(case)
    async with MCPClient(command="python", args=["-m", "mcp_server"]) as client:
        if action == "list_tools":
            result = await client.list_tools()
        elif action == "list_resources":
            result = await client.list_resources()
        elif action == "read_resource":
            result = await client.read_resource(case["uri"])
        elif action == "call_tool":
            result = await client.call_tool(case["tool"], case.get("args", {}))
        else:
            pytest.fail(f"Unknown action: {action}")
        assert_mcp_result(case, result)
    run_mcp_teardown(case, saved)
