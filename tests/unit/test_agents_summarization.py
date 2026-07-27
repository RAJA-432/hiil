from __future__ import annotations

import pytest

from mcp_cli.services.agents.summarization import SummarizationMiddleware


@pytest.fixture
def summarizer():
    return SummarizationMiddleware(max_messages=4)


def make_msg(role: str, content: str = "hi") -> dict:
    return {"role": role, "content": content}


class TestShouldSummarize:
    def test_false_when_below_threshold(self, summarizer):
        msgs = [make_msg("user"), make_msg("assistant")]
        assert summarizer.should_summarize(msgs) is False

    def test_true_when_above_threshold(self, summarizer):
        msgs = [make_msg("system")] + [make_msg("user") for _ in range(6)]
        assert summarizer.should_summarize(msgs) is True

    def test_system_messages_excluded_from_count(self, summarizer):
        msgs = [make_msg("system") for _ in range(10)]
        assert summarizer.should_summarize(msgs) is False

    def test_always_true_above_threshold(self, summarizer):
        msgs = [make_msg("system")] + [make_msg("user") for _ in range(6)]
        assert summarizer.should_summarize(msgs) is True
        assert summarizer.should_summarize(msgs) is True  # flag never set by should_summarize

    def test_before_run_resets_flag(self, summarizer):
        summarizer._has_summarized = True
        summarizer.before_run([])
        assert summarizer._has_summarized is False


class TestBuildSummaryMessages:
    def test_replaces_older_messages(self, summarizer):
        msgs = [
            make_msg("system", "sys prompt"),
            make_msg("user", "old msg 1"),
            make_msg("assistant", "old msg 2"),
            make_msg("user", "recent 1"),
            make_msg("assistant", "recent 2"),
        ]
        result = summarizer.build_summary_messages(msgs, "Key facts summarized")
        # system message preserved
        assert result[0]["role"] == "system"
        # summary message inserted
        assert "[Earlier conversation summarized" in result[1]["content"]
        assert "Key facts summarized" in result[1]["content"]
        # recent messages kept (max_messages // 2 = 2)
        assert result[2:] == msgs[-2:]

    def test_keep_count_zero_returns_all_non_system(self):
        s = SummarizationMiddleware(max_messages=1)
        msgs = [make_msg("system", "sys"), make_msg("user", "only")]
        result = s.build_summary_messages(msgs, "summary")
        # -0 == 0 in Python, so all non-system messages are kept
        assert len(result) == 3  # system + summary + recent (all non-system)

    def test_empty_non_system(self):
        s = SummarizationMiddleware(max_messages=10)
        msgs = [make_msg("system", "sys")]
        result = s.build_summary_messages(msgs, "summary text")
        assert len(result) == 2
        assert result[1]["role"] == "assistant"


class TestDefaultPrompt:
    def test_default_summary_prompt(self):
        s = SummarizationMiddleware()
        assert "Condense" in s._summary_prompt
        assert "factual" in s._summary_prompt

    def test_custom_summary_prompt(self):
        s = SummarizationMiddleware(summary_prompt="Custom summary instruction")
        assert s._summary_prompt == "Custom summary instruction"


