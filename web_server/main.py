"""Web Server — web search, guarded fetch, and LLM sampling.

Standalone FastMCP server exposing the web tools that were previously served
by ``veda_engine``. Tool implementations live in ``veda_engine.tools.web``
and ``veda_engine.tools.summarize`` (kept canonical so the engine's tests
that monkeypatch ``web_module.socket``/``httpx`` keep working).

Run directly:
    python -m web_server                              # stdio (default)
    python -m web_server --transport sse --port 8103
    python -m web_server --transport streamable-http --port 8203
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from veda_engine.tools.summarize import summarize
from veda_engine.tools.web import web_fetch, web_search

mcp = FastMCP("web-search")

mcp.tool(name="web_search")(web_search)
mcp.tool(name="web_fetch")(web_fetch)
mcp.tool(name="summarize")(summarize)


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Web Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8103)
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
