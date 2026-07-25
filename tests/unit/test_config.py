from unittest.mock import MagicMock, patch

import pytest

from mcp_cli.config import ServerConfig, Settings, _validate_config, load_settings


def test_load_settings_success(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("MODEL_NAME", "gpt-4")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")

    settings, servers = load_settings("nonexistent.yaml")
    assert settings.provider == "openrouter"
    assert settings.model == "gpt-4"
    assert settings.api_key == "test-key"

def test_load_settings_missing_model(monkeypatch):
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.setenv("MODEL_API_KEY", "test-key")

    with patch("mcp_cli.config.load_dotenv"):
        with pytest.raises(ValueError, match="Model name must be provided"):
            load_settings("nonexistent.yaml")

_LEGACY_KEYS = ["OPENROUTER_API_KEY", "OPENCODE_API_KEY", "OLLAMA_API_KEY"]

def test_load_settings_missing_key(monkeypatch):
    for k in _LEGACY_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("MODEL_NAME", "gpt-4")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    with patch("mcp_cli.config.load_dotenv"):
        with pytest.raises(ValueError, match="API Key must be provided"):
            load_settings("nonexistent.yaml")

def test_load_settings_ollama_no_key(monkeypatch):
    for k in _LEGACY_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL_NAME", "llama3")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    with patch("mcp_cli.config.load_dotenv"):
        settings, servers = load_settings("nonexistent.yaml")
    assert settings.provider == "ollama"
    assert settings.api_key == ""

def test_load_settings_ollama_legacy_key(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL_NAME", "llama3")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-legacy-key")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    with patch("mcp_cli.config.load_dotenv"):
        settings, servers = load_settings("nonexistent.yaml")
    assert settings.api_key == "ollama-legacy-key"

def test_load_settings_default_base_url(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("MODEL_NAME", "gpt-4")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")

    settings, servers = load_settings("nonexistent.yaml")
    assert settings.base_url == "https://openrouter.ai/api/v1"

def test_load_settings_provider_default(monkeypatch):
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")

    with patch("mcp_cli.config.load_dotenv"):
        settings, servers = load_settings("nonexistent.yaml")
    assert settings.provider == "openrouter"


def test_load_settings_credential_store(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("MODEL_NAME", "gpt-4")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    for k in ["OPENROUTER_API_KEY", "OPENCODE_API_KEY", "OLLAMA_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    with patch("mcp_cli.config.load_dotenv"):
        with patch("mcp_cli.services.credentials.load_api_key", return_value="cred-key"):
            settings, servers = load_settings("nonexistent.yaml")
    assert settings.api_key == "cred-key"


def test_load_settings_credential_overrides_yaml(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("MODEL_NAME", "gpt-4")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    for k in ["OPENROUTER_API_KEY", "OPENCODE_API_KEY", "OLLAMA_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    with patch("mcp_cli.config.load_dotenv"):
        with patch("mcp_cli.services.credentials.load_api_key", return_value="cred-key"):
            with patch("builtins.open") as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = "settings:\n  provider: openrouter\n  model: gpt-4\n  api_key: yaml-key\n"
                mock_open.return_value.__enter__.return_value = mock_file
                settings, servers = load_settings("dummy.yaml")
    assert settings.api_key == "cred-key"


def test_resolve_launch_npx():
    cfg = ServerConfig(id="test", script="@some-package")
    cmd, args = cfg.resolve_launch()
    assert cmd == "npx"
    assert "-y" in args


def test_resolve_launch_npx_with_args():
    cfg = ServerConfig(id="test", script="@some-package", args=["--flag"])
    cmd, args = cfg.resolve_launch()
    assert args == ["-y", "@some-package", "--flag"]


def test_resolve_launch_with_command():
    cfg = ServerConfig(id="test", script="server.py", command="node")
    cmd, args = cfg.resolve_launch()
    assert cmd == "node"
    assert args == ["server.py"]


def test_resolve_launch_uv(monkeypatch):
    monkeypatch.setenv("USE_UV", "1")
    cfg = ServerConfig(id="test", script="server.py")
    cmd, args = cfg.resolve_launch()
    assert cmd == "uv"
    assert args == ["run", "server.py"]


def test_resolve_launch_python_default(monkeypatch):
    monkeypatch.delenv("USE_UV", raising=False)
    cfg = ServerConfig(id="test", script="server.py")
    cmd, args = cfg.resolve_launch()
    assert cmd == "python"
    assert args == ["server.py"]


def test_server_config_defaults():
    cfg = ServerConfig(id="test", script="s.py")
    assert cfg.args == []
    assert cfg.env == {}
    assert cfg.command is None


def test_server_config_with_all_fields():
    cfg = ServerConfig(id="test", script="server.js", args=["-p", "3000"], env={"NODE_ENV": "prod"}, command="node")
    assert cfg.args == ["-p", "3000"]
    assert cfg.env == {"NODE_ENV": "prod"}
    assert cfg.command == "node"


def test_settings_dataclass():
    s = Settings(provider="ollama", model="llama3", api_key="", base_url="http://localhost", max_context_tokens=100000)
    assert s.provider == "ollama"
    assert s.model == "llama3"
    assert s.max_context_tokens == 100000


def test_validate_config_no_warnings_on_good_config(caplog):
    s = Settings(provider="ollama", model="llama3", api_key="", base_url="https://api.openai.com/v1", max_context_tokens=100000)
    servers = [ServerConfig(id="safe", script="server.py")]
    with caplog.at_level("WARNING"):
        _validate_config(s, servers)
    assert len(caplog.records) == 0


def test_validate_config_noop(caplog):
    s = Settings(provider="ollama", model="llama3", api_key="", base_url="http://insecure.example.com", max_context_tokens=100000)
    servers = [ServerConfig(id="bad", script="evil.sh", args=["something", "-exec", "malware"])]
    with caplog.at_level("WARNING"):
        _validate_config(s, servers)
    assert len(caplog.records) == 0


def test_load_settings_env_overrides_yaml(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL_NAME", "custom-model")
    monkeypatch.setenv("MODEL_API_KEY", "env-key")
    settings, servers = load_settings("nonexistent.yaml")
    assert settings.provider == "ollama"
    assert settings.model == "custom-model"
    assert settings.api_key == "env-key"


def test_load_settings_base_url_from_yaml(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL_NAME", "llama3")
    monkeypatch.setenv("MODEL_API_KEY", "test")
    with patch("mcp_cli.config.load_dotenv"):
        settings, servers = load_settings("nonexistent.yaml")
    assert settings.base_url == "http://localhost:11434/v1"


def test_resolve_launch_npx_with_env():
    cfg = ServerConfig(id="test", script="@pkg", env={"KEY": "VAL"})
    cmd, args = cfg.resolve_launch()
    assert cmd == "npx"
    assert cfg.env == {"KEY": "VAL"}


def test_server_config_repr():
    cfg = ServerConfig(id="my_id", script="script.py")
    r = repr(cfg)
    assert "my_id" in r
