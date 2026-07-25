import pytest

from mcp_cli.ui.status import StatusIndicator


@pytest.mark.asyncio
async def test_status_indicator_context_manager():
    flag = [False]
    async with StatusIndicator("Working"):
        flag[0] = True
    assert flag[0] is True


@pytest.mark.asyncio
async def test_status_indicator_cancels_on_exit():
    indicator = StatusIndicator("Testing")
    assert indicator._task is None
    async with indicator as sp:
        assert indicator._task is not None
        assert not indicator._task.done()
    assert indicator._task is None or indicator._task.done()


@pytest.mark.asyncio
async def test_status_indicator_custom_message():
    indicator = StatusIndicator("Custom msg")
    assert indicator._message == "Custom msg"


