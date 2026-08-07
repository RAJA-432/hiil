from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from mcp_cli.commands.skill_cmds import handle_cmd_skill


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def skills_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "skills").mkdir()
    return tmp_path


def test_create_skill(skills_cwd):
    ok, out = _run(handle_cmd_skill("create my-skill A custom skill", None))
    assert ok
    assert "created at skills" in out
    skill_md = Path("skills/my-skill/SKILL.md")
    assert skill_md.exists()
    content = skill_md.read_text(encoding="utf-8")
    assert "# My Skill" in content
    assert "A custom skill" in content


def test_create_duplicate_skill(skills_cwd):
    _run(handle_cmd_skill("create my-skill A", None))
    ok, out = _run(handle_cmd_skill("create my-skill B", None))
    assert "already exists" in out


def test_create_invalid_name(skills_cwd):
    ok, out = _run(handle_cmd_skill("create bad.name stuff", None))
    assert "Invalid skill name" in out


def test_list_empty(skills_cwd):
    ok, out = _run(handle_cmd_skill("list", None))
    assert out == "No skills found."


def test_list_skills(skills_cwd):
    (Path("skills") / "one").mkdir()
    (Path("skills") / "one" / "SKILL.md").write_text("# One\n", encoding="utf-8")
    ok, out = _run(handle_cmd_skill("list", None))
    assert "one" in out


def test_show_skill(skills_cwd):
    (Path("skills") / "one").mkdir()
    (Path("skills") / "one" / "SKILL.md").write_text("# One\n", encoding="utf-8")
    ok, out = _run(handle_cmd_skill("show one", None))
    assert "# One" in out


def test_show_missing_skill(skills_cwd):
    ok, out = _run(handle_cmd_skill("show nope", None))
    assert "not found" in out


def test_show_requires_name(skills_cwd):
    ok, out = _run(handle_cmd_skill("show", None))
    assert out == "Usage: /skill show <name>"


def test_delete_requires_name(skills_cwd):
    ok, out = _run(handle_cmd_skill("delete", None))
    assert out == "Usage: /skill delete <name>"


def test_delete_skill(skills_cwd):
    (Path("skills") / "one").mkdir()
    (Path("skills") / "one" / "SKILL.md").write_text("# One\n", encoding="utf-8")
    ok, out = _run(handle_cmd_skill("delete one", None))
    assert "deleted" in out
    assert not (Path("skills") / "one").exists()


def test_delete_missing_skill(skills_cwd):
    ok, out = _run(handle_cmd_skill("delete nope", None))
    assert "not found" in out


def test_traversal_blocked(skills_cwd):
    ok, out = _run(handle_cmd_skill("create ../evil stuff", None))
    assert "Invalid skill name" in out
    assert not (Path("..") / "evil").exists()


def test_usage_fallback(skills_cwd):
    ok, out = _run(handle_cmd_skill("bogus", None))
    assert out.startswith("Usage: /skill")
