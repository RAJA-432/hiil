from __future__ import annotations

import asyncio
import sys
from contextlib import AsyncExitStack

from dotenv import load_dotenv

from mcp_cli.services.factory import create_chat
from mcp_cli.services.logging import get_logger
from mcp_cli.ui.app import CliApp

load_dotenv()
logger = get_logger("main")


async def main() -> None:
    async with AsyncExitStack() as stack:
        chat = await create_chat(stack)
        cli = CliApp(chat)
        await cli.run()


def _run_main() -> None:
    if sys.platform == "win32" and sys.version_info < (3, 14):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())


if __name__ == "__main__":
    _run_main()
