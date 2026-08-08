from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import FuzzyCompleter
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import FileHistory

from mcp_cli.commands.router import route_command
from mcp_cli.locales import get as get_locale
from mcp_cli.services.usage import format_cost
from mcp_cli.ui.codeblock import CodeBlockAccumulator
from mcp_cli.ui.commands.help import print_help
from mcp_cli.ui.commands.history_cmds import (
    handle_history,
    handle_list_sessions,
    handle_switch_session,
)
from mcp_cli.ui.commands.status import print_status
from mcp_cli.ui.completers import HiilCompleter
from mcp_cli.ui.messaging import MessageManager, SpinnerManager
from mcp_cli.ui.renderer import get_renderer
from mcp_cli.ui.streaming import StreamingRenderer
from mcp_cli.ui.theme_manager import ThemeManager
from mcp_cli.ui.themes import RS
from mcp_cli.ui.tool_events import ToolEventHandler
from mcp_cli.ui.turn_renderer import TurnRenderer


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
        self._turn_renderer = TurnRenderer(
            self._msg,
            self._spinner,
            self._codeblocks,
            StreamingRenderer,
            self.theme,
        )

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
                reply = await self._turn_renderer.run(
                    self.chat,
                    user_input,
                    self._request_tool_approval,
                )

    def _render_phases(self, phases: list[dict[str, Any]]) -> list[str]:
        """Convert lifecycle state events into colored display lines."""
        t = self.theme
        lines: list[str] = []
        for event in phases:
            agent_id = event.get("agent_id", "?")
            phase = event.get("phase", "UNKNOWN")
            lines.append(f"{t.ansi('muted')}> {RS}{t.ansi('primary')}[{agent_id}]{RS} {phase}")
        return lines

    def _print_usage(self) -> None:
        t = self.theme
        session = self.chat.usage.session_summary()
        total = self.chat.usage.total_summary()
        print(f"{t.ansi('secondary')}--- Session Usage ---{RS}")
        print(f"  Input tokens:  {session['input_tokens']:,}")
        print(f"  Output tokens: {session['output_tokens']:,}")
        print(f"  Total tokens:  {session['total_tokens']:,}")
        print(f"  Cost:          {format_cost(session['cost'])}")
        print(f"{t.ansi('secondary')}--- All Time ---{RS}")
        print(f"  Input tokens:  {total['input_tokens']:,}")
        print(f"  Output tokens: {total['output_tokens']:,}")
        print(f"  Total tokens:  {total['total_tokens']:,}")
        print(f"  Cost:          {format_cost(total['cost'])}")

    async def _request_tool_approval(self, name: str, args: dict[str, Any]) -> bool:
        t = self.theme
        self._spinner.stop()
        print(
            f"{t.ansi('warning')}[sensitive]{RS} Tool '{t.ansi('primary')}{name}{RS}' "
            f"requests approval (args: {t.ansi('muted')}{json.dumps(args)}{RS})."
        )
        if self._session is None:
            return False
        while True:
            try:
                answer = await self._session.prompt_async(
                    ANSI(f"{t.ansi('warning')}Approve? (y/n) {RS}")
                )
            except (EOFError, KeyboardInterrupt):
                print()
                return False
            choice = answer.strip().lower()
            if choice in ("y", "yes"):
                return True
            if choice in ("n", "no"):
                return False
            print(f"{t.ansi('muted')}Please answer y or n.{RS}")

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
        await handle_history(self.chat, session_id, self.theme, self._format_timestamp)

    async def _handle_list_sessions(self) -> None:
        await handle_list_sessions(self.chat, self.theme)

    async def _handle_switch_session(self, session_id: str) -> None:
        await handle_switch_session(self.chat, session_id, self.theme)

    def _print_status(self) -> None:
        print_status(self.chat, self.theme)

    def _print_help(self) -> None:
        print_help(self.theme, self._locale)
