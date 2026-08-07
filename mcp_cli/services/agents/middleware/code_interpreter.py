from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from mcp_cli.services.agents.middleware.base import AgentMiddleware
from mcp_cli.services.agents.models import register_middleware

_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "execute_python",
        "description": (
            "Write and execute Python code in an isolated subprocess. "
            "Use this for exact arithmetic, data processing, string manipulation, "
            "or any computation that needs a programming language. "
            "The code runs in a restricted environment with no network or "
            "filesystem access beyond a scratch directory. "
            "Print output with ``print()`` to see it in the result."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute. Use print() for output.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds (default 15, max 60).",
                    "default": 15,
                },
            },
            "required": ["code"],
        },
    },
}

_SAFE_MODULES: set[str] = {
    "math", "statistics", "random", "datetime", "itertools", "collections",
    "functools", "operator", "json", "re", "string", "decimal", "fractions",
    "pathlib", "typing", "enum", "dataclasses", "uuid", "hashlib", "bisect",
    "heapq", "base64", "textwrap",
    "time", "traceback",
    # Transitive deps needed by safe modules
    "_io", "io", "abc", "os", "os.path", "errno", "fnmatch", "tokenize",
    "locale", "codecs", "encodings", "genericpath", "stat", "warnings",
    "importlib", "importlib.metadata", "importlib._bootstrap",
    "importlib._bootstrap_external", "ast", "weakref", "atexit",
    "_collections_abc", "_functools",
}

def _build_wrapper_script(code: str, timeout: int, subagents: bool = True) -> str:
    sanitized = code.replace("\r\n", "\n")
    _code_repr = repr(sanitized)
    _allowed_repr = repr(sorted(_SAFE_MODULES))
    _preamble_code = (
        "import math, statistics, random, datetime, itertools, collections\n"
        "import functools, operator, json, re, string\n"
        "from decimal import Decimal\n"
        "from fractions import Fraction\n"
        "from pathlib import Path\n"
        "import traceback\n"
    )
    if subagents:
        _task_globals = textwrap.dedent(
            """\
            def task(subagent_type="general-purpose", description="", **kwargs):
                request = {"op": "task", "subagent_type": subagent_type, "description": description, "kwargs": kwargs}
                print("__HIIL_TASK__" + json.dumps(request), flush=True)
                line = sys.stdin.readline()
                if not line:
                    return "[error] task() bridge closed"
                return json.loads(line).get("result", "[error] empty task result")

            def task_parallel(delegations=None):
                if not delegations:
                    return "[error] task_parallel requires a list of delegations"
                request = {"op": "task_parallel", "delegations": delegations}
                print("__HIIL_TASK__" + json.dumps(request), flush=True)
                line = sys.stdin.readline()
                if not line:
                    return "[error] task_parallel() bridge closed"
                return json.loads(line).get("result", "[error] empty task_parallel result")

            """
        )
        _ns_line = (
            "_ns = {\"__builtins__\": _safe_builtins, "
            "\"task\": task, \"task_parallel\": task_parallel}\n"
        )
    else:
        _task_globals = ""
        _ns_line = "_ns = {\"__builtins__\": _safe_builtins}\n"
    return textwrap.dedent(f"""\
import os, sys, threading

{_preamble_code}

def _die():
    print("[timeout] Code execution exceeded {timeout}s", flush=True)
    os._exit(1)

_timer = threading.Timer({timeout}, _die)
_timer.daemon = True
_timer.start()

_safe_builtins = {{}}
_safe_builtins.update(
    (k, v) for k, v in vars(__builtins__).items()
    if k in {{
        "abs", "all", "any", "bool", "chr", "dict", "divmod", "enumerate",
        "filter", "float", "format", "frozenset", "hash", "hex", "id", "int",
        "isinstance", "issubclass", "iter", "len", "list", "map", "max", "min",
        "next", "object", "oct", "ord", "pow", "print", "range", "repr",
        "reversed", "round", "set", "slice", "sorted", "str", "sum", "tuple",
        "type", "zip",
        "True", "False", "None",
        "__import__",
    }}
)

_SAFE_MODULES = set({_allowed_repr})
import builtins as _builtins
_orig_import = _builtins.__import__
def _safe_import(name, *args, **kwargs):
    top = name.split(".")[0]
    if top not in _SAFE_MODULES and name not in _SAFE_MODULES:
        raise ImportError(f"Module {{name}} not allowed")
    return _orig_import(name, *args, **kwargs)
_builtins.__import__ = _safe_import
_safe_builtins["__import__"] = _safe_import

{_task_globals}
{_ns_line}

try:
    exec({_code_repr}, _ns)
except SystemExit:
    raise
except BaseException:
    traceback.print_exc()
""")

@register_middleware
class CodeInterpreterMiddleware(AgentMiddleware):
    """Adds an ``execute_python`` tool that runs Python code in a subprocess.

    The code runs in a fresh Python interpreter with:
    * Restricted builtins (no open(), exec(), eval(), __import__ of dangerous modules)
    * Whitelisted import set (math, statistics, datetime, itertools, etc.)
    * SIGALRM timeout
    * No network or arbitrary filesystem access

    Usage in agent config::

        middleware=[CodeInterpreterMiddleware(timeout=30)]
    """

    def __init__(self, timeout: int = 15, subagents: bool = True, chat: Any = None):
        self._default_timeout = max(1, min(timeout, 60))
        self._subagents = subagents
        self._chat = chat

    # ------------------------------------------------------------------
    # Middleware API
    # ------------------------------------------------------------------

    def before_run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self._subagents:
            return messages
        addendum = (
            "\n\n## Orchestration\n"
            'If the request uses the word "workflow", write orchestration code '
            "that dispatches subagents with task() and assembles their results, "
            "instead of delegating one at a time."
        )
        if messages and messages[0].get("role") == "system":
            existing = messages[0].get("content", "")
            messages[0]["content"] = existing + addendum
        else:
            messages.insert(0, {"role": "system", "content": addendum.lstrip("\n")})
        return messages

    def get_extra_tools(self) -> list[dict[str, Any]]:
        return [_TOOL_DEFINITION]

    async def handle_tool(self, name: str, args: dict[str, Any]) -> tuple[bool, str | None]:
        if name != "execute_python":
            return (False, None)
        code = args.get("code", "")
        timeout = min(args.get("timeout", self._default_timeout), 60)
        result = await self._run_in_subprocess(code, timeout)
        return (True, result)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _run_in_subprocess(self, code: str, timeout: int) -> str:
        wrapper = _build_wrapper_script(code, timeout, subagents=self._subagents)

        with tempfile.TemporaryDirectory(prefix="hiil_code_") as tmpdir:
            script_path = Path(tmpdir) / "_execute.py"
            await asyncio.to_thread(
                lambda: script_path.write_text(wrapper, encoding="utf-8")
            )

            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(script_path),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmpdir,
                    env={"PYTHONUNBUFFERED": "1"},
                )

                out_lines: list[str] = []

                async def _pump() -> None:
                    while True:
                        line = await proc.stdout.readline()
                        if not line:
                            break
                        text = line.decode("utf-8", errors="replace").rstrip("\n")
                        if text.startswith("__HIIL_TASK__"):
                            payload = text[len("__HIIL_TASK__"):]
                            try:
                                request = json.loads(payload)
                            except json.JSONDecodeError:
                                result = "[error] malformed task request"
                            else:
                                result = await self._dispatch_subagent(request)
                            if proc.stdin is not None:
                                try:
                                    proc.stdin.write(
                                        (json.dumps({"result": result}) + "\n").encode("utf-8")
                                    )
                                    await proc.stdin.drain()
                                except (BrokenPipeError, ConnectionResetError):
                                    pass
                        else:
                            out_lines.append(text)

                try:
                    await asyncio.wait_for(_pump(), timeout=timeout + 5)
                except TimeoutError:
                    proc.kill()
                    await proc.wait()
                    return f"[timeout] Code execution exceeded {timeout}s"

                if proc.stdin is not None:
                    proc.stdin.close()
                await proc.wait()
                err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()

                out = "\n".join(out_lines).strip()

                parts: list[str] = []
                if out:
                    parts.append(out)
                if err:
                    parts.append(f"[stderr]\n{err}")
                if proc.returncode and proc.returncode != 0 and not err:
                    parts.append(f"[exit code {proc.returncode}]")

                return "\n".join(parts) if parts else "(no output)"
            except FileNotFoundError:
                return f"[error] Python interpreter not found: {sys.executable}"
            except Exception as exc:
                return f"[error] {exc}"

    async def _dispatch_subagent(self, request: dict) -> str:
        from mcp_cli.services.builtin_tools import (
            _MAX_DELEGATION_DEPTH,
            _delegate_parallel,
            _delegate_task,
            _delegation_depth,
            _push_depth,
        )

        if self._chat is None:
            return "[error] task() requires a chat reference"

        op = request.get("op")
        if op == "task":
            if _delegation_depth.get() >= _MAX_DELEGATION_DEPTH:
                return "[error] delegation depth exceeded."
            args = {
                "agent": request.get("subagent_type", ""),
                "task": request.get("description", ""),
                **request.get("kwargs", {}),
            }
            async with _push_depth():
                return await _delegate_task(self._chat, args)
        if op == "task_parallel":
            if _delegation_depth.get() >= _MAX_DELEGATION_DEPTH:
                return "[error] delegation depth exceeded."
            async with _push_depth():
                return await _delegate_parallel(
                    self._chat, {"delegations": request.get("delegations", [])}
                )
        return "[error] unknown task op"
