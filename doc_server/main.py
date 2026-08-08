"""Document Server — read, edit, and format documents.

Standalone FastMCP server exposing the document-store tools that were
previously served by ``veda_engine``. Tool implementations live in
``veda_engine.tools.documents`` and resources in ``veda_engine.resources.documents``
(kept canonical so the engine's test suite and the gateway's shared SQLite DB
keep working).

Run directly:
    python -m doc_server                              # stdio (default)
    python -m doc_server --transport sse --port 8101
    python -m doc_server --transport streamable-http --port 8201
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from veda_engine.resources.documents import fetch_doc, list_docs
from veda_engine.tools.documents import edit_document, format_document, read_document

mcp = FastMCP("doc-store")

mcp.tool(name="read_document")(read_document)
mcp.tool(name="edit_document")(edit_document)
mcp.tool(name="format_document")(format_document)

mcp.resource("docs://documents", mime_type="application/json")(list_docs)
mcp.resource("docs://documents/{doc_id}", mime_type="text/plain")(fetch_doc)


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Document Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8101)
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
