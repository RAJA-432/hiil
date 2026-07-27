import pytest

from veda_engine.storage.store import reset_store

_MCP_SERVER_AVAILABLE: bool | None = None


def _check_mcp_server() -> bool:
    global _MCP_SERVER_AVAILABLE
    if _MCP_SERVER_AVAILABLE is not None:
        return _MCP_SERVER_AVAILABLE
    try:
        import veda_engine  # noqa: F401
        _MCP_SERVER_AVAILABLE = True
    except ImportError:
        _MCP_SERVER_AVAILABLE = False
    return _MCP_SERVER_AVAILABLE


def _clean_store():
    reset_store("default")
    reset_store("test")


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
    """Skip test if veda_engine package is not installed."""
    if not _check_mcp_server():
        pytest.skip("veda_engine package not available — install with `pip install -e .`")


def pytest_runtest_makereport(item, call):
    """Reset the document store after a failed test."""
    if call.when == "teardown" and call.excinfo is not None:
        _clean_store()
