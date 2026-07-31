from __future__ import annotations

import asyncio
import os
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import FuzzyCompleter
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import FileHistory

from mcp_cli.commands.router import route_command
from mcp_cli.locales import get as get_locale
from mcp_cli.ui.codeblock import CodeBlockAccumulator
from mcp_cli.ui.completers import HiilCompleter
from mcp_cli.ui.messaging import MessageManager, SpinnerManager
from mcp_cli.ui.renderer import get_renderer
from mcp_cli.ui.theme_manager import ThemeManager
from mcp_cli.ui.themes import RS, THEMES
from mcp_cli.ui.tool_events import ToolEventHandler

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
        (lambda _: _('agent'), "manage background agents"),
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


class CliApp:
    def __init__(self, chat: Any, theme_name: str | None = None):
        self.chat = chat
        self._session: PromptSession | None = None
        self._prompt_timeout = float(os.getenv("PROMPT_TIMEOUT", "0"))
        self._theme_mgr = ThemeManager(theme_name)
        self._timestamps_enabled = False
        self._locale = get_locale()
        self._msg = MessageManager()
        self._spinner = SpinnerManager()
        self._codeblocks = CodeBlockAccumulator()
        self._tool_events = ToolEventHandler()

    @property
    def theme(self):
        """Return the current resolved theme instance."""
        return self._theme_mgr.current

    @property
    def _renderer(self):
        return get_renderer()

    @property
    def theme_mgr(self) -> ThemeManager:
        return self._theme_mgr

    def _set_theme(self, name: str) -> str:
        if name not in self._theme_mgr.names:
            return f"Unknown theme '{name}'. Available: {', '.join(self._theme_mgr.names)}"
        old = self._theme_mgr.theme
        self._theme_mgr.theme = name
        if old == name:
            return f"Already using '{self._theme_mgr.current.name}' theme."
        return f"Switched to '{self._theme_mgr.current.name}' theme."

    def _update_completer(self) -> None:
        if self._session is None:
            return
        comp = HiilCompleter(self.chat, self)
        comp.set_metadata()
        self._session.completer = FuzzyCompleter(comp)

    async def initialize(self) -> None:
        """Set up the prompt session and completer."""
        self._session = PromptSession(
            history=FileHistory(".cli_history"),
        )
        self._update_completer()

    async def run(self) -> None:
        """Start the main CLI event loop."""
        if self._session is None:
            await self.initialize()

        t = self.theme
        prompt = ANSI(f"{t.ansi('primary')}> {RS}")

        print(f"{t.style_box('primary', 'MCP Chat')}{RS}")

        while True:
            try:
                assert self._session is not None
                if self._prompt_timeout > 0:
                    user_input = await asyncio.wait_for(
                        self._session.prompt_async(prompt),
                        timeout=self._prompt_timeout,
                    )
                else:
                    user_input = await self._session.prompt_async(prompt)
            except TimeoutError:
                print(f"{t.ansi('muted')}[timeout] No input received within timeout period.{RS}")
                continue
            except (EOFError, KeyboardInterrupt):
                print(f"\n{t.ansi('success')}Bye!{RS}")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.startswith("/"):
                cont, reply = await route_command(user_input, self.chat, self)
                if not cont:
                    break
                if reply:
                    print(reply)
            else:
                try:
                    print(self._msg.user_header())
                    print(f"  {self._msg._renderer.palette_dict['fg']}{user_input}{RS}")
                    print(f"  {self._msg.user_separator(len(user_input))}")
                    print()

                    buf: list[str] = []
                    self._spinner.start("thinking")
                    header = self._msg.assistant_header()
                    started = False

                    def on_chunk(c: str) -> None:
                        nonlocal started
                        if not started:
                            started = True
                            self._spinner.clear()
                            print(f"{header}\n  ", end="", flush=True)
                        buf.append(c)

                        # Use the CodeBlockAccumulator to handle streaming code
                        # and the renderer for inline formatting.
                        # Since we are streaming, we feed it to the accumulator.
                        self._codeblocks.feed(c, on_text=lambda t: print(self._msg._renderer.render_inline(t), end="", flush=True))

                    usage_before = self.chat.usage.session_summary()
                    reply = await self.chat.send(user_input, on_chunk=on_chunk)
                    self._spinner.stop()

                    # Finalize any unclosed code blocks
                    self._codeblocks.flush(on_text=lambda t: print(self._msg._renderer.render_inline(t), end="", flush=True))

                    printed = "".join(buf)
                    final = reply or printed
                    if final:
                        print()
                        print(f"{self._msg.assistant_separator()}")
                        usage_after = self.chat.usage.session_summary()
                        in_turn = usage_after['input_tokens'] - usage_before['input_tokens']
                        out_turn = usage_after['output_tokens'] - usage_before['output_tokens']
                        cost_turn = usage_after['cost'] - usage_before['cost']
                        print(
                            f"{t.ansi('muted')}  {in_turn + out_turn:,} tokens "
                            f"({in_turn} in / {out_turn} out) ${cost_turn:.4f}{RS}"
                        )
                        print()

                except Exception as exc:
                    self._spinner.stop()
                    print(f"{t.ansi('error')}[error]{RS} {exc}")

    def _print_usage(self) -> None:
        t = self.theme
        session = self.chat.usage.session_summary()
        total = self.chat.usage.total_summary()
        print(f"{t.ansi('secondary')}--- Session Usage ---{RS}")
        print(f"  Input tokens:  {session['input_tokens']:,}")
        print(f"  Output tokens: {session['output_tokens']:,}")
        print(f"  Total tokens:  {session['total_tokens']:,}")
        print(f"  Cost:          ${session['cost']:.6f}")
        print(f"{t.ansi('secondary')}--- All Time ---{RS}")
        print(f"  Input tokens:  {total['input_tokens']:,}")
        print(f"  Output tokens: {total['output_tokens']:,}")
        print(f"  Total tokens:  {total['total_tokens']:,}")
        print(f"  Cost:          ${total['cost']:.6f}")

    def _format_timestamp(self, ts: str) -> str:
        if not self._timestamps_enabled or not ts:
            return ""
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(ts)
            return dt.strftime(" [%H:%M:%S]")
        except Exception:
            return ""

    async def _handle_history(self, session_id: str) -> None:
        t = self.theme
        sid = session_id.strip() or self.chat.session_id
        msgs = await self.chat.history.async_load_session(sid)
        if not msgs:
            print(f"{t.ansi('muted')}No messages in session '{sid}'.{RS}")
            return
        print(f"{t.ansi('secondary')}--- History: {sid} ({len(msgs)} messages) ---{RS}")
        for m in msgs[-20:]:
            preview = m["content"][:120].replace("\n", " ")
            ts = self._format_timestamp(m.get("timestamp", ""))
            print(f"  {t.ansi('primary') if m['role'] == 'assistant' else t.ansi('muted')}{m['role']}:{RS}{ts} {preview}")

    async def _handle_list_sessions(self) -> None:
        t = self.theme
        sessions = await self.chat.history.async_list_sessions()
        if not sessions:
            print(f"{t.ansi('muted')}No saved sessions.{RS}")
            return
        print(f"{t.ansi('secondary')}Sessions:{RS}")
        for s in sessions:
            marker = " *" if s == self.chat.session_id else ""
            print(f"  {t.ansi('primary')}{s}{RS}{marker}")

    async def _handle_switch_session(self, session_id: str) -> None:
        t = self.theme
        sid = session_id.strip()
        if not sid:
            print(f"{t.ansi('error')}Usage: /session <session_id>{RS}")
            return
        self.chat.session_id = sid
        self.chat.messages = await self.chat.history.async_load_session(sid)
        print(f"{t.ansi('success')}Switched to session '{sid}' ({len(self.chat.messages)} messages).{RS}")

    def _print_status(self) -> None:
        t = self.theme
        s = self.chat.get_status()
        print(f"{t.style_box('secondary', 'System Status')}{RS}")
        print(f"  {t.icon('session')} {t.ansi('primary')}Session:{RS}   {s['session']}{RS}")
        print(f"  {t.icon('message')} {t.ansi('primary')}Messages:{RS}  {s['messages']}{RS}")
        print(f"  {t.icon('network')} {t.ansi('primary')}Provider:{RS}  {s['provider']}{RS}")
        print(f"  {t.icon('model')} {t.ansi('primary')}Model:{RS}     {s['model']}{RS}")
        print(f"  {t.icon('tool')} {t.ansi('primary')}Tools:{RS}     {s['tools']}{RS}")
        print(f"  {t.icon('server')} {t.ansi('primary')}Servers:{RS}   {', '.join(s['servers']) if s['servers'] else 'none'}{RS}")

    async def _handle_search(self, query: str) -> None:
        t = self.theme
        # Use the HistoryManager via the chat service for a global search
        results = self.chat.history.search(query)

        if not results:
            print(f"{t.ansi('muted')}No matches found for '{query}'.{RS}")
            return

        print(f"{t.ansi('secondary')}--- Search: '{query}' ({len(results)} results) ---{RS}")
        for r in results:
            role = r.get("role", "unknown")
            content = r.get("content", "")
            preview = content[:120].replace("\n", " ")
            ts = self._format_timestamp(r.get("timestamp", ""))

            color = t.ansi('primary') if role == 'assistant' else t.ansi('muted')
            print(f"  {color}{role}:{RS}{ts} {preview}")

    def _print_help(self) -> None:
        t = self.theme
        loc = self._locale
        def _(eng: str) -> str:
            return loc.translate_cmd(eng)
        def cmd(c: str, desc: str) -> str:
            return f"  {t.ansi('muted')}/{c:<22}{RS} {t.ansi('secondary')}{desc}{RS}"
        bar = f"{t.ansi('muted')}\u2501{RS}" * 78
        print(bar)
        for section_name, entries in HELP_SECTIONS:
            print(f"  {t.ansi('primary')}{section_name}{RS}")
            for cmd_fn, desc in entries:
                print(cmd(cmd_fn(_), desc))
        print(bar)
