from __future__ import annotations

import json
from datetime import datetime

from mcp_cli.commands.agent import handle_agent_cmd
from mcp_cli.commands.plan import handle_plan_cmd
from mcp_cli.commands.servers import handle_load, handle_reload, handle_unload
from mcp_cli.locales import available_labels, set_lang
from mcp_cli.locales import get as get_locale
from mcp_cli.services.credentials import async_delete_api_key, async_load_api_key, async_save_api_key

_PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "default_model": "gpt-4o-mini"},
    "ollama": {"base_url": "http://localhost:11434/v1", "default_model": "gemma4:31b-cloud"},
    "opencode": {"base_url": "https://api.opencode.ai/v1", "default_model": "gpt-4o"},
}


def _provider_base_url(provider: str) -> str:
    cfg = _PROVIDER_CONFIG.get(provider)
    return cfg["base_url"] if cfg else ""


async def route_tool_command(chat, body: str) -> str:
    """Route a direct tool call by name and return its response."""
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
    """Route a /command. Returns (should_continue, reply)."""
    stripped = user_input.lstrip("/")
    if not stripped:
        return True, None
    parts = stripped.strip().split(maxsplit=1)
    raw = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""
    loc = get_locale()
    cmd = loc.resolve_cmd(raw)
    if cmd is None:
        cmd = raw

    if cmd == "timer":
        t0 = chat.__dict__.get("_timer_start") if hasattr(chat, "__dict__") else getattr(chat, "_timer_start", None)
        action = rest.strip().lower()
        if action == "start":
            chat._timer_start = datetime.now()
            return True, "Timer started."
        if action == "stop":
            if t0 is None:
                return True, "No timer running."
            elapsed = (datetime.now() - t0).total_seconds()
            chat._timer_start = None
            mins, secs = divmod(int(elapsed), 60)
            return True, f"Timer stopped: {mins}m {secs}s"
        if t0 is None:
            return True, "No timer running. Use /timer start to begin."
        elapsed = (datetime.now() - t0).total_seconds()
        mins, secs = divmod(int(elapsed), 60)
        return True, f"Timer running: {mins}m {secs}s"

    if cmd in ("lang", "language"):
        if not rest:
            current = get_locale()
            labels = ", ".join(available_labels())
            return True, f"Current language: {current.label}  Available: {labels}"
        lang_map = {"en": "en", "english": "en"}
        target = lang_map.get(rest.strip().lower())
        if target is None:
            return True, f"Unknown language '{rest}'. Available: {', '.join(available_labels())}"
        label = set_lang(target)
        if app:
            app._locale = get_locale()
            app._update_completer()
        return True, f"Switched to {label}"

    if cmd == "help":
        if app:
            app._print_help()
        return True, None

    if cmd == "tools":
        return True, f"Tools: {', '.join(chat.tools_by_name.keys())}"

    if cmd == "servers":
        return True, f"Active Servers: {', '.join(chat.clients.keys())}"

    if cmd == "theme":
        if not rest:
            from mcp_cli.ui.themes import THEMES
            names = ", ".join(THEMES.keys())
            if app:
                return True, f"Current theme: {app._theme.name}  Available: {names}"
            return True, None
        if app:
            reply = app._set_theme(rest.strip())
            return True, reply
        return True, None

    if cmd == "load":
        reply = await handle_load(chat, rest)
        return True, reply

    if cmd == "unload":
        reply = await handle_unload(chat, rest)
        return True, reply

    if cmd == "reload":
        reply = await handle_reload(chat, rest)
        return True, reply

    if cmd == "history":
        if app:
            await app._handle_history(rest)
        return True, None

    if cmd == "sessions":
        if app:
            await app._handle_list_sessions()
        return True, None

    if cmd == "session":
        if app:
            await app._handle_switch_session(user_input[9:])
        return True, None

    if cmd == "usage":
        if app:
            app._print_usage()
        return True, None

    if cmd in ("exit", "quit"):
        return False, None

    if cmd == "new":
        sid = chat.new_session()
        if app:
            app._update_completer()
        return True, f"Started new session: {sid}"

    if cmd == "model":
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
        chat.refresh_system_prompt()
        return True, reply

    if cmd == "semsearch":
        if not rest:
            return True, "Usage: /semsearch <query>"
        results = await chat.semantic_search(rest, limit=10)
        if not results:
            return True, "No semantic matches found."
        lines = [f"Semantic search results for: {rest}"]
        for r in results:
            lines.append(f"  [{r['score']}] {r['text'][:120]}")
        return True, "\n".join(lines)

    if cmd == "models":
        models = await chat.claude.list_models()
        if not models:
            return True, "Could not fetch model list from provider API."
        lines = [f"Available models ({len(models)}):"]
        for m in models[:30]:
            lines.append(f"  {m['id']}")
        if len(models) > 30:
            lines.append(f"  ... and {len(models) - 30} more")
        return True, "\n".join(lines)

    if cmd == "rename":
        name = rest.strip()
        if not name:
            return True, "Usage: /rename <name>"
        old = chat.session_id
        if await chat.history.async_rename_session(old, name):
            chat.session_id = name
            return True, f"Session renamed from '{old}' to '{name}'."
        return True, "Session not found."

    if cmd == "copy":
        last = chat.get_last_assistant_message()
        if last:
            try:
                import pyperclip
                pyperclip.copy(last)
                return True, f"Copied last assistant message ({len(last)} chars) to clipboard."
            except ImportError:
                return True, f"Last assistant message ({len(last)} chars):\n{last}"
        return True, "No assistant message to copy."

    if cmd == "status":
        if app:
            app._print_status()
        return True, None

    if cmd == "export":
        transcript = chat.export_transcript()
        name = f"transcript_{chat.session_id}.txt"
        try:
            with open(name, "w", encoding="utf-8") as f:
                f.write(transcript)
            return True, f"Transcript exported to {name} ({len(transcript)} chars)."
        except Exception as exc:
            return True, f"Export failed: {exc}"

    if cmd == "timestamp" or cmd == "timestamps":
        if app:
            app._timestamps_enabled = not app._timestamps_enabled
            state = "on" if app._timestamps_enabled else "off"
            return True, f"Timestamps {state}."
        return True, None

    if cmd == "fork":
        sid = rest.strip()
        if not sid:
            return True, "Usage: /fork <session_id>"
        new_id = f"fork_{sid}_{datetime.now().strftime('%H%M%S')}"
        count = await chat.history.async_fork_session(sid, new_id)
        if count:
            chat.session_id = new_id
            chat.messages = await chat.history.async_load_session(new_id)
            if app:
                app._update_completer()
            return True, f"Forked {count} messages from '{sid}' into '{new_id}'."
        return True, f"Source session '{sid}' not found."

    if cmd == "search":
        query = rest.strip()
        if not query:
            return True, "Usage: /search <query>"
        results = await chat.history.async_search_messages(chat.session_id, query)
        if not results:
            return True, f"No matches for '{query}' in this session."
        if app:
            app._print_search_results(query, results)
        return True, None

    if cmd == "undo":
        count_str = rest.strip()
        count = int(count_str) if count_str.isdigit() else 2
        removed = await chat.history.async_undo_last_messages(chat.session_id, count)
        if removed:
            chat.messages = await chat.history.async_load_session(chat.session_id)
            return True, f"Removed {removed} message(s)."
        return True, "Nothing to undo."

    if cmd == "compact":
        count = len(chat.messages)
        if count < 4:
            return True, "Too few messages to compact."
        summary = f"[Session compacted: {chat.session_id} had {count} messages]"
        chat.messages = [
            {"role": "system", "content": summary},
            *chat.messages[-4:],
        ]
        return True, f"Session compacted from {count} to {len(chat.messages)} messages."

    if cmd == "provider":
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
        chat.refresh_system_prompt()
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

    if cmd == "key":
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

    if cmd == "ls":
        path = rest.strip() or "."
        return True, await chat.call_tool_by_name("list_directory", {"path": path})

    if cmd == "roots":
        roots = chat.list_roots()
        if not roots:
            return True, "No roots configured. Add them to the `roots:` section in config.yaml."
        lines = ["Approved root directories:"]
        for r in roots:
            lines.append(f"  {r['name']}: {r['path']}")
        return True, "\n".join(lines)

    if cmd == "agent":
        subcmd_parts = rest.strip().split(maxsplit=1)
        subcmd = subcmd_parts[0].lower() if subcmd_parts else ""
        sub_rest = subcmd_parts[1] if len(subcmd_parts) > 1 else ""
        if subcmd == "respond":
            return True, "The /agent respond command has been removed."
        reply = await handle_agent_cmd(chat, subcmd, sub_rest, app._session.prompt_async if app else lambda _: "")
        return True, reply

    if cmd == "plan":
        reply = await handle_plan_cmd(chat, app)
        return True, reply

    reply = await route_tool_command(chat, user_input[1:])
    return True, reply
