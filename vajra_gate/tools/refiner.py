from __future__ import annotations

import argparse

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import SamplingMessage, TextContent

from vajra_gate.schemas.output_schemas import SKILL_OUTPUT_SCHEMAS

mcp = FastMCP("refiner")


@mcp.tool()
async def refine_output(
    raw_text: str,
    skill_id: str,
    ctx: Context,
) -> str:
    """Restructure raw LLM output to match a skill's expected output format.

    Looks up the registered schema for the given ``skill_id``, builds a
    refinement prompt that includes the schema's formatting instructions
    and an example, then delegates the actual LLM call to the client via
    the MCP sampling protocol (``ctx.session.create_message``).

    Args:
        raw_text: The raw LLM output text to reformat.
        skill_id: Target skill identifier (e.g. ``data-analyst``, ``code-reviewer``).
    """
    schema = SKILL_OUTPUT_SCHEMAS.get(skill_id)
    if schema is None:
        available = ", ".join(SKILL_OUTPUT_SCHEMAS)
        return f"Unknown skill_id '{skill_id}'. Available: {available}"

    prompt = (
        f"Reformat the following text to match the required output structure.\n\n"
        f"## Required Format Instructions\n{schema.instructions}\n\n"
        f"## Example of Correct Format\n{schema.example}\n\n"
        f"## Raw Text to Refine\n{raw_text}\n\n"
        f"Return ONLY the reformatted version. "
        f"Do not include any explanation, preamble, or commentary."
    )

    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ],
        max_tokens=8192,
        system_prompt="You are a formatting assistant. Reformat text exactly as instructed. Return only the reformatted output with no extra commentary.",
    )

    if result.content.type == "text":
        return result.content.text

    raise ValueError("Refinement failed — unexpected response type from sampling")


def main() -> None:
    parser = argparse.ArgumentParser(description="Refiner MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8300)
    args = parser.parse_args()
    if args.transport == "sse":
        import uvicorn
        uvicorn.run(mcp.sse_app(), host="127.0.0.1", port=args.port)
    elif args.transport == "streamable-http":
        import uvicorn
        uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
