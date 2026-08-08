"""Media Server — image generation and stock-template search.

Standalone FastMCP server exposing the media tools that were previously part
of ``drishti_engine``. Tool implementations live in
``drishti_engine.tools.media`` (kept canonical so the engine's tests that
monkeypatch ``media.httpx``/``MEDIA_DIR``/``validate_public_http_url`` keep
working); network access is SSRF-guarded via ``hiil_common.utils.ssrf``.

Run directly:
    python -m media_server                           # stdio (default)
    python -m media_server --transport sse --port 8401
    python -m media_server --transport streamable-http --port 8401
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from drishti_engine.tools.media import (
    graphic_art,
    search_template_images,
    search_template_videos,
)

mcp = FastMCP("media")

mcp.tool(name="graphic_art")(graphic_art)
mcp.tool(name="search_template_images")(search_template_images)
mcp.tool(name="search_template_videos")(search_template_videos)


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Media Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8401)
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
