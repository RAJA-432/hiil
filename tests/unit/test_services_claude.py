from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_cli.services.claude import Claude


@pytest.mark.asyncio
async def test_stream_chat_content(mock_openai):
    service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")

    class FakeChunk:
        def __init__(self, content):
            self.choices = [MagicMock(delta=MagicMock(content=content, tool_calls=None))]

    chunks = [FakeChunk("Hello"), FakeChunk(" world")]
    async def async_iter():
        for c in chunks:
            yield c
    mock_openai.chat.completions.create.return_value.__aiter__ = lambda self: async_iter()

    results = []
    async for kind, data in service.stream_chat([{"role": "user", "content": "Hi"}]):
        results.append((kind, data))

    assert ("content", "Hello") in results
    assert ("content", " world") in results
    assert any(k == "done" for k, _ in results)


@pytest.mark.asyncio
async def test_stream_chat_tool_calls(mock_openai):
    service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")

    class FakeFunc:
        def __init__(self, name="", arguments=""):
            self.name = name
            self.arguments = arguments

    class FakeToolCall:
        def __init__(self, index, name, args, id="call_1"):
            self.index = index
            self.id = id
            self.function = FakeFunc(name=name, arguments=args)

    class FakeDelta:
        def __init__(self, tool_calls=None, content=None):
            self.content = content
            self.tool_calls = tool_calls

    def _make_chunk(tc_list):
        return MagicMock(choices=[MagicMock(delta=FakeDelta(tool_calls=tc_list))])

    async def async_iter():
        yield _make_chunk([FakeToolCall(0, "get_weather", '{"city":"', id="call_1")])
        yield _make_chunk([FakeToolCall(0, "", ' "London"}', id="")])
        yield _make_chunk([FakeToolCall(0, "", "", id="")])

    mock_openai.chat.completions.create.return_value.__aiter__ = lambda self: async_iter()

    results = []
    async for kind, data in service.stream_chat([{"role": "user", "content": "weather"}]):
        results.append((kind, data))

    tool_events = [(k, d["name"]) for k, d in results if k == "tool_call"]
    assert ("tool_call", "get_weather") in tool_events
    assert any(d["arguments"] == '{"city":" "London"}' for k, d in results if k == "tool_call")


@pytest.mark.asyncio
async def test_stream_chat_empty(mock_openai):
    service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")

    async def async_iter():
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content=None, tool_calls=None))])

    mock_openai.chat.completions.create.return_value.__aiter__ = lambda self: async_iter()

    results = []
    async for kind, data in service.stream_chat([{"role": "user", "content": "hi"}]):
        results.append((kind, data))

    assert any(k == "done" for k, _ in results)


@pytest.mark.asyncio
async def test_chat_with_tools_none(mock_openai):
    service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")
    mock_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="ok", tool_calls=None))]
    )
    reply = await service.chat([{"role": "user", "content": "hi"}], tools=None)
    assert reply.content == "ok"


@pytest.mark.asyncio
async def test_chat_empty_choices(mock_openai):
    service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")
    mock_openai.chat.completions.create.return_value = MagicMock(choices=[])
    reply = await service.chat([{"role": "user", "content": "hi"}])
    assert reply.content == ""


@pytest.mark.asyncio
async def test_chat_dict_tool_calls(mock_openai):
    service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")
    raw_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": "c1", "function": {"name": "t1", "arguments": "{}"}, "type": "function"}],
                }
            }
        ]
    }
    mock_openai.chat.completions.create.return_value = raw_response
    reply = await service.chat([{"role": "user", "content": "call tool"}])
    assert reply.tool_calls is not None
    assert len(reply.tool_calls) == 1


@pytest.mark.asyncio
async def test_chat_dict_no_tool_calls(mock_openai):
    service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")
    raw_response = {
        "choices": [{"message": {"role": "assistant", "content": "hello"}}]
    }
    mock_openai.chat.completions.create.return_value = raw_response
    reply = await service.chat([{"role": "user", "content": "hi"}])
    assert reply.content == "hello"


@pytest.mark.asyncio
async def test_chat_tenacity_retry(mock_openai):
    import httpx
    from openai import APIError
    from openai.types.chat import ChatCompletionMessage

    service = Claude(provider="openrouter", model="gpt-4", api_key="test-key")
    mock_openai.chat.completions.create.side_effect = [
        APIError("transient", httpx.Request("POST", "https://api.example.com"), body=None),
        MagicMock(choices=[MagicMock(message=ChatCompletionMessage(role="assistant", content="retried"))]),
    ]
    result = await service.chat([{"role": "user", "content": "hi"}])
    assert result.content == "retried"


@pytest.mark.asyncio
async def test_embed_success(mock_openai, mock_httpx):
    service = Claude(provider="openrouter", model="gpt-4", api_key="test-key", base_url="https://api.openrouter.ai/v1")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
    mock_httpx.post = AsyncMock(return_value=mock_resp)
    result = await service.embed("hello world")
    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_embed_failure_returns_empty(mock_openai, mock_httpx):
    service = Claude(provider="openrouter", model="gpt-4", api_key="test-key", base_url="https://api.openrouter.ai/v1")
    mock_httpx.post = AsyncMock(side_effect=RuntimeError("api down"))
    result = await service.embed("test")
    assert result == []


@pytest.mark.asyncio
async def test_embed_calls_correct_url(mock_openai, mock_httpx):
    service = Claude(provider="ollama", model="gemma4:31b-cloud", api_key="", base_url="http://localhost:11434/v1")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"embeddings": [[0.5]]}
    mock_httpx.post = AsyncMock(return_value=mock_resp)
    await service.embed("text")
    call_url = mock_httpx.post.call_args[0][0]
    assert "embed" in call_url
    assert "embeddings" not in call_url


def test_system_prompt_ollama(ollama_service):
    prompt = ollama_service.system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 50
    assert "tools" in prompt.lower() or "tool" in prompt.lower()


def test_system_prompt_openrouter(claude_service):
    prompt = claude_service.system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 50


def test_update_model(claude_service):
    reply = claude_service.update_model("gpt-4o-mini")
    assert claude_service.model == "gpt-4o-mini"
    assert "gpt-4o-mini" in reply


def test_update_provider(claude_service):
    claude_service.update_provider("ollama", "", "http://localhost:11434/v1")
    assert claude_service.provider == "ollama"
    assert claude_service.base_url == "http://localhost:11434/v1"


def test_status_info(ollama_service):
    info = ollama_service.status_info()
    assert info["provider"] == "ollama"
    assert info["model"] == "gemma4:31b-cloud"


@pytest.mark.asyncio
async def test_list_models_empty(mock_openai, mock_httpx):
    service = Claude(provider="ollama", model="gemma4", api_key="")
    mock_httpx.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"data": []}))
    models = await service.list_models()
    assert models == []


@pytest.mark.asyncio
async def test_list_models_http_error(mock_openai, mock_httpx):
    service = Claude(provider="ollama", model="gemma4", api_key="")
    mock_httpx.get = AsyncMock(return_value=MagicMock(status_code=500))
    models = await service.list_models()
    assert models == []


@pytest.mark.asyncio
async def test_list_models_no_data_key(mock_openai, mock_httpx):
    service = Claude(provider="ollama", model="gemma4", api_key="")
    mock_httpx.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {}))
    models = await service.list_models()
    assert models == []


@pytest.mark.asyncio
async def test_list_models_non_json(mock_openai, mock_httpx):
    service = Claude(provider="ollama", model="gemma4", api_key="")
    mock_httpx.get = AsyncMock(side_effect=RuntimeError("connection error"))
    models = await service.list_models()
    assert models == []
