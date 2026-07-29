from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to sys.path for imports
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class FakeTool:
    def __init__(self, name="test_tool", description="A test tool", inputSchema=None):
        self.name = name
        self.description = description
        self.inputSchema = inputSchema or {"type": "object", "properties": {}}


class FakeToolCall:
    def __init__(self, name="my_tool", args='{"arg":"val"}', id="call_1"):
        self.function = MagicMock()
        self.function.name = name
        self.function.arguments = args
        self.id = id


class FakeContentBlock:
    def __init__(self, text="result text"):
        self.text = text


class FakeCallToolResult:
    def __init__(self, texts=None):
        self.content = [FakeContentBlock(t) for t in (texts or ["result text"])]


@pytest.fixture
def mock_openai():
    """Patches AsyncOpenAI in claude module, returns mock_client."""
    with patch("mcp_cli.services.claude.AsyncOpenAI") as mock_class:
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def claude_service():
    """Claude instance with mocked AsyncOpenAI (openrouter/gpt-4)."""
    with patch("mcp_cli.services.claude.AsyncOpenAI") as mock_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_class.return_value = mock_client
        from mcp_cli.services.claude import LLMClient

        yield LLMClient(provider="openrouter", model="gpt-4", api_key="test-key")

@pytest.fixture
def ollama_service():
    """Claude instance with mocked AsyncOpenAI (ollama/gemma4)."""
    with patch("mcp_cli.services.claude.AsyncOpenAI") as mock_class:
        mock_client = MagicMock()
        mock_class.return_value = mock_client
        from mcp_cli.services.claude import LLMClient

        yield LLMClient(provider="ollama", model="gemma4:31b-cloud", api_key="", base_url="http://localhost:11434/v1")

@pytest.fixture
def mock_httpx():
    """Patches httpx.AsyncClient, yields mock instance with __aenter__ configured."""
    with patch("httpx.AsyncClient") as mock_class:
        mock_instance = MagicMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.post = AsyncMock()
        mock_instance.get = AsyncMock()
        mock_class.return_value = mock_instance
        yield mock_instance
