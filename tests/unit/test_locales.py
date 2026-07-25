from mcp_cli.locales import available, available_labels, get, set_lang


def test_default_locale_is_english():
    set_lang("en")
    loc = get()
    assert loc.lang == "en"


def test_available_locales():
    langs = available()
    assert "en" in langs


def test_available_labels():
    labels = available_labels()
    assert "English" in labels


def test_resolve_cmd_english():
    set_lang("en")
    loc = get()
    assert loc.resolve_cmd("help") == "help"
    assert loc.resolve_cmd("exit") == "exit"


def test_resolve_cmd_unknown():
    set_lang("en")
    loc = get()
    assert loc.resolve_cmd("nonexistent") is None


def test_english_identity():
    set_lang("en")
    loc = get()
    for eng in ["help", "tools", "status", "exit", "model", "search", "theme"]:
        assert loc.translate_cmd(eng) == eng


def test_unknown_lang_fallback():
    set_lang("en")
    loc = get()
    assert loc.lang == "en"


def test_meta_contains_english_descriptions():
    set_lang("en")
    loc = get()
    assert "help" in loc.meta
    assert "Show this help message" in loc.meta["help"]


def test_translate_tool_identity_in_english():
    set_lang("en")
    loc = get()
    assert loc.translate_tool("search_resources") == "search_resources"
