from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
    WindowAlign,
)
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.styles import Style


async def handle_plan_cmd(chat, app) -> str:
    """Interactive model selection for planning."""
    models = await chat.claude.list_models()
    if not models:
        return "Could not fetch model list from provider."

    selected = await _interactive_model_picker(models)
    if selected is None:
        return "Model selection cancelled."

    chat.claude.update_model(selected)
    chat.refresh_system_prompt()
    return f"Switched to model '{selected}' for planning."


async def interactive_model_picker(models: list[dict]) -> str | None:
    return await _interactive_model_picker(models)


async def _interactive_model_picker(models: list[dict]) -> str | None:
    model_ids = [m["id"] for m in models]
    selected_idx = 0
    search_text = ""
    result: str | None = None

    def _filtered():
        if not search_text:
            return model_ids
        lower = search_text.lower()
        return [m for m in model_ids if lower in m.lower()]

    def _render_list():
        filtered = _filtered()
        lines = []
        for i, m_id in enumerate(filtered):
            marker = "●" if i == selected_idx else "○"
            lines.append(f" {marker} {m_id}")
        return "\n".join(lines) if lines else " (no matches)"

    kb = KeyBindings()

    @kb.add("up")
    def move_up(event):
        nonlocal selected_idx
        filtered = _filtered()
        if filtered:
            selected_idx = (selected_idx - 1) % len(filtered)

    @kb.add("down")
    def move_down(event):
        nonlocal selected_idx
        filtered = _filtered()
        if filtered:
            selected_idx = (selected_idx + 1) % len(filtered)

    @kb.add("enter")
    def confirm(event):
        nonlocal result
        filtered = _filtered()
        if filtered and 0 <= selected_idx < len(filtered):
            result = filtered[selected_idx]
        event.app.exit()

    @kb.add("escape")
    @kb.add("c-c")
    def cancel(event):
        event.app.exit()

    @kb.add("c-f")
    def focus_search(event):
        event.app.layout.focus(search_win)

    search_buffer = Buffer()

    def on_search_changed(buf):
        nonlocal search_text, selected_idx
        search_text = buf.text
        selected_idx = 0

    search_buffer.on_text_changed += on_search_changed

    search_win = Window(
        content=BufferControl(buffer=search_buffer),
        height=1,
        style="class:search",
    )

    list_control = FormattedTextControl(
        text=_render_list,
        focusable=True,
    )

    list_win = Window(
        content=list_control,
        style="class:list",
    )

    status_win = Window(
        content=FormattedTextControl(
            "  \u2302 Search  \u23ce Select  Esc Cancel",
        ),
        height=1,
        style="class:status",
        align=WindowAlign.LEFT,
    )

    title_win = Window(
        content=FormattedTextControl(" Select model"),
        height=1,
        style="bold",
        align=WindowAlign.LEFT,
    )

    root = HSplit([
        title_win,
        search_win,
        list_win,
        status_win,
    ])

    style = Style([
        ("bold", "bold"),
    ])

    app = Application(
        layout=Layout(root),
        key_bindings=kb,
        style=style,
        full_screen=False,
    )

    try:
        await app.run_async()
    except EOFError:
        pass

    return result
