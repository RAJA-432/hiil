"""
MCP server demonstrating sampling: requests LLM text generation from the client.

The client must provide a sampling_callback that fulfills these requests.
"""

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import SamplingMessage, TextContent

mcp = FastMCP("sampling-demo")


@mcp.tool()
async def summarize(text: str, ctx: Context) -> str:
    """Ask the client's LLM to summarize the given text."""
    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=f"Summarize this:\n\n{text}"),
            )
        ],
        max_tokens=1000,
        system_prompt="You are a concise summarizer. Respond in 2-3 sentences.",
    )

    content = result.content
    if isinstance(content, TextContent):
        return content.text
    if isinstance(content, list):
        parts = [b.text for b in content if isinstance(b, TextContent)]
        return "\n".join(parts)
    raise ValueError(f"Unexpected content type: {type(content).__name__}")


@mcp.tool()
async def translate(text: str, language: str, ctx: Context) -> str:
    """Ask the client's LLM to translate text into another language."""
    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"Translate this to {language}:\n\n{text}",
                ),
            )
        ],
        max_tokens=2000,
        system_prompt="You are a translator. Output only the translation.",
    )

    content = result.content
    if isinstance(content, TextContent):
        return content.text
    if isinstance(content, list):
        parts = [b.text for b in content if isinstance(b, TextContent)]
        return "\n".join(parts)
    raise ValueError(f"Unexpected content type: {type(content).__name__}")


@mcp.tool()
async def analyze_sentiment(text: str, ctx: Context) -> str:
    """Ask the client's LLM to analyze the sentiment of the given text."""
    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"Analyze the sentiment of this text:\n\n{text}",
                ),
            )
        ],
        max_tokens=500,
        system_prompt=(
            "You are a sentiment analyzer. "
            "Respond with exactly one word: POSITIVE, NEGATIVE, or NEUTRAL. "
            "Then on a new line, give a one-sentence explanation."
        ),
    )

    content = result.content
    if isinstance(content, TextContent):
        return content.text
    if isinstance(content, list):
        parts = [b.text for b in content if isinstance(b, TextContent)]
        return "\n".join(parts)
    raise ValueError(f"Unexpected content type: {type(content).__name__}")


if __name__ == "__main__":
    mcp.run()
