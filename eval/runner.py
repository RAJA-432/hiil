"""Command-line runner for evaluation scenarios.

Usage: ``python -m eval.runner --scenario <name|all> --judge on|off --out report.json --chat <path>``

The live path lazily builds the real chat (``mcp_cli.services.factory.create_chat``)
only inside the asyncio entry point, so importing this module is hermetic.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.judge import Judge, check_golden

PACKAGE_DIR = Path(__file__).resolve().parent
SCENARIO_DIR = PACKAGE_DIR / "scenarios"
GOLDEN_DIR = PACKAGE_DIR / "goldens"

ChatCallable = Callable[[str], Awaitable[tuple[Any, str]]]


def load_scenarios(scenario_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """Load all scenario definitions (YAML or JSON) from a directory."""
    base = Path(scenario_dir) if scenario_dir else SCENARIO_DIR
    files = (
        sorted(base.glob("*.yaml"))
        + sorted(base.glob("*.yml"))
        + sorted(base.glob("*.json"))
    )
    scenarios: list[dict[str, Any]] = []
    for path in files:
        data = _load_scenario_file(path)
        if data is not None:
            scenarios.append(data)
    return scenarios


def _load_scenario_file(path: Path) -> dict[str, Any] | None:
    try:
        if path.suffix.lower() in (".yaml", ".yml"):
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"warning: skipping {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict) or not data.get("name"):
        print(f"warning: skipping {path}: missing 'name'", file=sys.stderr)
        return None
    data["name"] = str(data["name"])
    data.setdefault("description", "")
    data.setdefault("min_score", 0.0)
    data.setdefault("expect_tool_use", False)
    data.setdefault("rubric", [])
    data.setdefault("allowed_tools", [])
    return data


def get_scenario(name: str, scenario_dir: str | Path | None = None) -> dict[str, Any]:
    """Return a single scenario by name, raising KeyError if missing."""
    for scenario in load_scenarios(scenario_dir):
        if scenario["name"] == name:
            return scenario
    raise KeyError(f"scenario not found: {name}")


def load_golden(name: str, golden_dir: str | Path | None = None) -> Any | None:
    """Load a golden snapshot for a scenario, or None when none exists."""
    base = Path(golden_dir) if golden_dir else GOLDEN_DIR
    path = base / f"{name}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run_golden_smoke(
    scenario_dir: str | Path | None = None,
    golden_dir: str | Path | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Hermetically verify golden snapshots parse and are self-consistent.

    No LLM, chat, or servers are involved: scenarios are loaded, and for each
    scenario that has a golden snapshot the smoke asserts that
    ``check_golden(expected, expected)`` is True.
    """
    scenarios = load_scenarios(scenario_dir)
    base = Path(golden_dir) if golden_dir else GOLDEN_DIR
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        name = scenario["name"]
        path = base / f"{name}.json"
        if not path.exists():
            continue
        try:
            golden = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            results.append({"scenario": name, "match": False, "error": str(exc)})
            continue
        expected = golden.get("answer") if isinstance(golden, dict) else golden
        results.append({"scenario": name, "match": check_golden(expected, expected), "error": None})
    passed = sum(1 for result in results if result["match"])
    ok = bool(results) and passed == len(results)
    report = {
        "mode": "golden_smoke",
        "scenarios_checked": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    return ok, report


def _answer_text(answer: Any) -> str:
    if isinstance(answer, str):
        return answer
    if isinstance(answer, list):
        return " ".join(str(p.get("text", "") if isinstance(p, dict) else p) for p in answer)
    if isinstance(answer, dict):
        return json.dumps(answer, sort_keys=True)
    return str(answer)


def _tool_use_observed(text: Any) -> bool:
    lowered = _answer_text(text).lower()
    markers = ("tool_call", "tool_use", "tool_result", "function_call")
    return any(marker in lowered for marker in markers)


def _estimate_tokens(answer: Any, transcript: str) -> dict[str, int]:
    answer_text = _answer_text(answer)
    return {
        "answer_chars": len(answer_text),
        "answer_words": len(answer_text.split()),
        "transcript_chars": len(transcript),
    }


async def run_scenario(
    scenario: dict[str, Any],
    chat_callable: ChatCallable,
    judge: Judge | None = None,
) -> dict[str, Any]:
    """Run one scenario and collect the answer, transcript, and scores."""
    answer, transcript = await chat_callable(scenario["prompt"])
    result: dict[str, Any] = {
        "name": scenario["name"],
        "description": scenario.get("description", ""),
        "prompt": scenario["prompt"],
        "min_score": float(scenario.get("min_score", 0.0)),
        "expect_tool_use": bool(scenario.get("expect_tool_use", False)),
        "answer": answer,
        "transcript": transcript,
        "tokens": _estimate_tokens(answer, transcript),
        "golden_match": None,
    }
    golden = load_golden(scenario["name"])
    if golden is not None:
        expected = golden.get("answer") if isinstance(golden, dict) else golden
        result["golden_match"] = check_golden(answer, expected)
    if judge is not None:
        judgment = await judge.judge(
            question=scenario["prompt"],
            answer=answer,
            rubric=list(scenario.get("rubric", [])),
            transcript=transcript or "",
        )
        result["judgment"] = asdict(judgment)
    result["pass"] = _compute_pass(result, scenario)
    return result


def _compute_pass(result: dict[str, Any], scenario: dict[str, Any]) -> bool | None:
    """Derive pass/fail from golden match, judgment, or a transcript heuristic."""
    golden_match = result.get("golden_match")
    if golden_match is not None:
        return bool(golden_match)
    judgment = result.get("judgment")
    if judgment is not None:
        passed = bool(judgment.get("pass_", False))
        score = float(judgment.get("score", 0.0))
        min_score = float(scenario.get("min_score", 0.0))
        return passed and score >= min_score
    if scenario.get("expect_tool_use"):
        combined = f"{result.get('transcript', '')} {result.get('answer', '')}"
        return _tool_use_observed(combined)
    return None


def summarize(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reduce result dicts to compact summary rows for reports."""
    rows: list[dict[str, Any]] = []
    for result in results:
        rows.append(
            {
                "scenario": result["name"],
                "passed": result.get("pass"),
                "score": _result_score(result),
                "golden_match": result.get("golden_match"),
                "judge_error": _judge_error(result),
            }
        )
    return rows


def _result_score(result: dict[str, Any]) -> float | None:
    golden_match = result.get("golden_match")
    if golden_match is not None:
        return 1.0 if golden_match else 0.0
    judgment = result.get("judgment")
    if judgment is not None:
        return float(judgment.get("score", 0.0))
    return None


def _judge_error(result: dict[str, Any]) -> bool | None:
    judgment = result.get("judgment")
    if judgment is None:
        return None
    return bool(judgment.get("judge_error", False))


def print_summary(results: list[dict[str, Any]]) -> str:
    """Print and return a human-readable pass/fail/score table."""
    rows = summarize(results)
    lines = [
        f"{'scenario':<16} {'pass':<6} {'score':<6}",
        "-" * 32,
    ]
    for row in rows:
        passed = row["passed"]
        label = "PASS" if passed is True else "FAIL" if passed is False else "SKIP"
        score = f"{row['score']:.2f}" if row["score"] is not None else "-"
        lines.append(f"{row['scenario']:<16} {label:<6} {score:<6}")
    table = "\n".join(lines)
    print(table)
    return table


def print_smoke_report(report: dict[str, Any]) -> str:
    """Print and return a human-readable golden smoke table."""
    lines = [
        f"{'scenario':<16} {'match':<6}",
        "-" * 22,
    ]
    for result in report["results"]:
        label = "OK" if result["match"] else "FAIL"
        suffix = f" ({result['error']})" if result.get("error") else ""
        lines.append(f"{result['scenario']:<16} {label:<6}{suffix}")
    table = "\n".join(lines)
    print(table)
    print(f"golden smoke: {report['passed']}/{report['scenarios_checked']} passed")
    return table


def write_report(results: list[dict[str, Any]], path: str | Path) -> Path:
    """Write results plus summary rows to a JSON report file."""
    out = Path(path)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "results": results,
        "summary": summarize(results),
    }
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="eval.runner", description="Run evaluation scenarios for the chat stack.")
    parser.add_argument("--scenario", default="all", help="Scenario name or 'all' (default: all)")
    parser.add_argument("--judge", choices=["on", "off"], default="on", help="Enable the LLM judge (default: on)")
    parser.add_argument("--out", default="report.json", help="Path to write the report JSON (default: report.json)")
    parser.add_argument("--chat", default=None, help="Path to a Python module exposing async chat(prompt) -> (answer, transcript)")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Hermetic golden-only smoke check: no LLM, no chat, no servers",
    )
    return parser.parse_args(argv)


def _resolve_scenarios(name: str) -> list[dict[str, Any]]:
    if name == "all":
        return load_scenarios()
    return [get_scenario(name)]


def _load_custom_chat(path: str) -> ChatCallable:
    import importlib.util

    module_path = Path(path).resolve()
    spec = importlib.util.spec_from_file_location("eval_custom_chat", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"could not load chat module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, "chat", None)
    if not callable(func):
        raise SystemExit(f"chat module {path} must expose a callable `chat(prompt)` returning (answer, transcript)")
    return func


async def _live_chat_callable(chat: Any) -> ChatCallable:
    async def call(prompt: str) -> tuple[str, str]:
        chat.new_session()
        answer = await chat.send(prompt)
        return answer, chat.export_transcript()

    return call


async def _run_all(scenarios: list[dict[str, Any]], chat_callable: ChatCallable, judge: Judge | None) -> list[dict[str, Any]]:
    return [await run_scenario(scenario, chat_callable, judge=judge) for scenario in scenarios]


async def _main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.smoke:
        ok, report = run_golden_smoke()
        print_smoke_report(report)
        return 0 if ok else 1
    scenarios = _resolve_scenarios(args.scenario)
    if args.chat is not None:
        chat_callable = _load_custom_chat(args.chat)
        judge = Judge() if args.judge == "on" else None
        results = await _run_all(scenarios, chat_callable, judge)
    else:
        from mcp_cli.services.factory import create_chat

        async with AsyncExitStack() as stack:
            chat = await create_chat(stack)
            try:
                chat_callable = await _live_chat_callable(chat)
                judge = Judge(claude=getattr(chat, "claude", None)) if args.judge == "on" else None
                results = await _run_all(scenarios, chat_callable, judge)
            finally:
                await chat.close()
    print_summary(results)
    write_report(results, args.out)
    return 1 if any(result.get("pass") is False for result in results) else 0


def entry() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    entry()
