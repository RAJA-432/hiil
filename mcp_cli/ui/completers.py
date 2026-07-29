from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from prompt_toolkit.completion import Completer, Completion

from mcp_cli.locales import get as get_locale

_COMMAND_COMPLETERS: dict[str, Callable] = {
    "session": lambda self, p: self._session_id_completions(p),
    "history": lambda self, p: self._session_id_completions(p),
    "fork": lambda self, p: self._session_id_completions(p),
    "model": lambda self, p: self._model_completions(p),
    "provider": lambda self, p: self._provider_completions(p),
    "theme": lambda self, p: self._theme_completions(p),
    "unload": lambda self, p: self._server_id_completions(p),
    "reload": lambda self, p: self._server_id_completions(p),
    "rename": lambda self, p: iter([Completion("", display="<new_name>", display_meta="new session name")]),
    "lang": lambda self, p: iter([Completion("", display="<lang>", display_meta="en / english")]),
    "language": lambda self, p: iter([Completion("", display="<lang>", display_meta="en / english")]),
    "search": lambda self, p: iter([Completion("", display="<query>", display_meta="search term")]),
    "semsearch": lambda self, p: iter([Completion("", display="<query>", display_meta="semantic search term")]),
    "ls": lambda self, p: iter([Completion("", display="<path>", display_meta="directory path (default: .)")]),
    "roots": lambda self, p: iter([Completion("", display="", display_meta="list approved root directories")]),
    "load": lambda self, p: iter([Completion("", display="<script>", display_meta="e.g. @modelcontextprotocol/server-*")]),
}

_SUBCOMMAND_META: dict[str, dict[str, str]] = {
    "key": {
        "set": "Save an encrypted API key for a provider",
        "delete": "Delete a stored API key",
        "status": "Show whether a key is stored for the current provider",
    },
    "agent": {
        "create": "Create a new background agent with a goal",
        "list": "List running agents",
        "search": "Search agent memory",
        "pause": "Pause a running agent",
        "approve": "Approve a pending agent action",
        "reject": "Reject a pending agent action",
    },
}


def _fuzzy_filter(partial: str, candidates: list[tuple[str, str]]):
    lower = partial.lower()
    results: list[Completion] = []
    for word, meta in candidates:
        if lower in word.lower():
            results.append(
                Completion(
                    word,
                    start_position=-len(partial),
                    display=word.split()[0] if " " in word else word,
                    display_meta=meta,
                )
            )
    results.sort(key=lambda c: (not c.text.lower().startswith(lower), c.text))
    return results


class HiilCompleter(Completer):
    def __init__(self, chat: Any, app: Any):
        self.chat = chat
        self.app = app
        self._themes: list[str] = []
        self._providers: list[str] = []
        self._providers_meta: dict[str, str] = {}

    def set_metadata(self) -> None:
        """Cache theme names, provider list, and provider metadata."""
        from mcp_cli.commands.provider_config import _PROVIDER_CONFIG
        from mcp_cli.ui.themes import THEMES
        self._themes = list(THEMES.keys())
        self._providers = list(_PROVIDER_CONFIG.keys())
        self._providers_meta = {
            name: f"default: {cfg['default_model']}"
            for name, cfg in _PROVIDER_CONFIG.items()
        }

    def get_completions(self, document, complete_event):
        """Yield tab-completions for @docs, /commands, and tool arguments."""
        text = document.text_before_cursor

        if m := re.search(r"(?:^|\s)@([^\s]*)$", text):
            yield from self._doc_completions(m.group(1))
            return

        if text.startswith("/"):
            yield from self._command_completions(text)
            return

    def _completions(self, candidates, partial, display_func=None, meta_func=None):
        lower = partial.lower()
        for c in candidates:
            if lower in c.lower():
                yield Completion(
                    c,
                    start_position=-len(partial),
                    display=display_func(c) if display_func else c,
                    display_meta=meta_func(c) if meta_func else "",
                )

    def _doc_completions(self, partial: str):
        yield from self._completions(
            getattr(self.chat, "doc_ids", []), partial,
            display_func=lambda d: f"@{d}",
            meta_func=lambda d: "document",
        )

    def _command_completions(self, text: str):
        loc = get_locale()
        after_slash = text[1:]
        space_idx = after_slash.find(" ")
        cmd = after_slash[:space_idx].lower() if space_idx >= 0 else after_slash.lower()
        rest = after_slash[space_idx + 1:] if space_idx >= 0 else ""

        eng_cmd = loc.resolve_cmd(cmd) or cmd

        if space_idx >= 0 and eng_cmd:
            if eng_cmd in _SUBCOMMAND_META:
                yield from self._subcommand_completions(eng_cmd, rest)
            else:
                completer = _COMMAND_COMPLETERS.get(eng_cmd)
                if completer:
                    yield from completer(self, rest)
                else:
                    yield from self._tool_arg_completions(eng_cmd, rest)
            return

        partial = cmd or after_slash
        yield from self._command_list_completions(partial)

    def _command_list_completions(self, partial: str):
        loc = get_locale()
        lower = partial.lower()
        candidates: list[tuple[str, str]] = []
        for eng, meta in loc.meta.items():
            localised = loc.translate_cmd(eng)
            candidates.append((f"/{localised}", meta))
        yield from _fuzzy_filter(partial, candidates)

        for tool_name in self.chat.tools_by_name:
            desc = self.chat.tools_by_name[tool_name]["openai"]["function"].get("description", "")
            if lower in tool_name.lower() or not partial:
                yield Completion(
                    f"/{tool_name}",
                    start_position=-len(partial) - 1,
                    display=f"/{tool_name}",
                    display_meta=desc or "MCP tool",
                )

    def _subcommand_completions(self, cmd: str, partial: str):
        sub_map = _SUBCOMMAND_META.get(cmd, {})
        candidates = [(k, v) for k, v in sub_map.items()]
        for w, meta_text in candidates:
            if partial.lower() in w.lower():
                yield Completion(
                    w,
                    start_position=-len(partial),
                    display=w,
                    display_meta=meta_text,
                )

    def _session_id_completions(self, partial: str):
        try:
            sessions = self.chat.history.list_sessions()
        except Exception:
            sessions = []
        yield from self._completions(
            sessions, partial,
            display_func=lambda s: s,
            meta_func=lambda s: f"session{' *' if s == self.chat.session_id else ''}",
        )

    def _model_completions(self, partial: str):
        cached = getattr(self, "_cached_models", [])
        yield from self._completions(
            cached, partial,
            display_func=lambda m: m,
            meta_func=lambda m: "model",
        )
        if not cached:
            yield Completion("", display="<model_name>", display_meta="type /models to list")

    def _provider_completions(self, partial: str):
        yield from self._completions(
            self._providers, partial,
            display_func=lambda n: n,
            meta_func=lambda n: self._providers_meta.get(n, ""),
        )

    def _theme_completions(self, partial: str):
        yield from self._completions(
            self._themes, partial,
            display_func=lambda n: n,
            meta_func=lambda n: f"theme{' *' if n == self.app._theme.name else ''}",
        )

    def _server_id_completions(self, partial: str):
        yield from self._completions(
            self.chat.clients, partial,
            display_func=lambda s: s,
            meta_func=lambda s: "MCP server",
        )

    def _tool_arg_completions(self, tool_name: str, partial: str):
        loc = get_locale()
        entry = self.chat.tools_by_name.get(tool_name)
        if entry is None:
            for eng_name in self.chat.tools_by_name:
                if loc.translate_tool(eng_name) == tool_name:
                    entry = self.chat.tools_by_name[eng_name]
                    break
        if entry is None:
            return
        func = entry["openai"]["function"]
        params = func.get("parameters", {}).get("properties", {})
        if not partial:
            for pname in params:
                yield Completion("", display=f"<{pname}>", display_meta="parameter")
            return
        for pname in params:
            ptype = params[pname].get("type", "str")
            pdesc = params[pname].get("description", "")
            meta_text = f"{ptype}" + (f": {pdesc}" if pdesc else "")
            if partial.lower() in pname.lower():
                yield Completion(
                    pname,
                    start_position=-len(partial),
                    display=pname,
                    display_meta=meta_text,
                )

    async def cache_models(self) -> None:
        """Fetch and cache the available model list from the provider."""
        try:
            models = await self.chat.claude.list_models()
            self._cached_models = [m["id"] for m in models[:50]]
        except Exception:
            self._cached_models = []
