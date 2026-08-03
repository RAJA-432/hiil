import asyncio
import json
import logging
from typing import Any

import vajra_gate.state as _state

logger = logging.getLogger("vajra_gate")

_LOG_FLUSH_EVERY = 50


async def _mcp_logging_callback(params: Any) -> None:
    logger.debug("MCP log [%s] %s: %s", getattr(params, "level", "info"), getattr(params, "logger", ""), getattr(params, "data", ""))


async def _init_chat():
    pool = _state._get_pool()
    if _state._chat is None:
        await pool.init(logging_callback=_mcp_logging_callback)
        _state._chat_stack = pool
    _state._chat = await pool.get(pool.active)
    return _state._chat


async def _require_chat(request, session_id: str | None = None):
    try:
        pool = _state._get_pool()
        if session_id:
            return await pool.get(session_id)
        await _init_chat()
        return _state._chat
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Chat init failed: {exc}")


async def _stream_chat(chat, message: str, session_id: str = "default", images: list[str] | None = None):
    from mcp_cli.services.notification_bus import NotificationBus

    bus = NotificationBus()

    def on_chunk(chunk: str):
        bus.push_tokens_nowait(chunk)

    def on_tool_event(event):
        bus.push_tool_call_nowait(event.name, event.args, "done" if event.result else "running", (event.result or "")[:200])

    async for event in _merge_events(bus, chat, message, on_chunk, on_tool_event, session_id, images=images):
        yield json.dumps(event) + "\n"


async def lekh_record(bus):
    import vajra_gate.config as config

    log_path = config.VAJRA_GATE_CHAT_LOG
    file = None
    if log_path:
        try:
            file = open(log_path, "a", encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to open chat log %s: %s", log_path, exc)

    try:
        written = 0
        async for event in bus.events():
            if file is not None:
                try:
                    file.write(json.dumps(event) + "\n")
                    written += 1
                    if written % _LOG_FLUSH_EVERY == 0:
                        file.flush()
                except Exception:
                    pass
    except (GeneratorExit, asyncio.CancelledError):
        pass
    except Exception:
        logger.warning("Failed to consume bus events (logging disabled)")
    finally:
        if file is not None:
            try:
                file.close()
            except Exception:
                pass


async def _heartbeat(bus, interval: float = 5.0):
    try:
        while True:
            await asyncio.sleep(interval)
            bus._broadcast({"type": "heartbeat", "timestamp": __import__("datetime").datetime.now().isoformat()})
    except asyncio.CancelledError:
        pass


async def _reward_observer(bus, session_id: str):
    from vajra_gate.services.reward import get_tracker

    tracker = get_tracker()
    reply_parts: list[str] = []
    try:
        async for event in bus.events():
            etype = event.get("type", "")
            if etype == "tool_event":
                status = event.get("status", "")
                ctx = {
                    "tool_name": event.get("tool", ""),
                    "valid_args": bool(event.get("args")),
                    "status": status,
                    "success": status == "done",
                }
                tracker.record(session_id, "tool_call", ctx, evaluate=True)
                if status == "done":
                    tracker.record(session_id, "tool_result", ctx, evaluate=True)
            elif etype == "tokens":
                reply_parts.append(event.get("text", ""))
            elif etype == "done":
                if reply_parts:
                    tracker.record(
                        session_id, "response",
                        {"content": "".join(reply_parts), "session_id": session_id},
                        evaluate=True,
                    )
    except (GeneratorExit, asyncio.CancelledError):
        pass
    except Exception:
        logger.debug("Reward observer error", exc_info=True)


async def _merge_events(bus, chat, message, on_chunk, on_tool_event, session_id: str = "default", images: list[str] | None = None):
    async def run_chat():
        try:
            await chat.send(message, on_chunk=on_chunk, on_tool_event=on_tool_event, notification_bus=bus, images=images)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Chat send failed")
        finally:
            try:
                await bus.push_done()
            except (GeneratorExit, asyncio.CancelledError, RuntimeError):
                pass

    chat_task = asyncio.create_task(run_chat(), name="chat_send")
    log_task = asyncio.create_task(lekh_record(bus), name="chat_log")
    hb_task = asyncio.create_task(_heartbeat(bus), name="heartbeat")
    reward_task = asyncio.create_task(_reward_observer(bus, session_id), name="reward_obs")
    tasks = (chat_task, log_task, hb_task, reward_task)
    try:
        async for event in bus.events():
            yield event
    except GeneratorExit:
        for t in tasks:
            t.cancel()
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, GeneratorExit, RuntimeError):
                pass
            except BaseExceptionGroup:
                pass
            except Exception:
                pass
