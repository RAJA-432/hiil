from __future__ import annotations

import asyncio


class StatusIndicator:
    """Simple async spinner shown while waiting for a long operation."""

    def __init__(self, message: str = "Thinking"):
        self._message = message
        self._task: asyncio.Task | None = None

    async def _spin(self):
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        i = 0
        while True:
            print(f"\r{self._message} {frames[i % len(frames)]}", end="", flush=True)
            i += 1
            await asyncio.sleep(0.1)

    async def __aenter__(self):
        self._task = asyncio.create_task(self._spin())
        return self

    async def __aexit__(self, *args):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("\r" + " " * 40 + "\r", end="", flush=True)
