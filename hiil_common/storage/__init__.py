"""Storage backends shared by H.I.I.L. MCP servers.

Note: the per-user SQLite document store is NOT shared here — its canonical
implementation lives in ``veda_engine.storage.store`` because
``tests/test_veda_store.py`` monkeypatches its module-level ``DB_DIR``. Only
the JSON store (shared with Drishti Engine) lives here.
"""

from __future__ import annotations

from hiil_common.storage import json_store

__all__ = ["json_store"]
