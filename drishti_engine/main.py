"""
MCP Server — Consumer Search (Drishti Engine)

Exposes:
1. Flight search (search_flights, search_airports) — deterministic offline mock
2. Healthcare lookup (search_healthcare) — curated educational index
3. Local browser-history search (browser_search, browser_add)

The media tools (graphic_art, search_template_images, search_template_videos)
moved to the standalone ``media_server``.

Run directly:
    python -m drishti_engine.main                           # stdio (default)
    python -m drishti_engine.main --transport sse --port 8400
    python -m drishti_engine.main --transport streamable-http --port 8400
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from drishti_engine.tools.browser_history import browser_add, browser_search
from drishti_engine.tools.flights import search_airports, search_flights
from drishti_engine.tools.healthcare import search_healthcare

mcp = FastMCP("drishti")

mcp.tool(name="search_flights")(search_flights)
mcp.tool(name="search_airports")(search_airports)
mcp.tool(name="search_healthcare")(search_healthcare)
mcp.tool(name="browser_search")(browser_search)
mcp.tool(name="browser_add")(browser_add)


def main() -> None:
    parser = argparse.ArgumentParser(description="Drishti Consumer Search MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8400)
    args = parser.parse_args()
    if args.transport == "sse":
        import uvicorn

        uvicorn.run(mcp.sse_app(), host="127.0.0.1", port=args.port)
    elif args.transport == "streamable-http":
        import uvicorn

        uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
