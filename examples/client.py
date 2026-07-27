"""
Standalone demo client (does not require the core/ package).

Launches examples/server.py and exercises its tools and resources.
"""

import asyncio
import os
import sys

# Make the project root importable so we can reuse the shared SetuBridge.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from setu_bridge import SetuBridge


async def main() -> None:
    async with SetuBridge(command="python", args=["examples/server.py"]) as client:
        tools = await client.list_tools()
        print("Available tools:", [t.name for t in tools])

        print("\nSearch results:", await client.call_tool(
            "search_resources", {"query": "README"}
        ))

        print("\nread_document(report.pdf):")
        print(await client.call_tool("read_document", {"doc_id": "report.pdf"}))

        print("\nedit_document(plan.md):")
        print(await client.call_tool(
            "edit_document",
            {"doc_id": "plan.md", "old_str": "implementation", "new_str": "deployment"},
        ))

        print("\ndocs://documents:")
        print(await client.read_resource("docs://documents"))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
