from __future__ import annotations

import asyncio
import sqlite3
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor

from mcp_cli.services.logging import get_logger

logger = get_logger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=8)


def asyncify(method_name: str):
    """Decorator that generates an async wrapper calling a sync method via run_in_executor."""
    def decorator(sync_method):
        async def wrapper(self, *args, **kwargs):
            loop = asyncio.get_running_loop()
            sync_fn = getattr(self, method_name)
            return await loop.run_in_executor(_EXECUTOR, lambda: sync_fn(*args, **kwargs))
        wrapper.__name__ = sync_method.__name__
        wrapper.__qualname__ = sync_method.__qualname__
        return wrapper
    return decorator


class SqliteStore:
    _SCHEMA: list[str] = []

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = sqlite3.connect(db_path, check_same_thread=False)
        conn = self._get_conn()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA cache_size=-20000")
        self._init_db()
        self._finalizer = weakref.finalize(self, self.__class__._close_conn, self._conn, self._lock)

    def _get_conn(self) -> sqlite3.Connection:
        assert self._conn is not None
        return self._conn

    def _init_db(self):
        for stmt in self._SCHEMA:
            self._get_conn().execute(stmt)
        self._get_conn().commit()

    def close(self):
        if hasattr(self, "_finalizer"):
            self._finalizer()
        self._conn = None

    @staticmethod
    def _close_conn(conn: sqlite3.Connection | None, lock: threading.Lock) -> None:
        if conn is None:
            return
        with lock:
            try:
                conn.close()
            except Exception:
                logger.warning("Failed to close database connection")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
