import asyncio
from pathlib import Path

import pytest

try:
    from mcp_server.storage.store import STORE_FILE as _STORE_FILE
    STORE_FILE = _STORE_FILE
except ImportError:
    STORE_FILE = Path(__file__).parents[2] / "mcp_server" / "storage" / "documents_store.json"

_MCP_SERVER_AVAILABLE: bool | None = None


def _check_mcp_server() -> bool:
    global _MCP_SERVER_AVAILABLE
    if _MCP_SERVER_AVAILABLE is not None:
        return _MCP_SERVER_AVAILABLE
    try:
        import mcp_server  # noqa: F401
        _MCP_SERVER_AVAILABLE = True
    except ImportError:
        _MCP_SERVER_AVAILABLE = False
    return _MCP_SERVER_AVAILABLE


def _clean_store():
    """Remove the on-disk store so tests start from hardcoded defaults."""
    if STORE_FILE.exists():
        STORE_FILE.unlink()


def pytest_sessionstart(session):
    _clean_store()


@pytest.fixture(autouse=True)
def clean_store_per_test():
    _clean_store()
    yield
    _clean_store()


@pytest.fixture(autouse=True)
def mcp_subprocess_timeout():
    """Give MCP subprocesses a generous but bounded timeout."""
    import socket
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(30)
    yield
    socket.setdefaulttimeout(old)


@pytest.fixture
def mcp_server_available():
    """Skip test if mcp_server package is not installed."""
    if not _check_mcp_server():
        pytest.skip("mcp_server package not available — install with `pip install -e .`")


def pytest_runtest_makereport(item, call):
    """Force-clean any lingering documents_store.json after a failed test."""
    if call.when == "teardown" and call.excinfo is not None:
        _clean_store()
