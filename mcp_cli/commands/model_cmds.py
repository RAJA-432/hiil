from __future__ import annotations

from mcp_cli.commands.provider_config import _PROVIDER_CONFIG
from mcp_cli.services.credentials import async_load_api_key


async def handle_cmd_model(rest: str, chat, app=None) -> tuple[bool, str]:
    if not rest:
        models = await chat.claude.list_models()
        if models:
            lines = [f"Current model: {chat.claude.model}", f"Available ({len(models)}):"]
            for m in models[:30]:
                lines.append(f"  /model {m['id']}")
            if len(models) > 30:
                lines.append(f"  ... and {len(models) - 30} more")
            return True, "\n".join(lines)
        return True, f"Current model: {chat.claude.model} (no model list available)"
    reply = chat.claude.update_model(rest.strip())
    await chat.refresh_system_prompt()
    return True, reply


async def handle_cmd_models(rest: str, chat, app=None) -> tuple[bool, str]:
    models = await chat.claude.list_models()
    if not models:
        return True, "Could not fetch model list from provider API."
    lines = [f"Available models ({len(models)}):"]
    for m in models[:30]:
        lines.append(f"  {m['id']}")
    if len(models) > 30:
        lines.append(f"  ... and {len(models) - 30} more")
    return True, "\n".join(lines)


async def handle_cmd_provider(rest: str, chat, app=None) -> tuple[bool, str]:
    parts = rest.strip().split()
    if not parts:
        return True, f"Current provider: {chat.claude.provider} ({chat.claude.model})\nUsage: /provider <name> [api_key]"
    provider = parts[0].lower()
    cfg = _PROVIDER_CONFIG.get(provider)
    if not cfg:
        return True, f"Unknown provider '{provider}'. Try: {', '.join(_PROVIDER_CONFIG)}"
    if len(parts) > 1:
        api_key = parts[1]
    else:
        api_key = (await async_load_api_key(provider)) or chat.claude.api_key or ""
    base_url = cfg["base_url"]
    chat.claude.update_provider(provider, api_key, base_url)
    if chat.claude.model == "gpt-4o" or provider == "ollama":
        chat.claude.model = cfg["default_model"]
    await chat.refresh_system_prompt()
    lines = [f"Switched to provider '{provider}' (model: {chat.claude.model})."]
    try:
        models = await chat.claude.list_models()
        if models:
            lines.append("Available models:")
            for m in models:
                lines.append(f"  /model {m['id']}")
        else:
            lines.append("No models returned by provider.")
    except Exception:
        lines.append("Could not fetch model list.")
    return True, "\n".join(lines)
