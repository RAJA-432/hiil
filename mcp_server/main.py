"""
MCP Server – Workspace Search + Document Store + Sampling

Exposes:
1. File system search (search_resources, glob, grep)
2. Document store (read_document, edit_document)
3. Document resources (list_docs, fetch_doc)
4. Root management (list_roots, read_dir)
5. LLM sampling via client (summarize)

Run directly:
    python -m mcp_server.main                           # stdio (default)
    python -m mcp_server.main --transport sse --port 8100
    python -m mcp_server.main --transport streamable-http --port 8200
"""

import argparse

from mcp.server.fastmcp import FastMCP

from mcp_server.resources.documents import fetch_doc, list_docs
from mcp_server.tools.documents import edit_document, format_document, read_document
from mcp_server.tools.roots import list_roots, read_dir
from mcp_server.tools.summarize import summarize
from mcp_server.tools.web import web_fetch, web_search
from mcp_server.tools.workspace import glob, grep, read_text_resource, search_resources

mcp = FastMCP("workspace-search")

mcp.tool(name="search_resources")(search_resources)
mcp.tool(name="glob")(glob)
mcp.tool(name="grep")(grep)
mcp.tool(name="read_text_resource")(read_text_resource)
mcp.tool(name="read_document")(read_document)
mcp.tool(name="edit_document")(edit_document)
mcp.tool(name="format_document")(format_document)
mcp.tool(name="list_roots")(list_roots)
mcp.tool(name="read_dir")(read_dir)
mcp.tool(name="summarize")(summarize)
mcp.tool(name="web_search")(web_search)
mcp.tool(name="web_fetch")(web_fetch)

mcp.resource("docs://documents", mime_type="application/json")(list_docs)
mcp.resource("docs://documents/{doc_id}", mime_type="text/plain")(fetch_doc)


def main():
    parser = argparse.ArgumentParser(description="MCP Workspace Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8100)
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
