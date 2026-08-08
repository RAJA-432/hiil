"""Workspace Server — file search, read, and shell tools.

Standalone FastMCP server exposing the workspace tools that were previously
served by ``veda_engine``. Tool implementations live in
``veda_engine.tools.*`` (kept as the canonical modules so the engine's test
suite that imports them directly keeps working); this package composes them
into one server.

Run directly:
    python -m workspace_server                           # stdio (default)
    python -m workspace_server --transport sse --port 8102
    python -m workspace_server --transport streamable-http --port 8202
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from veda_engine.tools.roots import list_roots, read_dir
from veda_engine.tools.shell import run_command
from veda_engine.tools.workspace import (
    glob,
    grep,
    read_text_batch,
    read_text_resource,
    search_resources,
)

mcp = FastMCP("workspace-search")

mcp.tool(name="search_resources")(search_resources)
mcp.tool(name="glob")(glob)
mcp.tool(name="grep")(grep)
mcp.tool(name="read_text_resource")(read_text_resource)
mcp.tool(name="read_text_batch")(read_text_batch)
mcp.tool(name="list_roots")(list_roots)
mcp.tool(name="read_dir")(read_dir)
mcp.tool(name="run_command")(run_command)


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Workspace Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8102)
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
