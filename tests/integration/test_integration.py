from __future__ import annotations

import os

import pytest

from setu_bridge import SetuBridge
from tests.harness import assert_mcp_result, load_cases, run_mcp_setup, run_mcp_teardown

CASES = load_cases("mcp_server_tests.json")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
async def test_mcp_server(case, mcp_server_available):
    action = case["action"]
    saved = run_mcp_setup(case)
    merged_env = {**os.environ, "HIIL_USER_ID": "test"}
    async with SetuBridge(command="python", args=["-m", "veda_engine"], env=merged_env) as client:
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
