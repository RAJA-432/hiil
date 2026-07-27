from __future__ import annotations

from mcp_cli.services.credentials import async_delete_api_key, async_load_api_key, async_save_api_key


async def handle_cmd_key(rest: str, chat, app=None) -> tuple[bool, str]:
    sub = rest.strip().split(maxsplit=1)
    action = sub[0].lower() if sub else "status"
    if action == "set":
        parts = sub[1].split(maxsplit=1) if len(sub) > 1 else []
        if len(parts) < 2:
            return True, "Usage: /key set <provider> <api_key>"
        await async_save_api_key(parts[0], parts[1])
        return True, f"API key for '{parts[0]}' saved to encrypted store."
    elif action == "delete":
        provider = sub[1].strip() if len(sub) > 1 else chat.claude.provider
        if await async_delete_api_key(provider):
            return True, f"API key for '{provider}' deleted."
        return True, f"No stored key for '{provider}'."
    elif action == "status":
        stored = await async_load_api_key(chat.claude.provider)
        if stored:
            masked = stored[:8] + "..." if len(stored) > 12 else "***"
            return True, f"Stored key for '{chat.claude.provider}': {masked}"
        return True, f"No stored key for '{chat.claude.provider}'."
    return True, "Usage: /key set <provider> <key> | /key delete [provider] | /key status"
