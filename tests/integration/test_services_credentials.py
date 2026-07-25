import base64
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_cli.services.credentials import (
    _decrypt,
    _encrypt,
    delete_api_key,
    load_api_key,
    save_api_key,
)


@pytest.fixture
def tmp_credentials(tmp_path):
    """Isolates credential file operations to a temp directory."""
    cred_dir = tmp_path / ".hiil"
    cred_file = cred_dir / "credentials.json"
    with (
        patch("mcp_cli.services.credentials._CRED_DIR", cred_dir),
        patch("mcp_cli.services.credentials._CRED_FILE", cred_file),
    ):
        yield cred_dir, cred_file


def test_encrypt_decrypt_roundtrip():
    original = "sk-test-api-key-12345"
    encrypted = _encrypt(original)
    assert encrypted != original
    assert _decrypt(encrypted) == original


def test_encrypt_empty_string():
    encrypted = _encrypt("")
    assert _decrypt(encrypted) == ""


def test_decrypt_invalid_format():
    with pytest.raises(ValueError):
        _decrypt("invalid_format!!")


def test_decrypt_b64_prefix():
    val = _encrypt("hello")
    assert _decrypt(val) == "hello"


def test_decrypt_legacy_b64_format():
    """b64: prefixed entries from older versions must still decrypt on non-Windows."""
    import sys
    if sys.platform == "win32":
        pytest.skip("b64: format never used on Windows")
    legacy = "b64:" + base64.b64encode(b"legacy-key").decode("ascii")
    assert _decrypt(legacy) == "legacy-key"


def test_save_and_load_api_key(tmp_credentials):
    save_api_key("test_provider", "sk-test-key-1")
    assert load_api_key("test_provider") == "sk-test-key-1"


def test_load_nonexistent_provider():
    assert load_api_key("nonexistent_provider") is None


def test_load_nonexistent_file(tmp_credentials):
    assert load_api_key("any") is None


def test_save_overwrites_existing(tmp_credentials):
    save_api_key("overwrite_prov", "key1")
    save_api_key("overwrite_prov", "key2")
    assert load_api_key("overwrite_prov") == "key2"


def test_save_multiple_providers(tmp_credentials):
    save_api_key("prov_a", "key_a")
    save_api_key("prov_b", "key_b")
    assert load_api_key("prov_a") == "key_a"
    assert load_api_key("prov_b") == "key_b"


def test_delete_existing_key(tmp_credentials):
    save_api_key("delete_me", "to_delete")
    assert delete_api_key("delete_me") is True
    assert load_api_key("delete_me") is None


def test_delete_nonexistent_key(tmp_credentials):
    assert delete_api_key("never_existed") is False


def test_delete_nonexistent_file(tmp_credentials):
    assert delete_api_key("any") is False


def test_load_with_corrupted_file(tmp_credentials):
    cred_dir, cred_file = tmp_credentials
    cred_dir.mkdir(parents=True, exist_ok=True)
    cred_file.write_text("not valid json", "utf-8")
    assert load_api_key("any") is None


def test_delete_with_corrupted_file(tmp_credentials):
    assert delete_api_key("any") is False


def test_encrypt_special_characters():
    val = "key-with-special_chars!@#$%^&*()"
    encrypted = _encrypt(val)
    assert _decrypt(encrypted) == val


def test_encrypt_unicode():
    val = "ключ-тест-🔥"
    encrypted = _encrypt(val)
    assert _decrypt(encrypted) == val


def test_encrypt_long_key():
    val = "A" * 10000
    encrypted = _encrypt(val)
    assert _decrypt(encrypted) == val


def test_encrypt_with_spaces():
    val = "  sk-test-key with spaces  "
    encrypted = _encrypt(val)
    assert _decrypt(encrypted) == val


def test_encrypt_deterministic_with_same_plaintext():
    a = _encrypt("deterministic-test")
    b = _encrypt("deterministic-test")
    assert _decrypt(a) == _decrypt(b)


def test_save_creates_directory(tmp_credentials):
    cred_dir, cred_file = tmp_credentials
    save_api_key("new_dir", "key")
    assert cred_dir.exists()
    assert cred_file.exists()


def test_load_returns_none_for_empty_file(tmp_credentials):
    cred_dir, cred_file = tmp_credentials
    cred_dir.mkdir(parents=True, exist_ok=True)
    cred_file.write_text("", "utf-8")
    assert load_api_key("any") is None


def test_load_returns_none_for_whitespace_file(tmp_credentials):
    _, cred_file = tmp_credentials
    cred_file.parent.mkdir(parents=True, exist_ok=True)
    cred_file.write_text("   \n  ", "utf-8")
    assert load_api_key("any") is None


def test_save_preserves_other_providers(tmp_credentials):
    save_api_key("keep_me", "keep_key")
    save_api_key("new_one", "new_key")
    assert load_api_key("keep_me") == "keep_key"
    assert load_api_key("new_one") == "new_key"


def test_delete_only_removes_target(tmp_credentials):
    save_api_key("keeper", "keep")
    save_api_key("remover", "remove")
    delete_api_key("remover")
    assert load_api_key("keeper") == "keep"
    assert load_api_key("remover") is None


def test_encrypt_output_format():
    val = "test"
    encrypted = _encrypt(val)
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0
