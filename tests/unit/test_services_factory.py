from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_cli.config import ServerConfig, Settings, _validate_config, load_settings
from mcp_cli.services.factory import _build_sampling_callback, create_chat

# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------

def test_settings_defaults():
    s = Settings(provider="ollama", model="llama3", api_key="", base_url=None)
    assert s.max_context_tokens == 200_000
    assert s.roots == ["."]


def test_settings_custom_values():
    s = Settings(
        provider="openrouter",
        model="gpt-4",
        api_key="sk-key",
        base_url="https://custom.ai/v1",
        max_context_tokens=100_000,
        roots=["/data"],
    )
    assert s.provider == "openrouter"
    assert s.base_url == "https://custom.ai/v1"
    assert s.max_context_tokens == 100_000
    assert s.roots == ["/data"]


# ---------------------------------------------------------------------------
# ServerConfig
# ---------------------------------------------------------------------------

def test_server_config_defaults():
    cfg = ServerConfig(id="my_id", script="s.py")
    assert cfg.args == []
    assert cfg.env == {}
    assert cfg.command is None
    assert cfg.transport == "stdio"


def test_server_config_all_fields():
    cfg = ServerConfig(
        id="svc", script="run.py", args=["-v"], env={"KEY": "VAL"},
        command="python3", transport="sse",
    )
    assert cfg.args == ["-v"]
    assert cfg.env == {"KEY": "VAL"}
    assert cfg.command == "python3"
    assert cfg.transport == "sse"


def test_resolve_launch_python_default(monkeypatch):
    monkeypatch.delenv("USE_UV", raising=False)
    cfg = ServerConfig(id="t", script="server.py")
    cmd, args = cfg.resolve_launch()
    assert cmd == "python"
    assert args == ["server.py"]


def test_resolve_launch_npx():
    cfg = ServerConfig(id="t", script="@some-package")
    cmd, args = cfg.resolve_launch()
    assert cmd == "npx"
    assert "-y" in args


def test_resolve_launch_npx_with_args():
    cfg = ServerConfig(id="t", script="@pkg", args=["--port", "9999"])
    cmd, args = cfg.resolve_launch()
    assert args == ["-y", "@pkg", "--port", "9999"]


def test_resolve_launch_with_command():
    cfg = ServerConfig(id="t", script="server.js", command="node")
    cmd, args = cfg.resolve_launch()
    assert cmd == "node"
    assert args == ["server.js"]


def test_resolve_launch_uv(monkeypatch):
    monkeypatch.setenv("USE_UV", "1")
    cfg = ServerConfig(id="t", script="server.py")
    cmd, args = cfg.resolve_launch()
    assert cmd == "uv"
    assert args == ["run", "server.py"]


# ---------------------------------------------------------------------------
# _validate_config
# ---------------------------------------------------------------------------

def test_validate_config_unknown_provider():
    s = Settings(provider="unknown", model="m", api_key="k", base_url=None)
    with pytest.raises(ValueError, match="Unknown provider"):
        _validate_config(s, [])


def test_validate_config_negative_tokens():
    s = Settings(provider="ollama", model="m", api_key="k", base_url=None, max_context_tokens=-1)
    with pytest.raises(ValueError, match="max_context_tokens"):
        _validate_config(s, [])


def test_validate_config_duplicate_server_id():
    s = Settings(provider="ollama", model="m", api_key="k", base_url=None)
    servers = [
        ServerConfig(id="dup", script="a.py"),
        ServerConfig(id="dup", script="b.py"),
    ]
    with pytest.raises(ValueError, match="Duplicate"):
        _validate_config(s, servers)


def test_validate_config_sse_without_command():
    s = Settings(provider="ollama", model="m", api_key="k", base_url=None)
    servers = [ServerConfig(id="sse_srv", script="s.py", transport="sse")]
    with pytest.raises(ValueError, match="sse transport requires a 'command'"):
        _validate_config(s, servers)


def test_validate_config_invalid_transport():
    s = Settings(provider="ollama", model="m", api_key="k", base_url=None)
    servers = [ServerConfig(id="bad", script="s.py", transport="websocket")]
    with pytest.raises(ValueError, match="transport must be"):
        _validate_config(s, servers)


def test_validate_config_no_script_or_command():
    s = Settings(provider="ollama", model="m", api_key="k", base_url=None)
    servers = [ServerConfig(id="empty", script="")]
    with pytest.raises(ValueError, match="one of 'script' or 'command' is required"):
        _validate_config(s, servers)


def test_validate_config_valid():
    s = Settings(provider="ollama", model="m", api_key="k", base_url=None)
    servers = [ServerConfig(id="ok", script="server.py")]
    _validate_config(s, servers)


def test_validate_config_provider_case_insensitive():
    s = Settings(provider="OpenRouter", model="m", api_key="k", base_url=None)
    with pytest.raises(ValueError, match="Unknown provider"):
        _validate_config(s, [])


# ---------------------------------------------------------------------------
# _build_sampling_callback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_sampling_callback():
    claude = MagicMock()
    claude.chat = AsyncMock(return_value=MagicMock(content="Hello!"))
    claude.model = "gpt-4"

    from mcp.types import CreateMessageRequestParams, TextContent

    callback = _build_sampling_callback(claude)
    params = MagicMock(spec=CreateMessageRequestParams)
    msg = MagicMock()
    msg.role = "user"
    msg.content = TextContent(type="text", text="Hi")
    params.messages = [msg]

    result = await callback(MagicMock(), params)
    assert result.role == "assistant"
    assert result.model == "gpt-4"
    assert result.content.text == "Hello!"


# ---------------------------------------------------------------------------
# create_chat
# ---------------------------------------------------------------------------

def _make_settings(**overrides) -> Settings:
    kwargs = dict(provider="ollama", model="llama3", api_key="", base_url="http://localhost:11434/v1")
    kwargs.update(overrides)
    return Settings(**kwargs)


@pytest.mark.asyncio
async def test_create_chat_wiring():
    settings = _make_settings(roots=["/tmp"])
    mock_doc_client = AsyncMock()
    mock_clients = {"fs": AsyncMock()}

    with (
        patch("mcp_cli.services.factory.load_settings", return_value=(settings, [])),
        patch("mcp_cli.services.factory.Claude") as MockClaude,
        patch("mcp_cli.services.factory.create_servers", return_value=(mock_doc_client, mock_clients)) as mock_create_servers,
        patch("mcp_cli.services.factory.CliChat") as MockCliChat,
    ):
        mock_claude_instance = MagicMock()
        MockClaude.return_value = mock_claude_instance
        mock_chat_instance = AsyncMock()
        MockCliChat.return_value = mock_chat_instance

        stack = AsyncExitStack()
        result = await create_chat(stack)

        MockClaude.assert_called_once_with(
            provider="ollama", model="llama3", api_key="", base_url="http://localhost:11434/v1",
        )
        mock_create_servers.assert_called_once()
        MockCliChat.assert_called_once()
        args, kwargs = MockCliChat.call_args
        assert kwargs["doc_client"] is mock_doc_client
        assert kwargs["clients"] is mock_clients
        assert kwargs["claude_service"] is mock_claude_instance
        assert kwargs["max_context_tokens"] == 200_000

        mock_chat_instance.initialize.assert_awaited_once()
        assert result is mock_chat_instance


@pytest.mark.asyncio
async def test_create_chat_custom_logging_callback():
    settings = _make_settings()
    mock_doc_client = AsyncMock()
    mock_clients = {}
    log_cb = AsyncMock()

    with (
        patch("mcp_cli.services.factory.load_settings", return_value=(settings, [])),
        patch("mcp_cli.services.factory.Claude"),
        patch("mcp_cli.services.factory.create_servers", return_value=(mock_doc_client, mock_clients)) as mock_create_servers,
        patch("mcp_cli.services.factory.CliChat", return_value=AsyncMock()),
    ):
        stack = AsyncExitStack()
        await create_chat(stack, logging_callback=log_cb)

        _, kwargs = mock_create_servers.call_args
        assert kwargs["logging_callback"] is log_cb


@pytest.mark.asyncio
async def test_create_chat_default_logging_callback_does_not_raise():
    settings = _make_settings()
    with (
        patch("mcp_cli.services.factory.load_settings", return_value=(settings, [])),
        patch("mcp_cli.services.factory.Claude"),
        patch("mcp_cli.services.factory.create_servers", return_value=(AsyncMock(), {})),
        patch("mcp_cli.services.factory.CliChat", return_value=AsyncMock()),
    ):
        stack = AsyncExitStack()
        await create_chat(stack)


# ---------------------------------------------------------------------------
# load_settings (wiring)
# ---------------------------------------------------------------------------

def test_load_settings_success(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL_NAME", "llama3")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")

    settings, servers = load_settings("nonexistent.yaml")
    assert settings.provider == "ollama"
    assert settings.model == "llama3"
    assert settings.api_key == "test-key"


def test_load_settings_provider_default(monkeypatch):
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")

    with patch("mcp_cli.config.load_dotenv"):
        settings, servers = load_settings("nonexistent.yaml")
    assert settings.provider == "openrouter"


def test_load_settings_missing_model(monkeypatch):
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.setenv("MODEL_API_KEY", "test-key")

    with patch("mcp_cli.config.load_dotenv"):
        with pytest.raises(ValueError, match="Model name must be provided"):
            load_settings("nonexistent.yaml")


def test_load_settings_missing_key(monkeypatch):
    for k in ["OPENROUTER_API_KEY", "OPENCODE_API_KEY", "OLLAMA_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("MODEL_NAME", "gpt-4")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    with patch("mcp_cli.config.load_dotenv"):
        with pytest.raises(ValueError, match="API Key must be provided"):
            load_settings("nonexistent.yaml")


def test_load_settings_ollama_no_key(monkeypatch):
    for k in ["OPENROUTER_API_KEY", "OPENCODE_API_KEY", "OLLAMA_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL_NAME", "llama3")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    with patch("mcp_cli.config.load_dotenv"):
        settings, servers = load_settings("nonexistent.yaml")
    assert settings.provider == "ollama"
    assert settings.api_key == ""


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


def test_load_settings_base_url_by_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("MODEL_NAME", "gpt-4")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")

    settings, servers = load_settings("nonexistent.yaml")
    assert settings.base_url == "https://openrouter.ai/api/v1"


def test_load_settings_ollama_base_url(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL_NAME", "llama3")
    monkeypatch.setenv("MODEL_API_KEY", "test")

    settings, servers = load_settings("nonexistent.yaml")
    assert settings.base_url == "http://localhost:11434/v1"


def test_load_settings_env_override(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL_NAME", "custom-model")
    monkeypatch.setenv("MODEL_API_KEY", "env-key")

    settings, servers = load_settings("nonexistent.yaml")
    assert settings.provider == "ollama"
    assert settings.model == "custom-model"
    assert settings.api_key == "env-key"
