from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai.types.chat import ChatCompletionMessage

from mcp_cli.services.claude import Claude


@pytest.mark.asyncio
async def test_claude_chat_success():
    with patch("mcp_cli.services.claude.AsyncOpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_openai_class.return_value = mock_client

        service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")

        mock_msg = ChatCompletionMessage(role="assistant", content="Hello!")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_msg)]
        mock_client.chat.completions.create.return_value = mock_response

        response = await service.chat([{"role": "user", "content": "Hi"}])
        assert response.content == "Hello!"

@pytest.mark.asyncio
async def test_claude_chat_string_response():
    with patch("mcp_cli.services.claude.AsyncOpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_openai_class.return_value = mock_client

        service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")
        mock_client.chat.completions.create.return_value = "Direct string response"

        response = await service.chat([{"role": "user", "content": "Hi"}])
        assert isinstance(response, ChatCompletionMessage)
        assert response.content == "Direct string response"

@pytest.mark.asyncio
async def test_claude_chat_dict_response():
    with patch("mcp_cli.services.claude.AsyncOpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_openai_class.return_value = mock_client

        service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")
        mock_client.chat.completions.create.return_value = {
            "choices": [{"message": {"content": "Dict response", "role": "assistant"}}]
        }

        response = await service.chat([{"role": "user", "content": "Hi"}])
        assert isinstance(response, ChatCompletionMessage)
        assert response.content == "Dict response"
