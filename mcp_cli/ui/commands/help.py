from __future__ import annotations

from mcp_cli.ui.themes import RS, THEMES

HELP_SECTIONS: list[tuple[str, list[tuple]]] = [
    ("Session", [
        (lambda _: _('new'), "start a new session"),
        (lambda _: _('rename') + " <n>", "rename current session"),
        (lambda _: _('fork') + " <id>", "fork messages from another session"),
        (lambda _: _('compact'), "compact session (collapse old messages)"),
        (lambda _: _('session') + " <id>", "switch to a different session"),
        (lambda _: _('sessions'), "list saved chat sessions"),
        (lambda _: _('history') + " [id]", "show recent messages from a session"),
        (lambda _: _('undo') + " [n]", "undo last n exchanges"),
        (lambda _: _('export'), "export session transcript to file"),
    ]),
    ("Model", [
        (lambda _: _('model') + " [name]", "show or switch the model"),
        (lambda _: _('models'), "list available models from provider"),
        (lambda _: _('provider') + " [name]", "show or switch the provider"),
        (lambda _: _('plan'), "interactive model picker for planning"),
        (lambda _: _('timer'), "session timer (start/stop/status)"),
    ]),
    ("System", [
        (lambda _: _('ls') + " [path]", "list directory contents"),
        (lambda _: _('roots'), "list approved root directories"),
        (lambda _: _('tools'), "list available MCP tools"),
        (lambda _: _('servers'), "list active MCP servers"),
        (lambda _: _('status'), "show system status"),
        (lambda _: _('theme') + " [name]", f"switch theme ({', '.join(THEMES.keys())})"),
        (lambda _: _('usage'), "show token usage and cost"),
        (lambda _: _('search') + " <q>", "search session messages"),
        (lambda _: _('semsearch') + " <q>", "semantic vector search over messages"),
        (lambda _: _('copy'), "copy last assistant message to clipboard"),
        (lambda _: _('key'), "manage encrypted API keys"),
        (lambda _: _('timestamp'), "toggle timestamps in history display"),
        (lambda _: _('lang'), "switch language"),
        (lambda _: _('agent'), "manage agents (subagents: agents/list, run)"),
        (lambda _: _('skill'), "manage skills (create, list, show, delete)"),
    ]),
    ("Server", [
        (lambda _: _('load') + " <script>", "dynamically load a new MCP server"),
        (lambda _: _('unload') + " <id>", "unload an MCP server"),
        (lambda _: _('reload') + " <id>", "restart an MCP server"),
    ]),
    ("Other", [
        (lambda _: "<tool> [args]", "call an MCP tool directly"),
        (lambda _: _('help'), "show this help"),
        (lambda _: _('exit') + " / " + _('quit'), "leave the chat"),
        (lambda _: "@docid", "inject a document from the store"),
        (lambda _: "@all / @*", "inject every document from the store"),
    ]),
    ("Shortcuts", [
        (lambda _: "Tab / arrows", "auto-complete commands and names"),
        (lambda _: "Ctrl+C", "cancel or interrupt"),
    ]),
]


def print_help(theme, locale) -> None:
    def _(eng: str) -> str:
        return locale.translate_cmd(eng)

    def cmd(c: str, desc: str) -> str:
        return f"  {theme.ansi('muted')}/{c:<22}{RS} {theme.ansi('secondary')}{desc}{RS}"

    bar = f"{theme.ansi('muted')}\u2501{RS}" * 78
    print(bar)
    for section_name, entries in HELP_SECTIONS:
        print(f"  {theme.ansi('primary')}{section_name}{RS}")
        for cmd_fn, desc in entries:
            print(cmd(cmd_fn(_), desc))
    print(bar)
