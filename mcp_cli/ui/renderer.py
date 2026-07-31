from __future__ import annotations

import re

RS = "\033[0m"

# ── ANSI constants ──────────────────────────────────────────────────────
BOLD_ON = "\033[1m"
BOLD_OFF = "\033[22m"
DIM_ON = "\033[2m"
DIM_OFF = "\033[22m"
ITALIC_ON = "\033[3m"
ITALIC_OFF = "\033[23m"
UNDERLINE_ON = "\033[4m"
UNDERLINE_OFF = "\033[24m"

# ── Palettes ────────────────────────────────────────────────────────────

DARK_PALETTE: dict[str, str] = {
    "bg":            "\033[48;2;18;18;18m",
    "bg_code_block": "\033[48;2;25;25;25m",
    "bg_inline":     "\033[48;2;35;35;35m",
    "fg":            "\033[38;2;220;220;220m",
    "fg_muted":      "\033[38;2;128;128;128m",
    "fg_primary":    "\033[38;2;0;200;255m",
    "fg_secondary":  "\033[38;2;255;100;200m",
    "fg_code":       "\033[38;2;255;184;108m",
    "fg_link":       "\033[38;2;80;180;255m",
    "fg_success":    "\033[38;2;80;255;120m",
    "fg_error":      "\033[38;2;255;80;80m",
    "fg_warning":    "\033[38;2;255;200;50m",
    "border":        "\033[38;2;80;80;80m",
}

LIGHT_PALETTE: dict[str, str] = {
    "bg":            "\033[48;2;250;250;250m",
    "bg_code_block": "\033[48;2;240;240;240m",
    "bg_inline":     "\033[48;2;230;230;230m",
    "fg":            "\033[38;2;30;30;30m",
    "fg_muted":      "\033[38;2;140;140;140m",
    "fg_primary":    "\033[38;2;0;120;200m",
    "fg_secondary":  "\033[38;2;200;0;150m",
    "fg_code":       "\033[38;2;180;100;0m",
    "fg_link":       "\033[38;2;0;80;200m",
    "fg_success":    "\033[38;2;0;160;50m",
    "fg_error":      "\033[38;2;200;30;30m",
    "fg_warning":    "\033[38;2;180;130;0m",
    "border":        "\033[38;2;180;180;180m",
}

_ANSI_CLOSE: dict[str, str] = {
    "bg":            RS,
    "bg_code_block": RS,
    "bg_inline":     RS,
    "fg":            RS,
    "fg_muted":      RS,
    "fg_primary":    RS,
    "fg_secondary":  RS,
    "fg_code":       RS,
    "fg_link":       RS,
    "fg_success":    RS,
    "fg_error":      RS,
    "fg_warning":    RS,
    "border":        RS,
}

# ── Regexes ─────────────────────────────────────────────────────────────

_RE_FENCED = re.compile(
    r"```(\w*)\n(.*?)```", re.DOTALL
)
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_RE_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


class MarkdownRenderer:
    """Renders Markdown text to ANSI-escaped terminal output.

    Supports bold, italic, inline code, fenced code blocks, links,
    images (as text fallback), nested formatting, and theme switching
    between dark and light palettes.
    """

    def __init__(self, theme: str = "dark"):
        self._theme_name = theme
        self._palette = dict(DARK_PALETTE if theme == "dark" else LIGHT_PALETTE)

    @property
    def theme(self) -> str:
        return self._theme_name

    def set_theme(self, name: str) -> None:
        if name == self._theme_name:
            return
        self._theme_name = name
        self._palette = dict(DARK_PALETTE if name == "dark" else LIGHT_PALETTE)

    @property
    def palette_dict(self) -> dict[str, str]:
        return self._palette

    def palette(self, key: str) -> str:
        return self._palette.get(key, "")

    # ── Public API ─────────────────────────────────────────────────────

    def render(self, text: str) -> str:
        """Full render for complete messages."""
        text = self._render_fenced_blocks(text)
        text = self.render_inline(text)
        return text

    def render_inline(self, text: str) -> str:
        """Light render for streaming chunks (no code blocks)."""
        text = _RE_INLINE_CODE.sub(self._replace_inline_code, text)
        text = _RE_LINK.sub(self._replace_link, text)
        text = _RE_BOLD.sub(self._replace_bold, text)
        text = _RE_ITALIC.sub(self._replace_italic, text)
        text = _RE_IMG.sub(self._replace_image, text)
        # Strip unmatched asterisks (partial ** or * across chunk boundaries)
        text = text.replace("**", "").replace("*", "")
        return text

    # ── Fenced code blocks ─────────────────────────────────────────────

    def _render_fenced_blocks(self, text: str) -> str:
        def _replace(m: re.Match) -> str:
            lang = m.group(1) or "text"
            code = m.group(2)
            rendered = self._render_code_block(code, lang)
            return rendered
        return _RE_FENCED.sub(_replace, text)

    def _render_code_block(self, code: str, lang: str) -> str:
        p = self._palette
        lines = code.rstrip("\n").split("\n")
        width = max((len(line) for line in lines), default=0)
        width = min(width + 4, 80)

        sep = p["border"] + "─" * width + RS
        badge = f" {p['fg_muted']}[{lang}]{RS} " if lang else ""

        header = f"{sep}\n{badge}"

        body_lines = []
        for line in lines:
            content = line if line else " "
            # Fill the remaining width with background color
            padding = " " * (width - len(content))
            body_lines.append(f"{p['bg_code_block']}{p['fg_code']}│ {content}{padding}{RS}")

        body = "\n".join(body_lines)
        footer = f"\n{sep}"

        return f"\n{header}\n{body}{footer}\n"

    # ── Inline replacements ────────────────────────────────────────────

    def _replace_inline_code(self, m: re.Match) -> str:
        p = self._palette
        return f"{p['bg_inline']}{p['fg_code']}{m.group(1)}{RS}"

    def _replace_link(self, m: re.Match) -> str:
        p = self._palette
        text = m.group(1)
        return f"{UNDERLINE_ON}{p['fg_link']}{text}{RS}{UNDERLINE_OFF}"

    def _replace_bold(self, m: re.Match) -> str:
        inner = m.group(1)
        # Handle nested italic inside bold
        inner = _RE_ITALIC.sub(self._replace_italic, inner)
        return f"{BOLD_ON}{inner}{BOLD_OFF}"

    def _replace_italic(self, m: re.Match) -> str:
        inner = m.group(1)
        # Handle nested bold inside italic
        inner = _RE_BOLD.sub(self._replace_bold, inner)
        return f"{ITALIC_ON}{DIM_ON}{inner}{DIM_OFF}{ITALIC_OFF}"

    def _replace_image(self, m: re.Match) -> str:
        alt = m.group(1)
        url = m.group(2)
        p = self._palette
        return f"{p['fg_muted']}[image: {alt}]({url}){RS}"


# ── Singleton / helper ──────────────────────────────────────────────────

_RENDERER_INSTANCE: MarkdownRenderer | None = None


def get_renderer(theme: str = "dark") -> MarkdownRenderer:
    global _RENDERER_INSTANCE
    if _RENDERER_INSTANCE is None:
        _RENDERER_INSTANCE = MarkdownRenderer(theme)
    return _RENDERER_INSTANCE
