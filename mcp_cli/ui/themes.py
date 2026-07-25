from __future__ import annotations

import os
from dataclasses import dataclass, field

RS = "\033[0m"  # ANSI reset sequence


@dataclass
class Theme:
    """
    Enhanced theme system that supports both legacy ANSI codes and Rich styling.
    Provides color utilities, styled boxes, icons, and gradient helpers.
    """

    name: str
    colors: dict[str, str] = field(default_factory=dict)
    # Optional: map semantic names to emoji/icons for visual cues
    icons: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        # Ensure essential color keys exist with sensible fallbacks
        defaults = {
            "primary": "#00ffff",
            "secondary": "#ff00ff",
            "success": "#00ff00",
            "error": "#ff0000",
            "warning": "#ffff00",
            "info": "#00ffff",
            "muted": "#888888",
            "background": "#000000",
            "foreground": "#ffffff",
        }
        for key, default in defaults.items():
            self.colors.setdefault(key, default)

        # Default icon set
        default_icons = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "debug": "🐛",
            "star": "⭐",
            "check": "✓",
            "cross": "✗",
            "arrow": "→",
            "bullet": "•",
        }
        self.icons.update({k: v for k, v in default_icons.items() if k not in self.icons})

    # --------------------------------------------------------------------- #
    # ANSI / Legacy support (keeps backward compatibility with existing code)
    # --------------------------------------------------------------------- #
    def ansi(self, key: str) -> str:
        """Return the ANSI escape sequence for a named color key."""
        hex_color = self.colors.get(key, self.colors["muted"])
        # Convert hex to RGB (assuming format "#RRGGBB")
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join([c * 2 for c in hex_color])  # shorthand
        try:
            r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            r, g, b = 128, 128, 128  # fallback to grey
        return f"\033[38;2;{r};{g};{b}m"

    def ansi_bg(self, key: str) -> str:
        """ANSI background color."""
        hex_color = self.colors.get(key, self.colors["background"])
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join([c * 2 for c in hex_color])
        try:
            r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            r, g, b = 0, 0, 0
        return f"\033[48;2;{r};{g};{b}m"

    # --------------------------------------------------------------------- #
    # Rich integration (modern terminal styling)
    # --------------------------------------------------------------------- #
    def rich_color(self, key: str) -> str:
        """Return a Rich-compatible color string (hex or rgb)."""
        hex_color = self.colors.get(key, self.colors["muted"])
        # Rich accepts "#RRGGBB" or "rgb(r,g,b)"
        return hex_color if hex_color.startswith("#") else f"rgb({hex_color})"

    def rich_style(
        self,
        key: str,
        *,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        bg_key: str | None = None,
    ) -> str:
        """
        Return a Rich style string.
        Example: "bold #ff0000 on #000000 italic"
        """
        parts = []
        if bold:
            parts.append("bold")
        if italic:
            parts.append("italic")
        if underline:
            parts.append("underline")

        fg = self.rich_color(key)
        parts.append(f"{fg}")

        if bg_key:
            bg = self.rich_color(bg_key)
            parts.append(f"on {bg}")

        return " ".join(parts)

    # --------------------------------------------------------------------- #
    # UI helper methods
    # --------------------------------------------------------------------- #
    def icon(self, name: str) -> str:
        """Get an emoji/icon for a semantic name."""
        return self.icons.get(name, "")

    def style_box(self, key: str, text: str, padding: int = 1) -> str:
        """
        Return a string formatted as a colored box using ANSI escapes.
        Example: "[ SUCCESS ]" with colors.
        """
        icon = self.icon(key)
        label = f"{icon} {text}".strip()
        colored = f"{self.ansi(key)}{label}{RS}"
        # Simple padding
        padded = " " * padding + colored + " " * padding
        # Add background for contrast if desired
        bg = self.ansi_bg("background")
        return f"{bg}{padded}{RS}"

    def gradient_text(self, text: str, start_key: str, end_key: str, steps: int | None = None) -> str:
        """
        Return a string with ANSI gradient applied across the text.
        Simple linear interpolation between two colors.
        """
        if steps is None:
            steps = len(text)

        start_hex = self.colors.get(start_key, self.colors["primary"]).lstrip("#")
        end_hex = self.colors.get(end_key, self.colors["secondary"]).lstrip("#")

        def hex_to_rgb(h: str) -> tuple[int, int, int]:
            h = h.lstrip("#")
            if len(h) == 3:
                h = "".join([c * 2 for c in h])
            return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4)) # type: ignore[return-value]

        s_r, s_g, s_b = hex_to_rgb(start_hex)
        e_r, e_g, e_b = hex_to_rgb(end_hex)

        out = []
        for i, ch in enumerate(text):
            if steps == 1:
                r, g, b = s_r, s_g, s_b
            else:
                ratio = i / (steps - 1)
                r = int(s_r + (e_r - s_r) * ratio)
                g = int(s_g + (e_g - s_g) * ratio)
                b = int(s_b + (e_b - s_b) * ratio)
            out.append(f"\033[38;2;{r};{g};{b}m{ch}{RS}")
        return "".join(out)


# ------------------------------------------------------------------------- #
# Built-in themes (extend as needed)
# ------------------------------------------------------------------------- #

# Base color palette (can be overridden per theme)
BASE_COLORS = {
    "primary": "#00ffff",  # cyan
    "secondary": "#ff00ff",  # magenta
    "success": "#00ff00",  # green
    "error": "#ff0000",  # red
    "warning": "#ffff00",  # yellow
    "info": "#00ffff",  # cyan
    "muted": "#888888",  # grey
    "background": "#000000",  # black
    "foreground": "#ffffff",  # white
}

# Deep-black theme (all colors are deep/dark)
DEEP_BLACK = Theme(
    name="opencode",
    colors={
        **BASE_COLORS,
        "primary": "#005f5f",
        "secondary": "#3a0a3a",
        "success": "#003a00",
        "error": "#3a0000",
        "warning": "#3a3a00",
        "info": "#003a3a",
        "muted": "#1a1a1a",
        "background": "#000000",
        "foreground": "#222222",
    },
)

# Deep cursor variant
DEEP_CURSOR = Theme(
    name="cursor",
    colors={
        **BASE_COLORS,
        "primary": "#004a45",
        "secondary": "#3a0030",
        "success": "#003a1a",
        "error": "#3a0005",
        "warning": "#3a3000",
        "info": "#003545",
        "muted": "#151515",
        "background": "#000000",
        "foreground": "#1a1a1a",
    },
)


# Mapping of theme names to Theme objects for easy lookup
THEMES = {
    "opencode": DEEP_BLACK,
    "cursor": DEEP_CURSOR,
}


def get_theme(name: str | None = None) -> Theme:
    """
    Retrieve a theme by name, falling back to environment or default.
    """
    if name is None:
        name = os.getenv("CLI_THEME", "opencode")
    return THEMES.get(name.lower(), DEEP_BLACK)


# For backward compatibility with existing code that expects THEMES dict
# and get_theme function (already provided above).

# Alias for common usage in app.py
T = get_theme()  # will be overridden per instance in App class if needed
