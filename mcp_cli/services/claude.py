"""
LLM wrapper for OpenRouter / OpenCode providers.

Both providers speak the OpenAI Chat Completions protocol, so we use the
`openai` Python SDK pointed at a provider-specific base URL.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, cast

import httpx
from openai import APIError as OpenAIError
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage
from tenacity import Future, retry, retry_if_exception, stop_after_attempt, wait_exponential

from mcp_cli.services.logging import get_logger

logger = get_logger("claude")

_RETRYABLE_NETWORK = (httpx.TimeoutException, httpx.ConnectError, ConnectionError, TimeoutError)

_EMBED_CACHE_MAXSIZE = 512

def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return (exc.response.status_code or 0) >= 500
    if isinstance(exc, OpenAIError):
        return True
    return isinstance(exc, _RETRYABLE_NETWORK)

_API_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_retryable),
    before_sleep=lambda retry_state: logger.warning(
        "API call failed (attempt %d/%d): %s",
        retry_state.attempt_number, 3, cast(Future, retry_state.outcome).exception(),
    ),
)


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
    ):
        """Initialize the LLM client with provider, model, and API credentials."""
        self.provider = provider
        self.model = str(model)
        self.api_key = api_key
        self.base_url = base_url
        effective_key = api_key or "ollama-placeholder"
        self._client = AsyncOpenAI(api_key=effective_key, base_url=base_url, timeout=120)
        self._http_client = httpx.AsyncClient(timeout=30)
        self._caps_cache: dict[tuple[str, str], tuple[float, list[str]]] = {}
        self._embed_cache: OrderedDict[tuple[str, str, str], list[float]] = OrderedDict()

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = 8192,
        response_format: dict[str, Any] | None = None,
    ):
        """Stream a chat completion, yielding content chunks and tool calls."""
        kwargs: dict[str, Any] = {
            "model": str(self.model),
            "messages": messages,
            "stream": True,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if response_format:
            kwargs["response_format"] = response_format

        response = await self._client.chat.completions.create(**kwargs)

        full_content: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}

        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            if delta.content:
                full_content.append(delta.content)
                yield "content", delta.content

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": tc.id or "",
                            "function": {
                                "name": tc.function.name or "",
                                "arguments": tc.function.arguments or "",
                            },
                        }
                    else:
                        if tc.function and tc.function.arguments:
                            tool_calls[idx]["function"]["arguments"] += tc.function.arguments
                        if tc.function and tc.function.name:
                            tool_calls[idx]["function"]["name"] += tc.function.name
                        if tc.id:
                            tool_calls[idx]["id"] += tc.id

        if tool_calls:
            sorted_calls = sorted(tool_calls.items(), key=lambda x: x[0])
            for idx, tc_data in sorted_calls:
                yield "tool_call", {
                    "id": tc_data["id"],
                    "name": tc_data["function"]["name"],
                    "arguments": tc_data["function"]["arguments"],
                }

        if full_content:
            yield "done", "".join(full_content)
        elif not tool_calls:
            yield "done", ""

    @_API_RETRY
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> Any:
        """
        Send a chat completion request.

        `messages` is a list of OpenAI-style message dicts.
        `tools` is an optional list of OpenAI-style function-tool dicts.
        `response_format` is an optional dict (e.g. ``{"type": "json_object"}``
        or ``{"type": "json_schema", "json_schema": {...}}``).

        Returns an OpenAI `ChatCompletionMessage` (with `.content` and
        `.tool_calls`). Some OpenAI-compatible proxies return a plain string
        or dict instead of a full ChatCompletion; we normalize those.
        """
        kwargs: dict[str, Any] = {
            "model": str(self.model),
            "messages": messages,
            "max_tokens": 8192,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if response_format:
            kwargs["response_format"] = response_format

        response = await self._client.chat.completions.create(**kwargs)

        # --- Normalize non-standard responses -------------------------------
        # Some OpenCode-style proxies reply with the assistant text directly.
        if isinstance(response, str):
            return ChatCompletionMessage(role="assistant", content=response)

        # A raw dict (unparsed) response: pull the message out if present.
        if isinstance(response, dict):
            if not response.get("choices"):
                return ChatCompletionMessage(role="assistant", content="")
            msg = response["choices"][0].get("message", {})
            # Normalize tool_calls if present
            tool_calls = msg.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                # Ensure each tool_call has proper structure
                tool_calls = [
                    tc if hasattr(tc, "function") else _normalize_tool_call(tc)
                    for tc in tool_calls
                ]
            return ChatCompletionMessage(
                role="assistant",
                content=msg.get("content"),
                tool_calls=tool_calls,
            )

        # Standard OpenAI response - validate before accessing
        try:
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message
        except (AttributeError, IndexError) as e:
            logger.warning("Unexpected response structure: %s", e)
            return ChatCompletionMessage(role="assistant", content="")

        # Fallback for empty response
        return ChatCompletionMessage(role="assistant", content="")

    def update_model(self, model: str) -> str:
        """Switch the active model and return a confirmation message."""
        self.model = str(model)
        return f"Model switched to '{self.model}'."

    def update_provider(self, provider: str, api_key: str, base_url: str) -> str:
        """Switch the active provider, re-create the API client, and return confirmation."""
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self._recreate_client()
        return f"Provider switched to '{provider}'."

    def _recreate_client(self):
        effective_key = self.api_key or "ollama-placeholder"
        self._client = AsyncOpenAI(api_key=effective_key, base_url=self.base_url)

    def status_info(self) -> dict[str, str]:
        """Return the current provider and model as a dict."""
        return {"provider": self.provider, "model": self.model}

    def system_prompt(self, format_instructions: str | None = None) -> str:
        """Generate the system prompt including current provider and model.

        ``format_instructions`` is an optional block of output-format
        guidance appended to the base prompt (e.g. schema rules,
        required structure, style constraints).  When provided the LLM
        is told to follow it before the generic instruction.
        """
        base = (
            f"You are an AI assistant with access to MCP tools. "
            f"Current provider: {self.provider}. Current model: {self.model}."
        )
        if format_instructions:
            return (
                f"{base}\n\n"
                f"## Output Format Requirements\n"
                f"{format_instructions}\n\n"
                f"Respond helpfully and use tools when appropriate."
            )
        return f"{base} Respond helpfully and use tools when appropriate."

    def _api_path(self, path: str) -> str:
        if self.provider == "ollama":
            base = (self.base_url or "").rstrip("/v1").rstrip("/")
            return f"{base}/api/{path}"
        base = (self.base_url or "").rstrip("/")
        return f"{base}/{path}"

    @_API_RETRY
    async def embed(self, text: str, model: str | None = None) -> list[float]:
        """Return a vector embedding for the given text via the provider's embeddings endpoint."""
        embed_model = model or self.model
        key = (self.provider, embed_model, text)
        cached = self._embed_cache.get(key)
        if cached is not None:
            self._embed_cache.move_to_end(key)
            return cached

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            if self.provider == "ollama":
                url = self._api_path("embed")
                payload = {"model": embed_model, "input": text}
                resp = await self._http_client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                emb = data.get("embeddings", [])
                emb = emb[0] if emb else []
            else:
                url = self._api_path("embeddings")
                payload = {"model": embed_model, "input": text}
                resp = await self._http_client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                emb = data["data"][0]["embedding"]
        except _RETRYABLE_NETWORK:
            raise
        except Exception as exc:
            logger.warning("embedding failed from %s: %s", url, exc)
            return []

        if emb:
            self._embed_cache[key] = emb
            self._embed_cache.move_to_end(key)
            if len(self._embed_cache) > _EMBED_CACHE_MAXSIZE:
                self._embed_cache.popitem(last=False)
        return emb

    @_API_RETRY
    async def list_models(self) -> list[dict[str, Any]]:
        """Fetch the available models list from the provider's API."""
        url = self._api_path("tags" if self.provider == "ollama" else "models")
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            resp = await self._http_client.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", data.get("models", []))
            if isinstance(models, list):
                return [
                    {"id": m.get("id") or m.get("name", ""), "name": m.get("name") or m.get("id", "")}
                    for m in models
                ]
        except _RETRYABLE_NETWORK:
            raise
        except Exception as exc:
            logger.warning("failed to list models from %s: %s", url, exc)
        return []

    async def model_capabilities(self, model: str) -> list[str]:
        """Return the capabilities advertised for the given Ollama model."""
        if self.provider != "ollama":
            return []
        key = (self.base_url or "", model)
        cached = self._caps_cache.get(key)
        if cached and time.monotonic() - cached[0] < 300:
            return list(cached[1])
        url = self._api_path("tags")
        try:
            resp = await self._http_client.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            caps: list[str] = []
            short = model.split("/")[-1]
            for m in data.get("models", []):
                if m.get("name") == model or m.get("id") == model or m.get("name") == short:
                    caps = list(m.get("capabilities") or [])
                    break
            self._caps_cache[key] = (time.monotonic(), caps)
            return caps
        except Exception as exc:
            logger.warning("failed to query model capabilities for %s: %s", model, exc)
            return []

    async def shutdown(self):
        await self._http_client.aclose()


def _normalize_tool_call(tc: Any) -> Any:
    """Ensure tool_call has proper OpenAI function-call structure."""
    if isinstance(tc, dict):
        if "function" not in tc and ("name" in tc or "arguments" in tc):
            # Wrap legacy format into function structure
            tc["function"] = {
                "name": tc.get("name", "unknown"),
                "arguments": tc.get("arguments", "{}"),
            }
    return tc


Claude = LLMClient  # backward compat alias
