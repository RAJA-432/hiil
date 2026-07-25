from mcp_cli.ui.themes import RS, DEEP_BLACK, DEEP_CURSOR, THEMES, Theme, get_theme

OPENCODE = DEEP_BLACK
CURSOR = DEEP_CURSOR


def test_theme_init():
    t = Theme("test", {"primary": "#ff0000", "muted": "#888888"})
    assert t.name == "test"
    assert t.colors["primary"] == "#ff0000"


def test_theme_ansi_returns_escape_code():
    t = Theme("test", {"primary": "#ff0000", "muted": "#888888"})
    result = t.ansi("primary")
    assert result.startswith("\033[")
    assert "38;2;255;0;0" in result
    assert result.endswith("m")


def test_theme_ansi_fallback_to_muted():
    t = Theme("test", {"primary": "#ff0000", "muted": "#888888"})
    result = t.ansi("nonexistent")
    assert "136;136;136" in result


def test_theme_reset_property():
    assert RS == "\033[0m"


def test_opencode_theme():
    assert OPENCODE.name == "opencode"
    assert OPENCODE.colors["primary"] == "#005f5f"
    assert OPENCODE.colors["secondary"] == "#3a0a3a"
    assert OPENCODE.colors["success"] == "#003a00"
    assert OPENCODE.colors["error"] == "#3a0000"
    assert OPENCODE.colors["muted"] == "#1a1a1a"


def test_cursor_theme():
    assert CURSOR.name == "cursor"
    assert CURSOR.colors["primary"] == "#004a45"
    assert CURSOR.colors["muted"] == "#151515"


def test_get_theme_default():
    t = get_theme(None)
    assert t.name == "opencode"


def test_get_theme_by_name():
    t = get_theme("cursor")
    assert t.name == "cursor"
    assert isinstance(t, Theme)


def test_get_theme_by_name_cursor():
    t = get_theme("cursor")
    assert t.name == "cursor"


def test_get_theme_invalid_falls_back():
    t = get_theme("nonexistent_theme")
    assert t.name == "opencode"


def test_get_theme_case_sensitive():
    t = get_theme("OPENCODE")
    assert t.name == "opencode"


def test_get_theme_empty_string():
    t = get_theme("")
    assert t.name == "opencode"


def test_get_theme_with_env_var(monkeypatch):
    monkeypatch.setenv("CLI_THEME", "cursor")
    t = get_theme(None)
    assert t.name == "cursor"


def test_get_theme_env_var_invalid(monkeypatch):
    monkeypatch.setenv("CLI_THEME", "bad_theme")
    t = get_theme(None)
    assert t.name == "opencode"


def test_get_theme_env_var_overridden_by_arg(monkeypatch):
    monkeypatch.setenv("CLI_THEME", "opencode")
    t = get_theme("cursor")
    assert t.name == "cursor"


def test_themes_dict():
    assert "opencode" in THEMES
    assert "cursor" in THEMES
    assert len(THEMES) == 2


def test_themes_dict_values():
    for name, theme in THEMES.items():
        assert isinstance(theme, Theme)
        assert theme.name == name


def test_theme_ansi_all_colors():
    t = OPENCODE
    for key in ["primary", "secondary", "accent", "success", "error", "muted"]:
        result = t.ansi(key)
        assert result.startswith("\033[")
        assert result.endswith("m")


def test_theme_ansi_parses_hex_correctly():
    t = Theme("test", {"primary": "#aabbcc", "muted": "#888888"})
    result = t.ansi("primary")
    assert "170;187;204" in result


def test_theme_ansi_black():
    t = Theme("test", {"primary": "#000000", "muted": "#888888"})
    result = t.ansi("primary")
    assert "0;0;0" in result


def test_theme_ansi_white():
    t = Theme("test", {"primary": "#ffffff", "muted": "#888888"})
    result = t.ansi("primary")
    assert "255;255;255" in result


def test_theme_ansi_missing_colors_dict():
    """primary is not passed but defaults are filled in __post_init__."""
    t = Theme("minimal", {"muted": "#123456"})
    result = t.ansi("primary")
    assert t.colors.get("primary") == "#00ffff"
    assert "0;255;255" in result


def test_theme_ansi_all_return_unique():
    t = OPENCODE
    results = {key: t.ansi(key) for key in ["primary", "secondary", "success", "error", "muted"]}
    assert len(set(results.values())) == len(results)
