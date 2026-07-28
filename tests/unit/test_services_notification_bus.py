from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from mcp_cli.services.notification_bus import NotificationBus


@pytest.mark.asyncio
async def test_push_log():
    bus = NotificationBus()
    collected: list[dict] = []

    async def collect():
        async for event in bus.events():
            collected.append(event)
            if event["type"] == "done":
                break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    await bus.push_log("info", "hello", source="test")
    await bus.push_done()
    await task

    assert len(collected) == 2
    assert collected[0] == {"type": "log", "level": "info", "text": "hello", "source": "test"}


@pytest.mark.asyncio
async def test_push_progress():
    bus = NotificationBus()
    collected: list[dict] = []

    async def collect():
        async for event in bus.events():
            collected.append(event)
            if event["type"] == "done":
                break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    await bus.push_progress(5, 10, "processing")
    await bus.push_done()
    await task

    assert collected[0]["type"] == "progress"
    assert collected[0]["current"] == 5
    assert collected[0]["total"] == 10
    assert collected[0]["percent"] == 50.0


@pytest.mark.asyncio
async def test_push_progress_zero_total():
    bus = NotificationBus()
    collected: list[dict] = []

    async def collect():
        async for event in bus.events():
            collected.append(event)
            if event["type"] == "done":
                break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    await bus.push_progress(0, 0, "no total")
    await bus.push_done()
    await task

    assert collected[0]["percent"] == 0


@pytest.mark.asyncio
async def test_push_tool_call():
    bus = NotificationBus()
    collected: list[dict] = []

    async def collect():
        async for event in bus.events():
            collected.append(event)
            if event["type"] == "done":
                break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    await bus.push_tool_call("read_file", {"path": "/test"}, "start")
    await bus.push_done()
    await task

    assert collected[0] == {
        "type": "tool_event",
        "tool": "read_file",
        "status": "start",
        "args": {"path": "/test"},
        "result": "",
    }


@pytest.mark.asyncio
async def test_push_tool_call_truncates_result():
    bus = NotificationBus()
    collected: list[dict] = []

    async def collect():
        async for event in bus.events():
            collected.append(event)
            if event["type"] == "done":
                break

    long_result = "x" * 500
    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    await bus.push_tool_call("read_file", {}, "done", result=long_result)
    await bus.push_done()
    await task

    assert len(collected[0]["result"]) == 200


def test_push_tool_call_nowait():
    bus = NotificationBus()
    bus.push_tool_call_nowait("write_file", {}, "done", result="ok")
    assert len(bus._queues) == 0


def test_push_tokens_nowait():
    bus = NotificationBus()
    bus.push_tokens_nowait("streaming text")
    assert len(bus._queues) == 0


@pytest.mark.asyncio
async def test_push_tokens():
    bus = NotificationBus()
    collected: list[dict] = []

    async def collect():
        async for event in bus.events():
            collected.append(event)
            if event["type"] == "done":
                break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    await bus.push_tokens("hello")
    await bus.push_done()
    await task

    assert collected[0]["type"] == "tokens"
    assert collected[0]["text"] == "hello"


@pytest.mark.asyncio
async def test_push_interrupt():
    bus = NotificationBus()
    collected: list[dict] = []

    async def collect():
        async for event in bus.events():
            collected.append(event)
            if event["type"] == "done":
                break

    actions = [{"type": "request_approval", "tool": "write_file"}]
    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    await bus.push_interrupt(actions)
    await bus.push_done()
    await task

    assert collected[0]["type"] == "interrupt"
    assert collected[0]["action_requests"] == actions


@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = NotificationBus()
    collected1: list[dict] = []
    collected2: list[dict] = []

    async def collect1():
        async for event in bus.events():
            collected1.append(event)
            if event["type"] == "done":
                break

    async def collect2():
        async for event in bus.events():
            collected2.append(event)
            if event["type"] == "done":
                break

    task1 = asyncio.create_task(collect1())
    task2 = asyncio.create_task(collect2())
    await asyncio.sleep(0)
    await bus.push_log("info", "broadcast")
    await bus.push_done()
    await task1
    await task2

    assert len(collected1) == 2
    assert len(collected2) == 2
    assert collected1[0]["text"] == "broadcast"
    assert collected2[0]["text"] == "broadcast"


@pytest.mark.asyncio
async def test_subscriber_consumes_and_stops():
    bus = NotificationBus()
    collected: list[dict] = []

    async def collect():
        async for event in bus.events():
            collected.append(event)
            if event["type"] == "done":
                break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    await bus.push_log("info", "before done")
    await bus.push_done()
    await task
    await asyncio.sleep(0)

    assert len(collected) == 2
    assert collected[0]["text"] == "before done"


@patch("mcp_cli.services.notification_bus._log")
def test_queue_full_logs_warning(mock_log):
    bus = NotificationBus()
    q = asyncio.Queue(maxsize=1)
    bus._queues.append(q)
    q.put_nowait({"type": "blocking"})

    bus._broadcast({"type": "dropped"})
    mock_log.warning.assert_called_once_with(
        "NotificationBus subscriber queue full, dropping event %s", "dropped",
    )
