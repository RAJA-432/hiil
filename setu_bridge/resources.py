from __future__ import annotations

import json

from mcp import ClientSession, types
from pydantic import AnyUrl


async def list_resources(session: ClientSession) -> list[types.Resource]:
    result = await session.list_resources()
    return result.resources


async def read_resource(session: ClientSession, uri: str) -> types.Any:
    result = await session.read_resource(AnyUrl(uri))
    if not result.contents:
        return None
    resource = result.contents[0]
    if isinstance(resource, types.TextResourceContents):
        if resource.mimeType == "application/json":
            return json.loads(resource.text)
        return resource.text
    return getattr(resource, "text", resource)
