"""Veda Engine configuration (re-exported from the shared ``hiil_common``).

Kept as a module so existing imports (``veda_engine.config.WORKSPACE_ROOT``)
and tests that monkeypatch ``config_module.WORKSPACE_ROOT`` keep working.
"""

from __future__ import annotations

from hiil_common.config import WORKSPACE_ROOT, user_id, workspace_root

__all__ = ["WORKSPACE_ROOT", "workspace_root", "user_id"]
