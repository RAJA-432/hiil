from __future__ import annotations

import json
from pathlib import Path

from mcp_cli.services.history import ChatHistoryManager
from scripts.export_training_data import (
    build_examples,
    export_sessions,
    read_sessions,
    write_examples,
    write_split,
)


def _make_history(db_path: Path) -> ChatHistoryManager:
    mgr = ChatHistoryManager(str(db_path), max_sessions=50)
    mgr.save_message("sess_a", "user", "What is the weather?")
    mgr.save_message("sess_a", "assistant", "Let me check.")
    mgr.save_message("sess_a", "tool", "tool result: 21 degrees")
    mgr.save_message("sess_a", "assistant", "The temperature is 21 degrees.")
    mgr.save_message("sess_b", "user", "Hello")
    mgr.save_message("sess_b", "assistant", "Hi there")
    mgr.save_message("sess_c", "user", "single message session")
    return mgr


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class TestExport:
    def test_exports_one_line_per_session_preserving_order_and_roles(self, tmp_path: Path) -> None:
        mgr = _make_history(tmp_path / "history.db")
        try:
            out = tmp_path / "out.jsonl"
            write_examples(export_sessions(str(tmp_path / "history.db")), out)
            lines = _read_jsonl(out)
            assert len(lines) == 2
            assert [line["messages"][0]["content"] for line in lines] == [
                "What is the weather?",
                "Hello",
            ]
            sess_a = lines[0]["messages"]
            assert [m["role"] for m in sess_a] == ["user", "assistant", "tool", "assistant"]
            assert [m["content"] for m in sess_a] == [
                "What is the weather?",
                "Let me check.",
                "tool result: 21 degrees",
                "The temperature is 21 degrees.",
            ]
            assert all("id" not in m for m in sess_a)
        finally:
            mgr.close()

    def test_tool_messages_carry_tool_call_id(self, tmp_path: Path) -> None:
        mgr = _make_history(tmp_path / "history.db")
        try:
            out = tmp_path / "out.jsonl"
            write_examples(export_sessions(str(tmp_path / "history.db")), out)
            lines = _read_jsonl(out)
            tool_msg = lines[0]["messages"][2]
            assert tool_msg["role"] == "tool"
            assert tool_msg["tool_call_id"]
            user_msg = lines[0]["messages"][0]
            assert "tool_call_id" not in user_msg
        finally:
            mgr.close()

    def test_min_messages_filters_sessions(self, tmp_path: Path) -> None:
        mgr = _make_history(tmp_path / "history.db")
        try:
            assert len(export_sessions(str(tmp_path / "history.db"), min_messages=1)) == 3
            assert len(export_sessions(str(tmp_path / "history.db"), min_messages=2)) == 2
            assert len(export_sessions(str(tmp_path / "history.db"), min_messages=3)) == 1
            only = export_sessions(str(tmp_path / "history.db"), min_messages=3)
            assert only[0]["messages"][0]["content"] == "What is the weather?"
        finally:
            mgr.close()

    def test_include_tool_calls_extracts_from_json_content(self, tmp_path: Path) -> None:
        mgr = ChatHistoryManager(str(tmp_path / "history.db"), max_sessions=50)
        try:
            mgr.save_message("sess", "user", "hi")
            mgr.save_message(
                "sess",
                "assistant",
                '{"tool_calls": [{"id": "call_1", "type": "function", '
                '"function": {"name": "get_current_weather", "arguments": "{\\"city\\": \\"Tokyo\\"}"}}]}',
            )
            mgr.save_message("sess", "tool", '{"tool_call_id": "call_1", "content": "21"}')
            mgr.save_message("sess", "assistant", "It is 21 degrees.")
            with_calls = export_sessions(str(tmp_path / "history.db"), include_tool_calls=True)
            without = export_sessions(str(tmp_path / "history.db"))
            assistant_msg = with_calls[0]["messages"][1]
            assert assistant_msg["tool_calls"][0]["id"] == "call_1"
            assert "tool_calls" not in without[0]["messages"][1]
            tool_msg = with_calls[0]["messages"][2]
            assert tool_msg["tool_call_id"] == "call_1"
        finally:
            mgr.close()

    def test_split_writes_train_and_val_with_counts(self, tmp_path: Path) -> None:
        mgr = _make_history(tmp_path / "history.db")
        try:
            examples = export_sessions(str(tmp_path / "history.db"))
            assert len(examples) == 2
            train_path, val_path = write_split(examples, tmp_path / "training_data.jsonl", train_ratio=0.5, seed=0)
            train = _read_jsonl(train_path)
            val = _read_jsonl(val_path)
            assert len(train) == 1
            assert len(val) == 1
            contents = {line["messages"][0]["content"] for line in train + val}
            assert contents == {"What is the weather?", "Hello"}
            assert train_path.name == "training_data.train.jsonl"
            assert val_path.name == "training_data.val.jsonl"
        finally:
            mgr.close()

    def test_split_is_deterministic_for_seed(self, tmp_path: Path) -> None:
        mgr = _make_history(tmp_path / "history.db")
        try:
            examples = export_sessions(str(tmp_path / "history.db"))
            a_train, a_val = write_split(examples, tmp_path / "a.jsonl", train_ratio=0.5, seed=7)
            b_train, b_val = write_split(examples, tmp_path / "b.jsonl", train_ratio=0.5, seed=7)
            assert a_train.read_text(encoding="utf-8") == b_train.read_text(encoding="utf-8")
            assert a_val.read_text(encoding="utf-8") == b_val.read_text(encoding="utf-8")
        finally:
            mgr.close()


class TestReadSessions:
    def test_sessions_ordered_by_first_message(self, tmp_path: Path) -> None:
        mgr = _make_history(tmp_path / "history.db")
        try:
            sessions = read_sessions(str(tmp_path / "history.db"))
            assert [sid for sid, _ in sessions] == ["sess_a", "sess_b"]
            sess_a_messages = sessions[0][1]
            assert [m["id"] for m in sess_a_messages] == sorted(m["id"] for m in sess_a_messages)
        finally:
            mgr.close()

    def test_missing_db_raises(self, tmp_path: Path) -> None:
        import pytest

        with pytest.raises(FileNotFoundError):
            read_sessions(str(tmp_path / "nope.db"))


class TestMain:
    def test_missing_db_returns_nonzero(self, tmp_path: Path) -> None:
        from scripts.export_training_data import main as export_main

        code = export_main(["--db", str(tmp_path / "nope.db"), "--out", str(tmp_path / "out.jsonl")])
        assert code == 2

    def test_main_writes_single_file(self, tmp_path: Path, capsys) -> None:
        from scripts.export_training_data import main as export_main

        mgr = _make_history(tmp_path / "history.db")
        try:
            out = tmp_path / "training_data.jsonl"
            code = export_main(["--db", str(tmp_path / "history.db"), "--out", str(out)])
            assert code == 0
            assert out.exists()
            assert len(_read_jsonl(out)) == 2
            assert "2 sessions" in capsys.readouterr().out
        finally:
            mgr.close()

    def test_main_split_flag(self, tmp_path: Path) -> None:
        from scripts.export_training_data import main as export_main

        mgr = _make_history(tmp_path / "history.db")
        try:
            base = tmp_path / "training_data.jsonl"
            code = export_main(
                ["--db", str(tmp_path / "history.db"), "--out", str(base), "--split", "--train-ratio", "0.5"]
            )
            assert code == 0
            assert (tmp_path / "training_data.train.jsonl").exists()
            assert (tmp_path / "training_data.val.jsonl").exists()
            assert not base.exists()
        finally:
            mgr.close()


def test_build_examples_passthrough() -> None:
    messages = [
        {"id": 1, "role": "user", "content": "q", "timestamp": "t1"},
        {"id": 2, "role": "assistant", "content": "a", "timestamp": "t2"},
    ]
    examples = build_examples([("s1", messages)])
    assert examples == [{"messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]}]
