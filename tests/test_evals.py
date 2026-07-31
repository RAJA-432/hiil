from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from eval.judge import Judge, Judgment, check_golden
from eval.runner import (
    load_golden,
    load_scenarios,
    print_summary,
    run_golden_smoke,
    run_scenario,
    summarize,
    write_report,
)


def _dump_yaml(data: dict[str, Any]) -> str:
    import yaml

    return yaml.safe_dump(data, sort_keys=False)


class FakeClaudeJSON:
    model = "fake-model"

    def __init__(self, payload: dict[str, Any], content_kind: str = "str") -> None:
        self._payload = payload
        self._content_kind = content_kind
        self.messages: list[dict[str, Any]] | None = None

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> Any:
        self.messages = messages
        assert response_format == {"type": "json_object"}
        payload = json.dumps(self._payload)
        if self._content_kind == "fenced":
            content = f"```json\n{payload}\n```"
        elif self._content_kind == "list":
            content = [{"type": "text", "text": payload}]
        else:
            content = payload
        return SimpleNamespace(content=content)


class FakeClaudeBroken:
    model = "fake-model"

    def __init__(self, error: Exception | None = None, content: Any = "not json at all") -> None:
        self._error = error
        self._content = content

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> Any:
        if self._error is not None:
            raise self._error
        return SimpleNamespace(content=self._content)


class TestScenarioLoading:
    def test_loads_default_scenarios_with_all_keys(self) -> None:
        scenarios = load_scenarios()
        assert len(scenarios) == 4
        assert {s["name"] for s in scenarios} == {"qa_format", "tool_use", "rag", "json_output"}
        for s in scenarios:
            assert s["name"]
            assert "description" in s
            assert "prompt" in s
            assert isinstance(s["min_score"], float)
            assert isinstance(s["expect_tool_use"], bool)
            assert isinstance(s["rubric"], list) and s["rubric"]
            assert "allowed_tools" in s
        tool_scenario = next(s for s in scenarios if s["name"] == "tool_use")
        assert tool_scenario["expect_tool_use"] is True
        assert tool_scenario["allowed_tools"] == ["get_current_weather"]

    def test_loads_yaml_and_json_scenarios_from_dir(self, tmp_path: Path) -> None:
        yaml_scenario = {
            "name": "custom_yaml",
            "description": "yaml scenario",
            "prompt": "hello",
            "min_score": 0.5,
            "expect_tool_use": False,
            "rubric": ["be nice"],
        }
        (tmp_path / "custom_yaml.yaml").write_text(_dump_yaml(yaml_scenario), encoding="utf-8")
        json_scenario = {
            "name": "custom_json",
            "description": "json scenario",
            "prompt": "hi",
            "min_score": 0.7,
            "expect_tool_use": True,
            "rubric": ["use a tool"],
            "allowed_tools": ["foo"],
        }
        (tmp_path / "custom_json.json").write_text(json.dumps(json_scenario), encoding="utf-8")
        scenarios = load_scenarios(tmp_path)
        assert {s["name"] for s in scenarios} == {"custom_yaml", "custom_json"}
        for s in scenarios:
            assert "prompt" in s
            assert "min_score" in s
            assert "expect_tool_use" in s


class TestRunScenario:
    async def test_records_answer_and_transcript(self) -> None:
        async def fake_chat(prompt: str) -> tuple[str, str]:
            assert prompt == "What is two plus two?"
            return "Four.", "user: What is two plus two?\nassistant: Four."

        scenario = {
            "name": "qa_unknown",
            "description": "no golden",
            "prompt": "What is two plus two?",
            "min_score": 0.6,
            "expect_tool_use": False,
            "rubric": ["correct"],
        }
        result = await run_scenario(scenario, fake_chat, judge=None)
        assert result["name"] == "qa_unknown"
        assert result["answer"] == "Four."
        assert "user: What is two plus two?" in result["transcript"]
        assert result["min_score"] == 0.6
        assert result["expect_tool_use"] is False
        assert result["golden_match"] is None
        assert "tokens" in result
        assert result["pass"] is None

    async def test_golden_scenario_sets_golden_match_and_pass(self) -> None:
        golden_answer = (
            "A list is mutable and its size can change after creation, "
            "while a tuple is immutable and cannot be modified once created."
        )

        async def fake_chat(prompt: str) -> tuple[str, str]:
            return golden_answer, ""

        scenario = {
            "name": "qa_format",
            "description": "golden scenario",
            "prompt": "Explain the difference",
            "min_score": 0.6,
            "expect_tool_use": False,
            "rubric": ["accurate"],
        }
        result = await run_scenario(scenario, fake_chat, judge=None)
        assert result["golden_match"] is True
        assert result["pass"] is True

    async def test_judge_on_writes_judgment_and_pass(self) -> None:
        fake = FakeClaudeJSON({"score": 0.9, "pass": True, "rationale": "good"})
        judge = Judge(claude=fake, model="fake-model")

        async def fake_chat(prompt: str) -> tuple[str, str]:
            return "A thorough answer.", "user: hi\nassistant: A thorough answer."

        scenario = {
            "name": "rag",
            "description": "judged scenario",
            "prompt": "Explain deployment modes",
            "min_score": 0.5,
            "expect_tool_use": False,
            "rubric": ["informative"],
        }
        result = await run_scenario(scenario, fake_chat, judge=judge)
        assert result["judgment"]["score"] == 0.9
        assert result["judgment"]["pass_"] is True
        assert result["judgment"]["judge_error"] is False
        assert result["pass"] is True


class TestCheckGolden:
    def test_matching_text_normalizes_whitespace(self) -> None:
        assert check_golden("  hello   world  ", "hello world") is True

    def test_non_matching_text(self) -> None:
        assert check_golden("goodbye world", "hello world") is False

    def test_matching_json_ignores_key_order(self) -> None:
        expected = {"product": "widget", "price": 9.99, "in_stock": True}
        answer = '{"price": 9.99, "in_stock": true, "product": "widget"}'
        assert check_golden(answer, expected) is True

    def test_non_matching_json(self) -> None:
        expected = {"product": "widget", "price": 9.99, "in_stock": True}
        answer = '{"product": "other", "price": 1.00, "in_stock": false}'
        assert check_golden(answer, expected) is False

    def test_invalid_json_does_not_match(self) -> None:
        assert check_golden("not json", {"product": "widget"}) is False


class TestJudgeHeuristic:
    async def test_returns_judgment_without_claude(self) -> None:
        judge = Judge()
        j = await judge.judge("Some question?", "A reasonably detailed answer with enough substance.", ["informative"])
        assert isinstance(j, Judgment)
        assert 0.0 <= j.score <= 1.0
        assert j.judge_error is False
        assert j.rationale

    async def test_empty_answer_scores_zero(self) -> None:
        judge = Judge()
        j = await judge.judge("q", "", ["informative"])
        assert j.score == 0.0
        assert j.pass_ is False
        assert j.judge_error is False

    async def test_tool_expectation_checks_transcript(self) -> None:
        judge = Judge()
        passed = await judge.judge(
            "use a tool",
            "The temperature is 21 degrees.",
            ["must call the tool"],
            transcript="tool_use: get_current_weather",
        )
        assert passed.score > 0.0
        assert passed.pass_ is True
        failed = await judge.judge(
            "use a tool",
            "I cannot answer.",
            ["must call the tool"],
            transcript="assistant: I cannot answer.",
        )
        assert failed.score == 0.0
        assert failed.pass_ is False


class TestJudgeWithClaude:
    async def test_parses_valid_json(self) -> None:
        fake = FakeClaudeJSON({"score": 0.85, "pass": True, "rationale": "covers rubric"})
        judge = Judge(claude=fake, model="fake-model")
        j = await judge.judge("q", "answer text", ["rubric"])
        assert j.score == 0.85
        assert j.pass_ is True
        assert j.rationale == "covers rubric"
        assert j.judge_error is False
        assert fake.messages is not None
        assert fake.messages[0]["role"] == "system"
        assert fake.messages[1]["role"] == "user"

    async def test_parses_fenced_json_content(self) -> None:
        fake = FakeClaudeJSON({"score": 0.6, "pass": True, "rationale": "ok"}, content_kind="fenced")
        judge = Judge(claude=fake)
        j = await judge.judge("q", "answer", ["rubric"])
        assert j.score == 0.6
        assert j.pass_ is True

    async def test_parses_list_content_parts(self) -> None:
        fake = FakeClaudeJSON({"score": 0.5, "pass": False, "rationale": "weak"}, content_kind="list")
        judge = Judge(claude=fake)
        j = await judge.judge("q", "answer", ["rubric"])
        assert j.score == 0.5
        assert j.pass_ is False
        assert j.judge_error is False

    async def test_score_is_clamped_to_unit_range(self) -> None:
        fake = FakeClaudeJSON({"score": 1.7, "pass": True, "rationale": "over"})
        judge = Judge(claude=fake)
        assert (await judge.judge("q", "answer", [])).score == 1.0
        fake = FakeClaudeJSON({"score": -0.4, "pass": False, "rationale": "under"})
        judge = Judge(claude=fake)
        assert (await judge.judge("q", "answer", [])).score == 0.0

    async def test_invalid_json_sets_judge_error(self) -> None:
        judge = Judge(claude=FakeClaudeBroken(content="not json at all"))
        j = await judge.judge("q", "answer", ["rubric"])
        assert j.judge_error is True
        assert j.score == 0.0
        assert j.pass_ is False
        assert j.rationale.startswith("judge_error:")

    async def test_exception_sets_judge_error_without_crash(self) -> None:
        judge = Judge(claude=FakeClaudeBroken(error=RuntimeError("boom")))
        j = await judge.judge("q", "answer", ["rubric"])
        assert j.judge_error is True
        assert j.score == 0.0
        assert j.pass_ is False


class TestGoldenSmoke:
    def test_repo_goldens_are_self_consistent(self) -> None:
        ok, report = run_golden_smoke()
        assert ok is True
        assert report["mode"] == "golden_smoke"
        assert report["scenarios_checked"] == 2
        assert report["passed"] == 2
        assert report["failed"] == 0
        assert {r["scenario"] for r in report["results"]} == {"qa_format", "json_output"}
        assert all(r["match"] is True for r in report["results"])

    def test_wrong_expected_value_fails_match(self) -> None:
        golden = load_golden("qa_format")
        assert golden is not None
        expected = golden["answer"]
        assert check_golden(expected, expected) is True
        assert check_golden(expected, "A totally different answer.") is False

    def test_corrupted_golden_fails_smoke(self, tmp_path: Path) -> None:
        scenario_dir = tmp_path / "scenarios"
        golden_dir = tmp_path / "goldens"
        scenario_dir.mkdir()
        golden_dir.mkdir()
        scenario = {
            "name": "qa_format",
            "description": "smoke scenario",
            "prompt": "Explain the difference",
            "min_score": 0.6,
            "expect_tool_use": False,
            "rubric": ["accurate"],
        }
        (scenario_dir / "qa_format.yaml").write_text(_dump_yaml(scenario), encoding="utf-8")
        (golden_dir / "qa_format.json").write_text("{ not valid json", encoding="utf-8")
        ok, report = run_golden_smoke(scenario_dir, golden_dir)
        assert ok is False
        assert report["failed"] == 1
        assert report["results"][0]["match"] is False
        assert report["results"][0]["error"]

    def test_scenario_without_golden_is_not_checked(self, tmp_path: Path) -> None:
        scenario_dir = tmp_path / "scenarios"
        scenario_dir.mkdir()
        scenario = {
            "name": "qa_format",
            "description": "smoke scenario",
            "prompt": "Explain the difference",
            "min_score": 0.6,
            "expect_tool_use": False,
            "rubric": ["accurate"],
        }
        (scenario_dir / "qa_format.yaml").write_text(_dump_yaml(scenario), encoding="utf-8")
        ok, report = run_golden_smoke(scenario_dir, tmp_path / "goldens")
        assert report["scenarios_checked"] == 0
        assert ok is False


class TestSummaryReport:
    def test_summary_and_report_without_judge(self, tmp_path: Path) -> None:
        results = [
            {
                "name": "qa_format",
                "description": "",
                "prompt": "q",
                "min_score": 0.6,
                "expect_tool_use": False,
                "answer": "match",
                "transcript": "",
                "tokens": {"answer_chars": 5},
                "golden_match": True,
                "pass": True,
            },
            {
                "name": "rag",
                "description": "",
                "prompt": "q",
                "min_score": 0.6,
                "expect_tool_use": False,
                "answer": "no",
                "transcript": "",
                "tokens": {"answer_chars": 2},
                "golden_match": False,
                "pass": False,
            },
        ]
        rows = summarize(results)
        assert rows[0]["scenario"] == "qa_format"
        assert rows[0]["passed"] is True
        assert rows[0]["score"] == 1.0
        assert rows[1]["scenario"] == "rag"
        assert rows[1]["passed"] is False
        assert rows[1]["score"] == 0.0
        out = tmp_path / "report.json"
        write_report(results, out)
        assert out.exists()
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["results"] == results
        assert len(payload["summary"]) == 2

    def test_print_summary_renders_table(self, capsys: Any) -> None:
        results = [
            {
                "name": "qa_format",
                "description": "",
                "prompt": "q",
                "min_score": 0.6,
                "expect_tool_use": False,
                "answer": "x",
                "transcript": "",
                "tokens": {},
                "golden_match": True,
                "pass": True,
            }
        ]
        table = print_summary(results)
        assert "qa_format" in table
        assert "PASS" in table
        captured = capsys.readouterr()
        assert "qa_format" in captured.out
