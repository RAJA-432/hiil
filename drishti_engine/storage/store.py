"""Thread-safe JSON file store shared by Drishti Engine tool servers.

Re-exported from ``hiil_common.storage.json_store`` (which mirrors the
per-user JSON persistence pattern used by the Setu Bridge calendar/mail
servers). Kept as a module so existing imports
(``drishti_engine.storage.store.JsonStore``) work unchanged.
"""

from __future__ import annotations

from hiil_common.storage.json_store import JsonStore

__all__ = ["JsonStore"]
