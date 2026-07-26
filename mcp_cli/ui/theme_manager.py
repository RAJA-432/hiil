from __future__ import annotations

import os

from mcp_cli.ui.themes import THEMES, Theme

# ── Accessibility presets ────────────────────────────────────────────────

_ACCESSIBILITY_PRESETS = {
    "default": {},
    "high_contrast": {
        "primary": "#00ffff",
        "secondary": "#ff88ff",
        "success": "#00ff44",
        "error": "#ff2222",
        "warning": "#ffdd00",
        "muted": "#cccccc",
        "foreground": "#ffffff",
    },
    "large_text": {},
}

# ── Light-mode overrides ────────────────────────────────────────────────

_LIGHT_OVERRIDES = {
    "primary": "#005f87",
    "secondary": "#87005f",
    "success": "#006600",
    "error": "#cc0000",
    "warning": "#887a00",
    "muted": "#666666",
    "background": "#f5f5f5",
    "foreground": "#1a1a1a",
}


class ThemeManager:
    """Manages theme lifecycle, registration, accessibility, and light/dark.

    Provides a single ``current`` property consumed by the render pipeline::

        mgr = ThemeManager()
        mgr.theme = "cursor"
        mgr.light = True
        mgr.accessibility = "high_contrast"
        theme = mgr.current  # resolved Theme instance
    """

    def __init__(self, theme_name: str | None = None, **overrides: str):
        self._named_themes: dict[str, Theme] = dict(THEMES)
        self._theme_name: str = theme_name or os.getenv("CLI_THEME", "opencode")  # type: ignore[assignment]
        self._base = self._named_themes.get(self._theme_name) or next(
            iter(self._named_themes.values())
        )
        self._light = bool(int(os.getenv("CLI_LIGHT", "0")))
        self._accessibility = os.getenv("CLI_ACCESSIBILITY", "default")
        self._compact = False
        self._overrides: dict[str, str] = dict(overrides)
        self._current: Theme | None = None

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def theme(self) -> str:
        return self._theme_name

    @theme.setter
    def theme(self, name: str) -> None:
        self._theme_name = name
        self._base = self._named_themes.get(name) or self._base
        self._current = None

    @property
    def light(self) -> bool:
        return self._light

    @light.setter
    def light(self, value: bool) -> None:
        self._light = value
        self._current = None

    @property
    def accessibility(self) -> str:
        return self._accessibility

    @accessibility.setter
    def accessibility(self, value: str) -> None:
        if value not in _ACCESSIBILITY_PRESETS:
            value = "default"
        self._accessibility = value
        self._current = None

    @property
    def compact(self) -> bool:
        return self._compact

    @compact.setter
    def compact(self, value: bool) -> None:
        self._compact = value
        self._current = None

    # ── Registration ────────────────────────────────────────────────────

    def register(self, name: str, theme: Theme) -> None:
        self._named_themes[name] = theme
        if name == self._theme_name:
            self._base = theme
            self._current = None

    def unregister(self, name: str) -> bool:
        if name not in self._named_themes:
            return False
        del self._named_themes[name]
        if name == self._theme_name:
            self._theme_name = next(iter(self._named_themes.keys()), "opencode")
            self._base = self._named_themes.get(self._theme_name) or self._base
            self._current = None
        return True

    @property
    def names(self) -> list[str]:
        return list(self._named_themes.keys())

    # ── Resolve current theme ───────────────────────────────────────────

    @property
    def current(self) -> Theme:
        if self._current is not None:
            return self._current
        colors = dict(self._base.colors)

        if self._light:
            colors.update(_LIGHT_OVERRIDES)

        preset = _ACCESSIBILITY_PRESETS.get(self._accessibility if self._accessibility is not None else "default", {})
        if preset:
            colors.update(preset)

        colors.update(self._overrides)

        icons = dict(self._base.icons)
        if self._light:
            icons.pop("success", None)
            icons.pop("error", None)

        self._current = Theme(
            name=f"{self._theme_name}{'_light' if self._light else ''}"
            f"{'_hc' if self._accessibility == 'high_contrast' else ''}",
            colors=colors,
            icons=icons,
        )
        return self._current

    # ── Toggle helpers ──────────────────────────────────────────────────

    def toggle_light(self) -> bool:
        self.light = not self._light
        return self._light

    def toggle_compact(self) -> bool:
        self._compact = not self._compact
        return self._compact

    def cycle_accessibility(self) -> str:
        keys = list(_ACCESSIBILITY_PRESETS.keys())
        idx = keys.index(self._accessibility) if self._accessibility in keys else -1
        self.accessibility = keys[(idx + 1) % len(keys)]
        return self._accessibility
