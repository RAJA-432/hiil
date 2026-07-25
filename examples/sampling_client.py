"""
MCP client demonstrating sampling: connects to sampling_server.py with a
sampling_callback that fulfills LLM generation requests via OpenAI SDK.

Usage:
    python examples/sampling_client.py                          # real LLM via .env
    python examples/sampling_client.py --mock                    # fake responses
"""

import argparse
import asyncio
import os
import sys
from contextlib import AsyncExitStack

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.session import RequestContext
from mcp.types import CreateMessageRequestParams, CreateMessageResult, TextContent


async def mock_sampling_callback(
    context: RequestContext,
    params: CreateMessageRequestParams,
) -> CreateMessageResult:
    """Mock callback that returns canned responses (no API key needed)."""
    prompt = params.messages[0].content.text if params.messages else ""
    model_used = "mock-model"

    if "summarize" in prompt.lower():
        reply = "This is a mock summary of the provided text."
    elif "translate" in prompt.lower():
        reply = "[Mock translation]"
    elif "sentiment" in prompt.lower():
        reply = "NEUTRAL\nThis appears to be a neutral statement based on the mock analysis."
    else:
        reply = f"Mock response to: {prompt[:60]}..."

    return CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text=reply),
        model=model_used,
    )


async def openai_sampling_callback(
    context: RequestContext,
    params: CreateMessageRequestParams,
) -> CreateMessageResult:
    """Real callback using OpenAI SDK (supports OpenRouter, Ollama, etc.)."""
    from openai import AsyncOpenAI

    provider = os.getenv("MODEL_PROVIDER", "ollama")
    model = os.getenv("MODEL_NAME", "gemma4:31b-cloud")
    api_key = os.getenv("MODEL_API_KEY", "")
    base_url = os.getenv("BASE_URL", "")

    if provider == "ollama" and not base_url:
        base_url = "http://localhost:11434/v1"

    client = AsyncOpenAI(api_key=api_key or "sk-unset", base_url=base_url or None)

    messages: list[dict] = []
    if params.systemPrompt:
        messages.append({"role": "system", "content": params.systemPrompt})
    for sm in params.messages:
        content = sm.content
        text = content.text if isinstance(content, TextContent) else str(content)
        messages.append({"role": sm.role, "content": text})

    response = await client.chat.completions.create(
        model=params.modelPreferences.model if params.modelPreferences else model,
        messages=messages,
        max_tokens=params.maxTokens,
        temperature=params.temperature or 0.7,
    )

    reply = response.choices[0].message.content or ""
    return CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text=reply),
        model=response.model,
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Use mock responses")
    args = parser.parse_args()

    sampling_fn = mock_sampling_callback if args.mock else openai_sampling_callback

    server_params = StdioServerParameters(
        command=sys.executable or "python",
        args=["examples/sampling_server.py"],
    )

    async with AsyncExitStack() as stack:
        stdio_transport = await stack.enter_async_context(stdio_client(server_params))
        _read, _write = stdio_transport
        session = await stack.enter_async_context(
            ClientSession(_read, _write, sampling_callback=sampling_fn)
        )
        await session.initialize()

        caps = session.get_server_capabilities()
        print(f"Server capabilities: {caps}")
        print()

        # --- List tools ---
        tools_result = await session.list_tools()
        print(f"Available tools ({len(tools_result.tools)}):")
        for t in tools_result.tools:
            print(f"  {t.name}: {t.description}")
        print()

        # --- Exercise summarize ---
        print("=" * 60)
        print("1. summarize")
        print("-" * 60)
        result = await session.call_tool(
            "summarize",
            {"text": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed."},
        )
        for c in result.content:
            print(c.text)
        print()

        # --- Exercise translate ---
        print("=" * 60)
        print("2. translate")
        print("-" * 60)
        result = await session.call_tool(
            "translate",
            {"text": "Hello, how are you?", "language": "hindi"},
        )
        for c in result.content:
            print(c.text)
        print()

        # --- Exercise analyze_sentiment ---
        print("=" * 60)
        print("3. analyze_sentiment")
        print("-" * 60)
        result = await session.call_tool(
            "analyze_sentiment",
            {"text": "I absolutely hate this product! It not works perfectly and exceeded all my expectations."},
        )
        for c in result.content:
            print(c.text)
        print()


if __name__ == "__main__":
    asyncio.run(main())
