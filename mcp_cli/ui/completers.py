from __future__ import annotations

import re
from typing import Any

from prompt_toolkit.completion import Completer, Completion

from mcp_cli.locales import get as get_locale

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
        from mcp_cli.commands.router import _PROVIDER_CONFIG
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

    def _doc_completions(self, partial: str):
        lower = partial.lower()
        for doc_id in getattr(self.chat, "doc_ids", []):
            if lower in doc_id.lower():
                yield Completion(
                    doc_id,
                    start_position=-len(partial),
                    display=f"@{doc_id}",
                    display_meta="document",
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
            elif eng_cmd == "session":
                yield from self._session_id_completions(rest)
            elif eng_cmd == "history":
                yield from self._session_id_completions(rest)
            elif eng_cmd == "fork":
                yield from self._session_id_completions(rest)
            elif eng_cmd == "model":
                yield from self._model_completions(rest)
            elif eng_cmd == "provider":
                yield from self._provider_completions(rest)
            elif eng_cmd == "theme":
                yield from self._theme_completions(rest)
            elif eng_cmd == "unload":
                yield from self._server_id_completions(rest)
            elif eng_cmd == "reload":
                yield from self._server_id_completions(rest)
            elif eng_cmd == "rename":
                yield Completion("", display="<new_name>", display_meta="new session name")
            elif eng_cmd == "key":
                yield from self._subcommand_completions(eng_cmd, rest)
            elif eng_cmd == "agent":
                yield from self._subcommand_completions(eng_cmd, rest)
            elif eng_cmd in ("lang", "language"):
                yield Completion("", display="<lang>", display_meta="en / english")
            elif eng_cmd == "search":
                yield Completion("", display="<query>", display_meta="search term")
            elif eng_cmd == "semsearch":
                yield Completion("", display="<query>", display_meta="semantic search term")
            elif eng_cmd == "ls":
                yield Completion("", display="<path>", display_meta="directory path (default: .)")
            elif eng_cmd == "roots":
                yield Completion("", display="", display_meta="list approved root directories")
            elif eng_cmd == "load":
                yield Completion("", display="<script>", display_meta="e.g. @modelcontextprotocol/server-*")
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
        lower = partial.lower()
        for sid in sessions:
            if lower in sid.lower():
                marker = " *" if sid == self.chat.session_id else ""
                yield Completion(
                    sid,
                    start_position=-len(partial),
                    display=sid,
                    display_meta=f"session{marker}",
                )

    def _model_completions(self, partial: str):
        cached = getattr(self, "_cached_models", [])
        lower = partial.lower()
        for model in cached:
            if lower in model.lower():
                yield Completion(
                    model,
                    start_position=-len(partial),
                    display=model,
                    display_meta="model",
                )
        if not cached:
            yield Completion("", display="<model_name>", display_meta="type /models to list")

    def _provider_completions(self, partial: str):
        lower = partial.lower()
        for name in self._providers:
            if lower in name.lower():
                yield Completion(
                    name,
                    start_position=-len(partial),
                    display=name,
                    display_meta=self._providers_meta.get(name, ""),
                )

    def _theme_completions(self, partial: str):
        lower = partial.lower()
        for name in self._themes:
            if lower in name.lower():
                marker = " *" if name == self.app._theme.name else ""
                yield Completion(
                    name,
                    start_position=-len(partial),
                    display=name,
                    display_meta=f"theme{marker}",
                )

    def _server_id_completions(self, partial: str):
        lower = partial.lower()
        for sid in self.chat.clients:
            if lower in sid.lower():
                yield Completion(
                    sid,
                    start_position=-len(partial),
                    display=sid,
                    display_meta="MCP server",
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
