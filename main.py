from __future__ import annotations

import asyncio
import sys

from mcp_cli.main import main

if __name__ == "__main__":
    if sys.platform == "win32":
        if sys.version_info < (3, 14):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    asyncio.run(main())
