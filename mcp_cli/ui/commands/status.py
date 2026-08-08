from __future__ import annotations

from mcp_cli.ui.themes import RS


def print_status(chat, theme) -> None:
    s = chat.get_status()
    print(f"{theme.style_box('secondary', 'System Status')}{RS}")
    print(f"  {theme.icon('session')} {theme.ansi('primary')}Session:{RS}   {s['session']}{RS}")
    print(f"  {theme.icon('message')} {theme.ansi('primary')}Messages:{RS}  {s['messages']}{RS}")
    print(f"  {theme.icon('network')} {theme.ansi('primary')}Provider:{RS}  {s['provider']}{RS}")
    print(f"  {theme.icon('model')} {theme.ansi('primary')}Model:{RS}     {s['model']}{RS}")
    print(f"  {theme.icon('tool')} {theme.ansi('primary')}Tools:{RS}     {s['tools']}{RS}")
    print(f"  {theme.icon('server')} {theme.ansi('primary')}Servers:{RS}   {', '.join(s['servers']) if s['servers'] else 'none'}{RS}")
