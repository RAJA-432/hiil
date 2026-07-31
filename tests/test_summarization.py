from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from mcp_cli.services.agents.models import AgentConfig
from mcp_cli.services.agents.runner import AgentRunner
from mcp_cli.services.agents.summarization import SummarizationMiddleware


def _tool_message() -> SimpleNamespace:
    return SimpleNamespace(
        content="",
        tool_calls=[
            SimpleNamespace(
                id="call_noop_1",
                function=SimpleNamespace(name="noop", arguments="{}"),
            )
        ],
    )


def _final_message(content: str = "final answer") -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=None)


def _system(content: str = "system prompt") -> dict[str, str]:
    return {"role": "system", "content": content}


def _user(content: str = "user message") -> dict[str, str]:
    return {"role": "user", "content": content}


class FakeStreamer:
    def __init__(self, responses: list[tuple[Any, int, int]]) -> None:
        self._responses = list(responses)
        self.call_count = 0
        self.summary_call_count = 0
        self.summary_response = "SUMMARY TEXT"

    async def chat(self, messages, tools=None, on_chunk=None, response_format=None):
        self.call_count += 1
        if len(messages) == 1 and messages[0].get("role") == "user":
            self.summary_call_count += 1
            return SimpleNamespace(content=self.summary_response), 5, 5
        message, input_tokens, output_tokens = self._responses.pop(0)
        return message, input_tokens, output_tokens


class FakeParentChat:
    def __init__(self, streamer: FakeStreamer) -> None:
        self.streamer = streamer
        self.tools_by_name: dict[str, Any] = {}
        self.clients: dict[str, Any] = {}


def _make_streamer() -> FakeStreamer:
    return FakeStreamer(
        [
            (_tool_message(), 600, 100),
            (_final_message(), 10, 5),
        ]
    )


class TestSummarizationMiddleware:
    def test_count_trigger(self) -> None:
        mw = SummarizationMiddleware(max_messages=3)
        messages = [_system(), _user("one"), _user("two"), _user("three")]
        assert mw.should_summarize(messages) is False
        messages.append(_user("four"))
        assert mw.should_summarize(messages) is True
        system_heavy = [_system() for _ in range(10)] + [_user("one"), _user("two"), _user("three")]
        assert mw.should_summarize(system_heavy) is False

    def test_token_trigger(self) -> None:
        mw = SummarizationMiddleware(max_messages=1000, token_threshold=100)
        messages = [_system(), _user("one")]
        assert mw.should_summarize(messages, total_tokens=101) is True
        assert mw.should_summarize(messages, total_tokens=100) is False
        thresholdless = SummarizationMiddleware(max_messages=1000, token_threshold=0)
        assert thresholdless.should_summarize(messages, total_tokens=1_000_000) is False

    def test_token_trigger_requires_total_tokens(self) -> None:
        mw = SummarizationMiddleware(max_messages=1000, token_threshold=100)
        messages = [_system(), _user("one")]
        assert mw.should_summarize(messages, total_tokens=None) is False

    def test_mark_summarized_once(self) -> None:
        mw = SummarizationMiddleware(max_messages=1, token_threshold=1)
        messages = [_system(), _user("one"), _user("two")]
        assert mw.should_summarize(messages, total_tokens=10) is True
        mw.mark_summarized()
        assert mw.should_summarize(messages, total_tokens=10) is False
        mw.before_run(messages)
        assert mw.should_summarize(messages, total_tokens=10) is True

    def test_build_summary_messages_structure(self) -> None:
        mw = SummarizationMiddleware(max_messages=4)
        systems = [_system("s1"), _system("s2")]
        turns = [_user("one"), _user("two"), _user("three"), _user("four")]
        result = mw.build_summary_messages(systems + turns, "the summary")
        assert result[:2] == systems
        summary = result[2]
        assert summary["role"] == "assistant"
        assert summary["content"].startswith("[Earlier conversation summarized: ")
        assert summary["content"].endswith("the summary]")
        assert result[3:] == turns[-2:]


class TestRunnerSummarization:
    async def test_runner_token_threshold_archives_raw_messages(self) -> None:
        mw = SummarizationMiddleware(max_messages=1000, token_threshold=500)
        config = AgentConfig(name="a", role="assistant", token_budget=0, middleware=[mw])
        streamer = _make_streamer()
        runner = AgentRunner(config, FakeParentChat(streamer))
        result = await runner.run("do the thing")
        assert result.output == "final answer"
        assert result.status == "completed"
        archive = runner.summarized_archive
        assert len(archive) == 3
        assert archive[0]["role"] == "system"
        assert archive[1] == {"role": "user", "content": "do the thing"}
        assert archive[2]["role"] == "assistant"
        assert archive[2]["tool_calls"]
        assert streamer.summary_call_count == 1
        archive.append({"role": "user", "content": "injected"})
        assert len(runner.summarized_archive) == 3

    async def test_runner_auto_85_percent_of_budget(self) -> None:
        mw = SummarizationMiddleware(max_messages=1000)
        config = AgentConfig(
            name="a",
            role="assistant",
            token_budget=800,
            middleware=[mw],
        )
        streamer = _make_streamer()
        runner = AgentRunner(config, FakeParentChat(streamer))
        result = await runner.run("do the thing")
        assert result.output == "final answer"
        assert result.status == "completed"
        assert mw.token_threshold == int(800 * 0.85)
        assert len(runner.summarized_archive) == 3
        assert streamer.summary_call_count == 1

    async def test_runner_no_summarize_when_under_threshold(self) -> None:
        mw = SummarizationMiddleware(max_messages=1000, token_threshold=10000)
        config = AgentConfig(name="a", role="assistant", token_budget=0, middleware=[mw])
        streamer = _make_streamer()
        runner = AgentRunner(config, FakeParentChat(streamer))
        result = await runner.run("do the thing")
        assert result.output == "final answer"
        assert runner.summarized_archive == []
        assert streamer.call_count == 2
        assert streamer.summary_call_count == 0

    async def test_summarization_via_dict_spec(self) -> None:
        config = AgentConfig(
            name="a",
            role="assistant",
            middleware=[{"type": "summarization", "max_messages": 1, "token_threshold": 0}],
        )
        assert isinstance(config.middleware[0], SummarizationMiddleware)
        streamer = _make_streamer()
        runner = AgentRunner(config, FakeParentChat(streamer))
        result = await runner.run("do the thing")
        assert result.output == "final answer"
        assert len(runner.summarized_archive) == 3
        assert streamer.summary_call_count == 1
