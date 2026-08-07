from __future__ import annotations

from unittest.mock import AsyncMock

from veda_engine.tools.roots import is_path_allowed


class _FakeSession:
    def __init__(self, roots_result=None, exc=None):
        self._roots_result = roots_result
        self._exc = exc
        self.list_roots = AsyncMock(side_effect=self._exc or (lambda: self._roots_result))

    async def list_roots(self):
        if self._exc:
            raise self._exc
        return self._roots_result


class _FakeContext:
    def __init__(self, session):
        self.session = session


class _Roots:
    def __init__(self, roots):
        self.roots = roots


class _Root:
    def __init__(self, uri):
        self.uri = uri


async def test_allowed_within_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("x", encoding="utf-8")
    ctx = _FakeContext(_FakeSession(roots_result=_Roots([_Root(f"file://{root}")])))
    assert await is_path_allowed(root / "a.txt", ctx) is True


async def test_denied_outside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "other"
    outside.mkdir()
    (outside / "a.txt").write_text("x", encoding="utf-8")
    ctx = _FakeContext(_FakeSession(roots_result=_Roots([_Root(f"file://{root}")])))
    assert await is_path_allowed(outside / "a.txt", ctx) is False


async def test_fail_closed_when_list_roots_raises(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("x", encoding="utf-8")
    ctx = _FakeContext(_FakeSession(exc=RuntimeError("boom")))
    assert await is_path_allowed(root / "a.txt", ctx) is False
