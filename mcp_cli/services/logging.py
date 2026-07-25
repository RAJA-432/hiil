from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path.home() / ".hiil"
_LOG_FILE = _LOG_DIR / "chat.log"
_LOG_FORMAT = "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_LEVEL_MAP: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}

_ROOT: logging.Logger | None = None


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance, initialising the root hiil logger on first call."""
    global _ROOT
    if _ROOT is None:
        _setup()
    return logging.getLogger(name)


def _setup() -> None:
    global _ROOT
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    level = _LEVEL_MAP.get(os.getenv("HIIL_LOG_LEVEL", "").lower())
    if level is None:
        level = logging.DEBUG if os.getenv("HIIL_DEBUG") else logging.WARNING

    # Silence the Python root logger and all 'hiil' child loggers from the console
    # during normal operation to keep the UI clean.
    logging.getLogger().setLevel(logging.ERROR)

    # We will let the file handler capture everything, but the console handler
    # for the 'hiil' logger should only show errors by default.

    _ROOT = logging.getLogger("hiil")
    _ROOT.setLevel(logging.DEBUG)
    _ROOT.handlers.clear()

    file_handler = RotatingFileHandler(
        str(_LOG_FILE),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    _ROOT.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    # Set console level based on environment variables or default to WARNING
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(message)s" if level == logging.DEBUG
        else "[%(levelname)s] %(message)s",
        _DATE_FORMAT if level == logging.DEBUG else "",
    ))
    _ROOT.addHandler(console_handler)

