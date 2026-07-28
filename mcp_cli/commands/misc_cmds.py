from __future__ import annotations

import asyncio
from datetime import datetime

from mcp_cli.locales import available_labels, set_lang
from mcp_cli.locales import get as get_locale


async def handle_cmd_timer(rest: str, chat, app=None) -> tuple[bool, str]:
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


async def handle_cmd_lang(rest: str, chat, app=None) -> tuple[bool, str | None]:
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


async def handle_cmd_help(rest: str, chat, app=None) -> tuple[bool, str | None]:
    if app:
        app._print_help()
    return True, None


async def handle_cmd_tools(rest: str, chat, app=None) -> tuple[bool, str]:
    return True, f"Tools: {', '.join(chat.tools_by_name.keys())}"


async def handle_cmd_servers(rest: str, chat, app=None) -> tuple[bool, str]:
    return True, f"Active Servers: {', '.join(chat.clients.keys())}"


async def handle_cmd_theme(rest: str, chat, app=None) -> tuple[bool, str | None]:
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


async def handle_cmd_status(rest: str, chat, app=None) -> tuple[bool, str | None]:
    if app:
        app._print_status()
    return True, None


async def handle_cmd_usage(rest: str, chat, app=None) -> tuple[bool, str | None]:
    if app:
        app._print_usage()
    return True, None


async def handle_cmd_ls(rest: str, chat, app=None) -> tuple[bool, str]:
    path = rest.strip() or "."
    return True, await chat.call_tool_by_name("list_directory", {"path": path})


async def handle_cmd_roots(rest: str, chat, app=None) -> tuple[bool, str]:
    roots = chat.list_roots()
    if not roots:
        return True, "No roots configured. Add them to the `roots:` section in config.yaml."
    lines = ["Approved root directories:"]
    for r in roots:
        lines.append(f"  {r['name']}: {r['path']}")
    return True, "\n".join(lines)


async def handle_cmd_export(rest: str, chat, app=None) -> tuple[bool, str]:
    transcript = chat.export_transcript()
    name = f"transcript_{chat.session_id}.txt"
    try:
        await asyncio.to_thread(lambda: open(name, "w", encoding="utf-8").write(transcript))
        return True, f"Transcript exported to {name} ({len(transcript)} chars)."
    except Exception as exc:
        return True, f"Export failed: {exc}"


async def handle_cmd_timestamp(rest: str, chat, app=None) -> tuple[bool, str | None]:
    if app:
        app._timestamps_enabled = not app._timestamps_enabled
        state = "on" if app._timestamps_enabled else "off"
        return True, f"Timestamps {state}."
    return True, None


async def handle_cmd_exit(rest: str = "", chat=None, app=None) -> tuple[bool, None]:
    return False, None
