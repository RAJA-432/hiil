from __future__ import annotations

from datetime import datetime


async def handle_cmd_new(rest: str, chat, app=None) -> tuple[bool, str]:
    sid = chat.new_session()
    if app:
        app._update_completer()
    return True, f"Started new session: {sid}"


async def handle_cmd_session(rest: str, chat, app=None) -> tuple[bool, str | None]:
    if app:
        await app._handle_switch_session(rest)
    return True, None


async def handle_cmd_sessions(rest: str, chat, app=None) -> tuple[bool, str | None]:
    if app:
        await app._handle_list_sessions()
    return True, None


async def handle_cmd_history(rest: str, chat, app=None) -> tuple[bool, str | None]:
    if app:
        await app._handle_history(rest)
    return True, None


async def handle_cmd_rename(rest: str, chat, app=None) -> tuple[bool, str]:
    name = rest.strip()
    if not name:
        return True, "Usage: /rename <name>"
    old = chat.session_id
    if await chat.history.async_rename_session(old, name):
        chat.session_id = name
        return True, f"Session renamed from '{old}' to '{name}'."
    return True, "Session not found."


async def handle_cmd_fork(rest: str, chat, app=None) -> tuple[bool, str]:
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


async def handle_cmd_compact(rest: str, chat, app=None) -> tuple[bool, str]:
    count = len(chat.messages)
    if count < 4:
        return True, "Too few messages to compact."
    summary = f"[Session compacted: {chat.session_id} had {count} messages]"
    chat.messages = [
        {"role": "system", "content": summary},
        *chat.messages[-4:],
    ]
    return True, f"Session compacted from {count} to {len(chat.messages)} messages."


async def handle_cmd_undo(rest: str, chat, app=None) -> tuple[bool, str]:
    count_str = rest.strip()
    count = int(count_str) if count_str.isdigit() else 2
    removed = await chat.history.async_undo_last_messages(chat.session_id, count)
    if removed:
        chat.messages = await chat.history.async_load_session(chat.session_id)
        return True, f"Removed {removed} message(s)."
    return True, "Nothing to undo."
