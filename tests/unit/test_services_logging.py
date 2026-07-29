import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_cli.services.logging import _LEVEL_MAP, _LOG_FILE, _ROOT, _setup, get_logger


@pytest.fixture(autouse=True)
def reset_logging():
    for h in getattr(_ROOT, "handlers", [])[:]:
        _ROOT.removeHandler(h)
    import mcp_cli.services.logging as m
    m._ROOT = None
    yield
    for k in ["HIIL_LOG_LEVEL", "HIIL_DEBUG"]:
        os.environ.pop(k, None)


@pytest.fixture
def setup_env():
    for k in ["HIIL_LOG_LEVEL", "HIIL_DEBUG"]:
        os.environ.pop(k, None)
    yield
    for k in ["HIIL_LOG_LEVEL", "HIIL_DEBUG"]:
        os.environ.pop(k, None)


def test_get_logger_returns_logger():
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"


def test_get_logger_uses_hiil_namespace():
    logger = get_logger("test")
    assert logger.name == "test"


def test_setup_creates_log_file():
    _setup()
    assert _LOG_FILE.exists()


def test_setup_adds_handlers():
    _setup()
    root = logging.getLogger("hiil")
    handler_types = [type(h).__name__ for h in root.handlers]
    assert "RotatingFileHandler" in handler_types
    assert "StreamHandler" in handler_types


def test_root_logger_level_debug():
    _setup()
    root = logging.getLogger("hiil")
    assert root.level == logging.DEBUG


def test_file_handler_level_debug():
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.handlers.RotatingFileHandler):
            assert h.level == logging.DEBUG
            return
    pytest.fail("RotatingFileHandler not found")


def test_file_handler_encoding():
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.handlers.RotatingFileHandler):
            assert h.encoding == "utf-8"


def test_file_handler_max_bytes():
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.handlers.RotatingFileHandler):
            assert h.maxBytes == 10 * 1024 * 1024
            assert h.backupCount == 5
            return


def test_logger_writes_to_file():
    _setup()
    log_file = _LOG_FILE
    if log_file.exists():
        log_file.write_text("", "utf-8")
    logger = logging.getLogger("hiil.test_write")
    logger.info("test message 12345")
    for h in logging.getLogger("hiil").handlers:
        h.flush()
    assert log_file.exists()
    content = log_file.read_text("utf-8")
    assert "test message 12345" in content


def test_default_level_no_env(setup_env):
    _setup()
    root = logging.getLogger("hiil")
    console_handler = None
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler):
            console_handler = h
            break
    assert console_handler is not None
    assert console_handler.level == logging.WARNING


def test_env_debug_sets_debug_level(setup_env):
    os.environ["HIIL_DEBUG"] = "1"
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler):
            assert h.level == logging.DEBUG
            return


def test_env_log_level_debug(setup_env):
    os.environ["HIIL_LOG_LEVEL"] = "debug"
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler):
            assert h.level == logging.DEBUG
            return


def test_env_log_level_info(setup_env):
    os.environ["HIIL_LOG_LEVEL"] = "info"
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler):
            assert h.level == logging.INFO
            return


def test_env_log_level_warn(setup_env):
    os.environ["HIIL_LOG_LEVEL"] = "warn"
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler):
            assert h.level == logging.WARNING
            return


def test_env_log_level_error(setup_env):
    os.environ["HIIL_LOG_LEVEL"] = "error"
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler):
            assert h.level == logging.ERROR
            return


def test_env_log_level_invalid_defaults_to_warning(setup_env):
    os.environ["HIIL_LOG_LEVEL"] = "invalid"
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler):
            assert h.level == logging.WARNING
            return


def test_console_formatter_with_debug_level(setup_env):
    os.environ["HIIL_LOG_LEVEL"] = "debug"
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler):
            fmt = h.formatter._fmt
            assert "%(asctime)s" in fmt
            return


def test_console_formatter_with_warning_level(setup_env):
    os.environ["HIIL_LOG_LEVEL"] = "warn"
    _setup()
    root = logging.getLogger("hiil")
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler):
            assert "[%(levelname)s] %(message)s" == h.formatter._fmt
            return


def test_logger_returns_same_instance():
    l1 = get_logger("same")
    l2 = get_logger("same")
    assert l1 is l2


def test_get_logger_different_names():
    l1 = get_logger("module_a")
    l2 = get_logger("module_b")
    assert l1 is not l2
    assert l1.name == "module_a"
    assert l2.name == "module_b"


def test_setup_creates_directory():
    import tempfile
    test_dir = Path(tempfile.mkdtemp())
    with patch("mcp_cli.services.logging._LOG_DIR", test_dir):
        with patch("mcp_cli.services.logging._LOG_FILE", test_dir / "chat.log"):
            _setup()
            assert test_dir.exists()
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)


def test_level_map_keys():
    assert _LEVEL_MAP["debug"] == logging.DEBUG
    assert _LEVEL_MAP["info"] == logging.INFO
    assert _LEVEL_MAP["warn"] == logging.WARNING
    assert _LEVEL_MAP["error"] == logging.ERROR


