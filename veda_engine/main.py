"""
MCP Server — Workspace Search (veda_engine compat).

The workspace tools moved to the standalone ``workspace_server`` package. This
module re-exports its ``mcp``/``main`` so legacy launchers
(``veda_engine.py``, ``examples/server.py``, ``mcp dev veda_engine.py``) keep
working unchanged.

Run directly:
    python -m veda_engine.main                           # stdio (default)
    python -m veda_engine.main --transport sse --port 8102
    python -m veda_engine.main --transport streamable-http --port 8202
"""

from __future__ import annotations

from workspace_server.main import main, mcp

__all__ = ["mcp", "main"]

if __name__ == "__main__":
    main()
