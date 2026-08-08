from __future__ import annotations

from collections.abc import Callable

from mcp_cli.ui.themes import RS


async def handle_history(chat, session_id: str, theme, format_timestamp: Callable[[str], str]) -> None:
    sid = session_id.strip() or chat.session_id
    msgs = await chat.history.async_load_session(sid)
    if not msgs:
        print(f"{theme.ansi('muted')}No messages in session '{sid}'.{RS}")
        return
    print(f"{theme.ansi('secondary')}--- History: {sid} ({len(msgs)} messages) ---{RS}")
    for m in msgs[-20:]:
        preview = m["content"][:120].replace("\n", " ")
        ts = format_timestamp(m.get("timestamp", ""))
        print(f"  {theme.ansi('primary') if m['role'] == 'assistant' else theme.ansi('muted')}{m['role']}:{RS}{ts} {preview}")


async def handle_list_sessions(chat, theme) -> None:
    sessions = await chat.history.async_list_sessions()
    if not sessions:
        print(f"{theme.ansi('muted')}No saved sessions.{RS}")
        return
    print(f"{theme.ansi('secondary')}Sessions:{RS}")
    for s in sessions:
        marker = " *" if s == chat.session_id else ""
        print(f"  {theme.ansi('primary')}{s}{RS}{marker}")


async def handle_switch_session(chat, session_id: str, theme) -> None:
    sid = session_id.strip()
    if not sid:
        print(f"{theme.ansi('error')}Usage: /session <session_id>{RS}")
        return
    chat.session_id = sid
    chat.messages = await chat.history.async_load_session(sid)
    print(f"{theme.ansi('success')}Switched to session '{sid}' ({len(chat.messages)} messages).{RS}")


async def handle_search(chat, query: str, theme, format_timestamp: Callable[[str], str]) -> None:
    # Use the HistoryManager via the chat service for a global search
    results = chat.history.search(query)

    if not results:
        print(f"{theme.ansi('muted')}No matches found for '{query}'.{RS}")
        return

    print(f"{theme.ansi('secondary')}--- Search: '{query}' ({len(results)} results) ---{RS}")
    for r in results:
        role = r.get("role", "unknown")
        content = r.get("content", "")
        preview = content[:120].replace("\n", " ")
        ts = format_timestamp(r.get("timestamp", ""))

        color = theme.ansi('primary') if role == 'assistant' else theme.ansi('muted')
        print(f"  {color}{role}:{RS}{ts} {preview}")
