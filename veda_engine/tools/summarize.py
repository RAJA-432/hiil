from __future__ import annotations

from mcp.server.fastmcp import Context
from mcp.types import SamplingMessage, TextContent
from pydantic import Field

_MAX_INPUT_CHARS = 100_000


async def summarize(
    text_to_summarize: str = Field(description="Text content to summarize"),
    *,
    ctx: Context,
    max_tokens: int = Field(
        default=4000,
        description="Maximum number of tokens in the summary",
        ge=1,
        le=32768,
    ),
) -> str:
    """Summarize text by asking the client LLM via the sampling protocol.

    The server has no API key — it delegates the LLM call back to the
    client through ``ctx.session.create_message()``.
    """
    if len(text_to_summarize) > _MAX_INPUT_CHARS:
        text_to_summarize = (
            text_to_summarize[:_MAX_INPUT_CHARS]
            + f"\n[truncated at {_MAX_INPUT_CHARS} chars]"
        )
    prompt = f"Please summarize the following text:\n\n{text_to_summarize}"

    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ],
        max_tokens=max_tokens,
        system_prompt="You are a helpful research assistant.",
    )

    if result.content.type == "text":
        return result.content.text

    raise ValueError("Sampling failed — unexpected response type")
