import asyncio
import json
import logging
from typing import Any

import vajram.state as _state

logger = logging.getLogger("vajram")


async def _mcp_logging_callback(params: Any) -> None:
    logger.debug("MCP log [%s] %s: %s", getattr(params, "level", "info"), getattr(params, "logger", ""), getattr(params, "data", ""))


async def _init_chat():
    if _state._chat is not None:
        return _state._chat
    from contextlib import AsyncExitStack

    from mcp_cli.services.factory import create_chat
    _state._chat_stack = AsyncExitStack()
    _state._chat = await create_chat(_state._chat_stack, logging_callback=_mcp_logging_callback)
    return _state._chat


async def _require_chat(request):
    try:
        return await _init_chat()
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Chat init failed: {exc}")


async def _stream_chat(chat, message: str):
    from mcp_cli.services.notification_bus import NotificationBus

    bus = NotificationBus()
    full_reply = ""
    tool_call_count = 0

    def on_chunk(chunk: str):
        nonlocal full_reply
        full_reply += chunk
        bus.push_tokens_nowait(full_reply)

    def on_tool_event(event):
        nonlocal tool_call_count
        tool_call_count += 1
        bus.push_tool_call_nowait(event.name, event.args, "done" if event.result else "running", (event.result or "")[:200])

    async for event in _merge_events(bus, chat, message, on_chunk, on_tool_event):
        yield json.dumps(event) + "\n"


async def _log_events(bus):
    import aiofiles

    from vajram.config import VAJRAM_CHAT_LOG

    if not VAJRAM_CHAT_LOG:
        try:
            async for _ in bus.events():
                pass
        except Exception:
            logger.warning("Failed to consume bus events (logging disabled)")
            pass
        return
    try:
        async with aiofiles.open(VAJRAM_CHAT_LOG, "a", encoding="utf-8") as f:
            async for event in bus.events():
                await f.write(json.dumps(event) + "\n")
    except Exception:
        logger.exception("Failed to log events to file")
        try:
            async for _ in bus.events():
                pass
        except Exception:
            logger.warning("Failed to consume bus events (after file log failure)")
            pass


async def _merge_events(bus, chat, message, on_chunk, on_tool_event):
    async def run_chat():
        try:
            await chat.send(message, on_chunk=on_chunk, on_tool_event=on_tool_event, notification_bus=bus)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Chat send failed")
            pass
        finally:
            await bus.push_done()

    chat_task = asyncio.create_task(run_chat(), name="chat_send")
    log_task = asyncio.create_task(_log_events(bus), name="chat_log")
    try:
        async for event in bus.events():
            yield event
    except GeneratorExit:
        chat_task.cancel()
        log_task.cancel()
        raise
    finally:
        chat_task.cancel()
        log_task.cancel()
        try:
            await chat_task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await log_task
        except (asyncio.CancelledError, Exception):
            pass
