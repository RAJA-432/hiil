"""Veda Engine package.

Historically re-exported the workspace ``mcp`` instance. The workspace server
now lives in ``workspace_server``; ``veda_engine.main`` re-exports its
``mcp``/``main`` for backwards compatibility. ``mcp`` is exposed lazily here
to avoid a circular import (``workspace_server.main`` imports
``veda_engine.tools.*``, which triggers this package's init).
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"


def __getattr__(name: str) -> Any:
    if name == "mcp":
        from veda_engine.main import mcp

        return mcp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
