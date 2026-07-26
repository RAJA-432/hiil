from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    import win32crypt

from mcp_cli.services.logging import get_logger

logger = get_logger(__name__)

try:
    from cryptography.fernet import Fernet
    from cryptography.fernet import InvalidToken as FernetInvalidToken
except ImportError:
    Fernet = None  # type: ignore[assignment, misc]
    FernetInvalidToken = None  # type: ignore[assignment, misc]

_CRED_DIR = Path.home() / ".hiil"
_CRED_FILE = _CRED_DIR / "credentials"


def _get_fernet() -> Any:
    if Fernet is None:
        return None
    key_file = _CRED_DIR / ".key"
    if not key_file.exists():
        _CRED_DIR.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        key_file.write_bytes(key)
        key_file.chmod(0o600)
    else:
        key = key_file.read_bytes()
    return Fernet(key)


def _encrypt(plaintext: str) -> str:
    if sys.platform == "win32":
        data = plaintext.encode("utf-16-le")
        blob = win32crypt.CryptProtectData(data, None, None, None, None, 0)
        return base64.b64encode(blob).decode("ascii")
    f = _get_fernet()
    if f is not None:
        return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    blob = base64.b64encode(plaintext.encode("utf-8"))
    return f"b64:{blob.decode('ascii')}"


def _decrypt(ciphertext: str) -> str:
    if sys.platform == "win32":
        blob = base64.b64decode(ciphertext)
        data = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        return data[1].decode("utf-16-le")
    f = _get_fernet()
    if f is not None:
        try:
            return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except FernetInvalidToken:
            pass
    if ciphertext.startswith("b64:"):
        return base64.b64decode(ciphertext[4:]).decode("utf-8")
    raise ValueError("Unknown credential format")


def load_api_key(provider: str) -> str | None:
    """Load and decrypt an API key for the given provider from the credentials store."""
    if not _CRED_FILE.exists():
        return None
    try:
        raw = _CRED_FILE.read_text("utf-8").strip()
        if not raw:
            return None
        store: dict = json.loads(raw) if raw.startswith("{") else {}
        return _decrypt(store.get(provider, "")) if store.get(provider) else None
    except Exception:
        logger.exception("Failed to load API key")
        return None


def save_api_key(provider: str, key: str) -> None:
    """Encrypt and persist an API key for the given provider."""
    _CRED_DIR.mkdir(parents=True, exist_ok=True)
    store: dict = {}
    if _CRED_FILE.exists():
        try:
            raw = _CRED_FILE.read_text("utf-8").strip()
            store = json.loads(raw) if raw.startswith("{") else {}
        except Exception:
            logger.exception("Failed to parse credentials file")
            store = {}
    store[provider] = _encrypt(key)
    _CRED_FILE.write_text(json.dumps(store, indent=2), "utf-8")
    if sys.platform != "win32":
        _CRED_FILE.chmod(0o600)


def delete_api_key(provider: str) -> bool:
    """Remove a stored API key for the given provider and return True if one was removed."""
    if not _CRED_FILE.exists():
        return False
    try:
        raw = _CRED_FILE.read_text("utf-8").strip()
        store: dict = json.loads(raw) if raw.startswith("{") else {}
        removed = store.pop(provider, None)
        if removed:
            _CRED_FILE.write_text(json.dumps(store, indent=2), "utf-8")
        return removed is not None
    except Exception:
        logger.exception("Failed to delete API key")
        return False


async def async_load_api_key(provider: str) -> str | None:
    """Load an API key asynchronously via the thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, load_api_key, provider)


async def async_save_api_key(provider: str, key: str) -> None:
    """Save an API key asynchronously via the thread pool."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, save_api_key, provider, key)


async def async_delete_api_key(provider: str) -> bool:
    """Delete an API key asynchronously via the thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, delete_api_key, provider)
