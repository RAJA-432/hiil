from __future__ import annotations

import json
from typing import Any

from openai.types.chat import ChatCompletionMessage
from openai.types.chat.chat_completion_message_function_tool_call import Function
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall

from mcp_cli.services.logging import get_logger

logger = get_logger("streamer")


class Streamer:
    def __init__(self, claude: Any):
        self.claude = claude

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        on_chunk: Any = None,
    ) -> tuple[ChatCompletionMessage, int, int]:
        input_text = json.dumps([m.get("content", "") for m in messages])
        from mcp_cli.services.usage import count_tokens
        input_tokens = count_tokens(input_text, self.claude.model)

        if on_chunk:
            return await self._stream(messages, tools, on_chunk, input_tokens)
        message = await self.claude.chat(messages, tools=tools)
        output_text = message.content or ""
        output_tokens = count_tokens(output_text, self.claude.model)
        return message, input_tokens, output_tokens

    async def _stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        on_chunk: Any,
        input_tokens: int,
    ) -> tuple[ChatCompletionMessage, int, int]:
        from mcp_cli.services.usage import count_tokens
        content_parts: list[str] = []
        streamed_tool_calls: list[ChatCompletionMessageToolCall] = []
        try:
            async for kind, data in self.claude.stream_chat(messages, tools=tools):
                if kind == "content":
                    content_parts.append(data)
                    on_chunk(data)
                elif kind == "tool_call":
                    streamed_tool_calls.append(
                        ChatCompletionMessageToolCall(
                            id=data["id"],
                            function=Function(
                                name=data["name"],
                                arguments=data["arguments"],
                            ),
                            type="function",
                        )
                    )
        except Exception:
            logger.exception("streaming failed, falling back to non-streaming")
            message = await self.claude.chat(messages, tools=tools)
            output_text = message.content or ""
            output_tokens = count_tokens(output_text, self.claude.model)
            return message, input_tokens, output_tokens
        full_content = "".join(content_parts)
        message = ChatCompletionMessage(
            role="assistant",
            content=full_content or None,
            tool_calls=streamed_tool_calls or None, # type: ignore
        )
        output_tokens = count_tokens(full_content, self.claude.model)
        return message, input_tokens, output_tokens
