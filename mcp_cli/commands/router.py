from __future__ import annotations

import json

from mcp_cli.commands.agent import handle_agent_cmd
from mcp_cli.commands.key_cmds import handle_cmd_key
from mcp_cli.commands.misc_cmds import (
    handle_cmd_exit,
    handle_cmd_export,
    handle_cmd_help,
    handle_cmd_lang,
    handle_cmd_ls,
    handle_cmd_roots,
    handle_cmd_servers,
    handle_cmd_status,
    handle_cmd_theme,
    handle_cmd_timer,
    handle_cmd_timestamp,
    handle_cmd_tools,
    handle_cmd_usage,
)
from mcp_cli.commands.model_cmds import handle_cmd_model, handle_cmd_models, handle_cmd_provider
from mcp_cli.commands.plan import handle_plan_cmd
from mcp_cli.commands.search_cmds import handle_cmd_copy, handle_cmd_search, handle_cmd_semsearch
from mcp_cli.commands.servers import handle_load, handle_reload, handle_unload
from mcp_cli.commands.session_cmds import (
    handle_cmd_compact,
    handle_cmd_fork,
    handle_cmd_history,
    handle_cmd_new,
    handle_cmd_rename,
    handle_cmd_session,
    handle_cmd_sessions,
    handle_cmd_undo,
)
from mcp_cli.locales import get as get_locale

_CMD_HANDLERS = {
    "timer": handle_cmd_timer,
    "lang": handle_cmd_lang,
    "language": handle_cmd_lang,
    "help": handle_cmd_help,
    "tools": handle_cmd_tools,
    "servers": handle_cmd_servers,
    "theme": handle_cmd_theme,
    "history": handle_cmd_history,
    "sessions": handle_cmd_sessions,
    "session": handle_cmd_session,
    "usage": handle_cmd_usage,
    "exit": handle_cmd_exit,
    "quit": handle_cmd_exit,
    "new": handle_cmd_new,
    "model": handle_cmd_model,
    "semsearch": handle_cmd_semsearch,
    "models": handle_cmd_models,
    "rename": handle_cmd_rename,
    "copy": handle_cmd_copy,
    "status": handle_cmd_status,
    "export": handle_cmd_export,
    "timestamp": handle_cmd_timestamp,
    "timestamps": handle_cmd_timestamp,
    "fork": handle_cmd_fork,
    "search": handle_cmd_search,
    "undo": handle_cmd_undo,
    "compact": handle_cmd_compact,
    "provider": handle_cmd_provider,
    "key": handle_cmd_key,
    "ls": handle_cmd_ls,
    "roots": handle_cmd_roots,
}

_SPECIAL_HANDLERS = {
    "load": handle_load,
    "unload": handle_unload,
    "reload": handle_reload,
    "agent": handle_agent_cmd,
    "plan": handle_plan_cmd,
}


async def route_tool_command(chat, body: str) -> str:
    parts = body.split(maxsplit=1)
    name = parts[0]
    arg_str = parts[1] if len(parts) > 1 else ""
    entry = chat.tools_by_name.get(name)
    if entry is None:
        loc = get_locale()
        for eng_name in chat.tools_by_name:
            if loc.translate_tool(eng_name) == name:
                entry = chat.tools_by_name[eng_name]
                name = eng_name
                break
    if entry is None:
        return f"Unknown command or tool: {name}"
    if arg_str.strip().startswith("{"):
        try:
            args = json.loads(arg_str)
        except json.JSONDecodeError:
            args = {}
    elif arg_str:
        first_param = next(
            iter(entry["openai"]["function"]["parameters"].get("properties", {})),
            "arg",
        )
        args = {first_param: arg_str}
    else:
        args = {}
    return await chat.call_tool_by_name(name, args)


async def route_command(user_input: str, chat, app=None) -> tuple[bool, str | None]:
    stripped = user_input.lstrip("/")
    if not stripped:
        return True, None
    parts = stripped.strip().split(maxsplit=1)
    raw = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""
    loc = get_locale()

    eng = loc.resolve_cmd(raw)
    if eng is None:
        eng = raw

    handler = _CMD_HANDLERS.get(eng)
    if handler is not None:
        return await handler(rest, chat, app)

    special = _SPECIAL_HANDLERS.get(eng)
    if special is not None:
        if eng == "agent":
            subcmd_parts = rest.strip().split(maxsplit=1)
            subcmd = subcmd_parts[0].lower() if subcmd_parts else ""
            sub_rest = subcmd_parts[1] if len(subcmd_parts) > 1 else ""
            if subcmd == "respond":
                return True, "The /agent respond command has been removed."
            prompt_async = app._session.prompt_async if app else lambda _: ""
            return True, await special(chat, subcmd, sub_rest, prompt_async)
        if eng == "plan":
            return True, await special(chat, app)
        return True, await special(chat, rest)

    reply = await route_tool_command(chat, user_input[1:])
    return True, reply
