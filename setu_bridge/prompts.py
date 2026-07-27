from __future__ import annotations

from mcp import ClientSession, types


async def list_prompts(session: ClientSession) -> list[types.Prompt]:
    result = await session.list_prompts()
    return result.prompts


async def get_prompt(session: ClientSession, prompt_name: str, args: dict[str, str]):
    result = await session.get_prompt(prompt_name, args)
    return result.messages
