from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_chat_and_app(MockCliChat, MockCliApp):
    chat_instance = MagicMock()
    chat_instance.initialize = AsyncMock()
    MockCliChat.return_value = chat_instance
    app_instance = AsyncMock()
    MockCliApp.return_value = app_instance
    return chat_instance, app_instance


@patch("mcp_cli.services.factory.load_settings")
@patch("mcp_cli.services.factory.Claude")
@patch("mcp_cli.services.factory.AsyncExitStack")
@patch("mcp_cli.services.server_manager.MCPClient")
@patch("mcp_cli.services.factory.create_servers")
@patch("mcp_cli.services.factory.CliChat")
@patch("mcp_cli.main.CliApp")
@pytest.mark.asyncio
async def test_main_success(MockCliApp, MockCliChat, MockCreateServers,
                            MockMCPClient, MockExitStack, MockClaude,
                            MockLoadSettings):
    MockLoadSettings.return_value = (
        MagicMock(provider="ollama", model="gemma4", api_key="", base_url="", max_context_tokens=200000),
        [MagicMock(id="fs", script="server.py")],
    )
    stack_instance = AsyncMock()
    stack_instance.__aenter__ = AsyncMock(return_value=stack_instance)
    MockExitStack.return_value = stack_instance
    MockCreateServers.return_value = (AsyncMock(), {"fs": AsyncMock()})
    chat_instance, app_instance = _make_chat_and_app(MockCliChat, MockCliApp)

    from mcp_cli.main import main
    await main()

    MockCliChat.assert_called_once()
    MockCliApp.assert_called_once_with(chat_instance)
    app_instance.run.assert_awaited_once()


@patch("mcp_cli.services.factory.load_settings")
@pytest.mark.asyncio
async def test_main_settings_error(MockLoadSettings):
    MockLoadSettings.side_effect = ValueError("bad config")
    from mcp_cli.main import main
    with pytest.raises(ValueError, match="bad config"):
        await main()
