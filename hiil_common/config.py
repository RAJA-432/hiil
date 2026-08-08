"""Shared configuration for H.I.I.L. MCP servers.

Centralizes env-driven values (workspace root, user id) and dotenv loading so
every server and the gateway agree on the same configuration. The gateway's
``HIIL_WORKSPACE_DIR`` and the engines' ``HIIL_WORKSPACE`` are unified here.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_WORKSPACE_VAR = os.environ.get("HIIL_WORKSPACE") or os.environ.get("HIIL_WORKSPACE_DIR")

WORKSPACE_ROOT: Path = Path(_WORKSPACE_VAR).resolve() if _WORKSPACE_VAR else Path.cwd().resolve()


def workspace_root() -> Path:
    """Resolve the effective workspace root at call time.

    Honors ``HIIL_WORKSPACE`` first, then ``HIIL_WORKSPACE_DIR``, then the
    current working directory. Reads ``WORKSPACE_ROOT`` if the env changed
    after import.
    """
    var = os.environ.get("HIIL_WORKSPACE") or os.environ.get("HIIL_WORKSPACE_DIR")
    if var:
        return Path(var).resolve()
    return Path.cwd().resolve()


def user_id(user: str = "default") -> str:
    """Resolve the effective user id, honoring ``HIIL_USER_ID`` for ``default``."""
    return user if user != "default" else os.environ.get("HIIL_USER_ID", "default")
