from __future__ import annotations


async def handle_load(chat, body: str) -> str:
    """Load and add a new MCP server from a script path."""
    parts = body.strip().split(maxsplit=1)
    if not parts:
        return "Usage: /load <script_path> [id]"
    script = parts[0]
    server_id = parts[1] if len(parts) > 1 else script.split('/')[-1].replace('.py', '')
    return await chat.add_server(server_id, script)


async def handle_unload(chat, body: str) -> str:
    """Unload and remove an MCP server by server ID."""
    server_id = body.strip()
    if not server_id:
        return "Usage: /unload <server_id>"
    return await chat.remove_server(server_id)


async def handle_reload(chat, body: str) -> str:
    """Reload an MCP server, optionally with a new script path."""
    parts = body.strip().split(maxsplit=1)
    if not parts:
        return "Usage: /reload <server_id> [script_path]"
    server_id = parts[0]
    script = parts[1] if len(parts) > 1 else ""
    if not script:
        client = chat.clients.get(server_id)
        if client is None:
            return f"Server '{server_id}' not found."
        return await chat.reload_server(server_id, client.script)
    return await chat.reload_server(server_id, script)
