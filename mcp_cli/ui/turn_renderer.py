from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from mcp_cli.services.notification_bus import NotificationBus
from mcp_cli.services.usage import format_cost
from mcp_cli.ui.codeblock import CodeBlockAccumulator
from mcp_cli.ui.messaging import MessageManager, SpinnerManager
from mcp_cli.ui.streaming import StreamingRenderer
from mcp_cli.ui.themes import RS


class TurnRenderer:
    """Owns the streaming-render orchestration for a single chat turn."""

    def __init__(
        self,
        msg: MessageManager,
        spinner: SpinnerManager,
        codeblocks: CodeBlockAccumulator,
        streaming: type[StreamingRenderer],
        theme: Any,
    ) -> None:
        self._msg = msg
        self._spinner = spinner
        self._codeblocks = codeblocks
        self._streaming = streaming
        self._theme = theme

    async def run(
        self,
        chat: Any,
        user_input: str,
        on_approval: Callable[[str, dict[str, Any]], Awaitable[bool]],
    ) -> str | None:
        t = self._theme
        msg = self._msg
        reply: str | None = None
        try:
            print(msg.user_header())
            print(f"  {msg._renderer.palette_dict['fg']}{user_input}{RS}")
            print(f"  {msg.user_separator(len(user_input))}")
            print()

            buf: list[str] = []
            self._spinner.start("thinking")
            header = msg.assistant_header()
            started = False

            streaming = self._streaming(
                msg._renderer.render_inline,
                on_output=lambda text: print(text, end="", flush=True),
            )

            def on_chunk(c: str) -> None:
                nonlocal started
                if not started:
                    started = True
                    self._spinner.clear()
                    print(f"{header}\n  ", end="", flush=True)
                buf.append(c)

                # Use the CodeBlockAccumulator to handle streaming code
                # and the throttled StreamingRenderer for inline text.
                # Since we are streaming, we feed it to the accumulator.
                self._codeblocks.feed(c, on_text=streaming.push, on_block=streaming.emit_raw)

            bus = NotificationBus()
            phases: list[dict[str, Any]] = []

            async def _consume_phases() -> None:
                try:
                    async for event in bus.events():
                        if event.get("type") == "log":
                            # Update spinner status with log message
                            message = event.get("text", "")
                            self._spinner.status = message
                        elif event.get("type") == "state":
                            phase = event.get("phase", "UNKNOWN")
                            agent_id = event.get("agent_id", "?")
                            # Update spinner status and record for final report
                            self._spinner.status = f"[{agent_id}] {phase}"
                            phases.append(event)
                        elif event.get("type") == "done":
                            break
                except asyncio.CancelledError:
                    pass

            consumer = asyncio.create_task(_consume_phases())

            try:
                usage_before = chat.usage.session_summary()
                reply = await chat.send(
                    user_input,
                    on_chunk=on_chunk,
                    on_approval=on_approval,
                    notification_bus=bus,
                )
                self._spinner.stop()

                # Finalize any unclosed code blocks
                self._codeblocks.flush(on_text=streaming.push, on_block=streaming.emit_raw)
                streaming.flush_now()

                printed = "".join(buf)
                final = reply or printed
                if final:
                    print()
                    print(f"{msg.assistant_separator()}")
                    usage_after = chat.usage.session_summary()
                    in_turn = usage_after['input_tokens'] - usage_before['input_tokens']
                    out_turn = usage_after['output_tokens'] - usage_before['output_tokens']
                    cost_turn = usage_after['cost'] - usage_before['cost']
                    print(
                        f"{t.ansi('muted')}  {in_turn + out_turn:,} tokens "
                        f"({in_turn} in / {out_turn} out) {format_cost(cost_turn)}{RS}"
                    )
                    print()
            except asyncio.CancelledError:
                self._spinner.stop()
                streaming.flush_now()
                print(f"\n{t.ansi('muted')}[cancelled] Turn interrupted.{RS}")
            finally:
                await bus.push_done()
                try:
                    await asyncio.wait_for(consumer, timeout=2.0)
                except TimeoutError:
                    consumer.cancel()
                    try:
                        await consumer
                    except (asyncio.CancelledError, RuntimeError):
                        pass
                while bus._queues:
                    q = bus._queues.pop()
                    while not q.empty():
                        q.get_nowait()
        except Exception as exc:
            self._spinner.stop()
            print(f"{t.ansi('error')}[error]{RS} {exc}")
        return reply
