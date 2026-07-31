from __future__ import annotations

import json
from pathlib import Path


class Locale:
    def __init__(self, lang: str, label: str, commands: dict[str, str],
                 tools: dict[str, str], meta: dict[str, str]):
        self.lang = lang
        self.label = label
        self.commands = commands
        self.tools = tools
        self.meta = meta
        self._reverse_commands: dict[str, str] = {v: k for k, v in commands.items()}
        self._reverse_tools: dict[str, str] = {v: k for k, v in tools.items()}

    def translate_cmd(self, eng: str) -> str:
        return self.commands.get(eng, eng)

    def translate_tool(self, eng: str) -> str:
        return self.tools.get(eng, eng)

    def resolve_cmd(self, candidate: str) -> str | None:
        if candidate in self.commands.values():
            return self._reverse_commands.get(candidate)
        if candidate in self.commands:
            return candidate
        return None


_locales: dict[str, Locale] = {}
_current: Locale | None = None


def register(locale: Locale) -> None:
    _locales[locale.lang] = locale


def set_lang(lang: str) -> str | None:
    global _current
    loc = _locales.get(lang)
    if loc is None:
        return None
    _current = loc
    save_lang_pref(lang)
    return loc.label


def get() -> Locale:
    global _current
    if _current is None:
        found = _locales.get("en") or next(iter(_locales.values()), None)
        assert found is not None
        _current = found
    return _current


def available() -> list[str]:
    return list(_locales.keys())


def available_labels() -> list[str]:
    return [loc.label for loc in _locales.values()]


from mcp_cli.locales.en import ENGLISH  # noqa: E402

register(ENGLISH)


def _load_saved_lang() -> str:
    p = Path.home() / ".hiil" / "prefs.json"
    if p.exists():
        try:
            data = json.loads(p.read_text("utf-8"))
            return data.get("lang", "en")
        except Exception:
            pass
    return "en"


def save_lang_pref(lang: str) -> None:
    p = Path.home() / ".hiil" / "prefs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {"lang": lang}
    if p.exists():
        try:
            existing = json.loads(p.read_text("utf-8"))
            data.update(existing)
        except Exception:
            pass
    data["lang"] = lang
    p.write_text(json.dumps(data, indent=2), "utf-8")


set_lang(_load_saved_lang())
