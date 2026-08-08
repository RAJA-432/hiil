"""Memory Server — long-term user preferences.

Standalone FastMCP server exposing the preference tools that were previously
served by ``veda_engine``. Tool implementations live in
``veda_engine.tools.preferences``, backed by ``hiil_common.services.preferences``
(same ``~/.hiil/store/preferences.json`` as the gateway).

Run directly:
    python -m memory_server                          # stdio (default)
    python -m memory_server --transport sse --port 8104
    python -m memory_server --transport streamable-http --port 8204
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from veda_engine.tools.preferences import forget, recall, remember

mcp = FastMCP("memory-store")

mcp.tool(name="remember")(remember)
mcp.tool(name="recall")(recall)
mcp.tool(name="forget")(forget)


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Memory Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8104)
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
