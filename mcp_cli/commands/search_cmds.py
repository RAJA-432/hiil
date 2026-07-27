from __future__ import annotations


async def handle_cmd_search(rest: str, chat, app=None) -> tuple[bool, str | None]:
    query = rest.strip()
    if not query:
        return True, "Usage: /search <query>"
    results = await chat.history.async_search_messages(chat.session_id, query)
    if not results:
        return True, f"No matches for '{query}' in this session."
    if app:
        app._print_search_results(query, results)
    return True, None


async def handle_cmd_semsearch(rest: str, chat, app=None) -> tuple[bool, str]:
    if not rest:
        return True, "Usage: /semsearch <query>"
    results = await chat.semantic_search(rest, limit=10)
    if not results:
        return True, "No semantic matches found."
    lines = [f"Semantic search results for: {rest}"]
    for r in results:
        lines.append(f"  [{r['score']}] {r['text'][:120]}")
    return True, "\n".join(lines)


async def handle_cmd_copy(rest: str, chat, app=None) -> tuple[bool, str]:
    last = chat.get_last_assistant_message()
    if last:
        try:
            import pyperclip
            pyperclip.copy(last)
            return True, f"Copied last assistant message ({len(last)} chars) to clipboard."
        except ImportError:
            return True, f"Last assistant message ({len(last)} chars):\n{last}"
    return True, "No assistant message to copy."
