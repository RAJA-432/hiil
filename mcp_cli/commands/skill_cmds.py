from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

_SKILLS_DIR = Path("skills")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

_SKILL_SKELETON = """# {Title}

{Description}

## Tools

| Tool | Signature | Description |
|------|-----------|-------------|

## Usage

- Describe when to use this skill and expected inputs/outputs.
"""


def _safe_skill_path(name: str) -> Path | None:
    if not _NAME_RE.match(name):
        return None
    path = _SKILLS_DIR / name
    base = _SKILLS_DIR.resolve()
    if base not in path.resolve().parents and path.resolve() != base:
        return None
    return path


def _title_from_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


async def _confirm(app, question: str) -> bool:
    if app is None or app._session is None:
        return True
    try:
        answer = await app._session.prompt_async(question)
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().lower() in ("y", "yes")


async def _skill_create(rest: str, app) -> str:
    parts = rest.strip().split(maxsplit=1)
    name = parts[0].lower() if parts else ""
    description = parts[1].strip() if len(parts) > 1 else f"Custom skill '{name}'."
    if not name:
        return "Usage: /skill create <name> [description]"
    path = _safe_skill_path(name)
    if path is None:
        return f"Invalid skill name '{name}'. Use lowercase letters, digits, and dashes."
    if (path / "SKILL.md").exists():
        return f"Skill '{name}' already exists."
    await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
    content = _SKILL_SKELETON.format(
        Title=_title_from_name(name),
        Description=description,
    )
    await asyncio.to_thread(
        (path / "SKILL.md").write_text, content, encoding="utf-8",
    )
    return f"Skill '{name}' created at {path / 'SKILL.md'}."


async def _skill_list() -> str:
    if not _SKILLS_DIR.exists():
        return "No skills found."
    entries = sorted(
        d.name for d in _SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )
    if not entries:
        return "No skills found."
    return "Skills:\n" + "\n".join(f"  {name}" for name in entries)


async def _skill_show(rest: str) -> str:
    name = rest.strip().lower()
    if not name:
        return "Usage: /skill show <name>"
    path = _safe_skill_path(name)
    if path is None or not (path / "SKILL.md").exists():
        return f"Skill '{name}' not found."
    content = await asyncio.to_thread(
        (path / "SKILL.md").read_text, encoding="utf-8",
    )
    return f"--- {path / 'SKILL.md'} ---\n{content}"


async def _skill_delete(rest: str, app) -> str:
    name = rest.strip().lower()
    if not name:
        return "Usage: /skill delete <name>"
    path = _safe_skill_path(name)
    if path is None or not path.exists():
        return f"Skill '{name}' not found."
    if not await _confirm(app, f"Delete skill '{name}'? (y/n): "):
        return "Delete cancelled by user."
    await asyncio.to_thread(shutil.rmtree, path)
    return f"Skill '{name}' deleted."


async def handle_cmd_skill(rest: str, chat, app=None) -> tuple[bool, str]:
    sub = rest.strip().split(maxsplit=1)
    action = sub[0].lower() if sub else "list"
    arg = sub[1] if len(sub) > 1 else ""
    if action == "create":
        return True, await _skill_create(arg, app)
    if action == "list":
        return True, await _skill_list()
    if action == "show":
        return True, await _skill_show(arg)
    if action == "delete":
        return True, await _skill_delete(arg, app)
    return True, "Usage: /skill create <name> [desc] | list | show <name> | delete <name>"
