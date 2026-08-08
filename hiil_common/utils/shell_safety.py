"""Deny-by-verb shell-command safety shared by H.I.I.L. servers.

Pure functions: the workspace root is passed explicitly rather than read from
a global, so the same logic can back every server. ``veda_engine.tools.shell_safety``
re-exports these with the veda config binding preserved.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from hiil_common.utils.paths import is_safe_path

_DENIED_PATTERNS = re.compile(
    r"\brm\b[^|;&\n]*\s+-+[a-z]*r[a-z]*f[a-z]*\b[^|;&\n]*\s*[/\\*]"      # rm -rf /, rm -rf /*
    r"|\bmkfs\b"                                                            # filesystem creation
    r"|\bdd\b[^\n]*\bif="                                                   # dd if=<device> (disk wipe)
    r"|>\s*[/\\]dev[/\\]sd"                                                 # > /dev/sdX (disk overwrite)
    r"|\bformat\b\s+[a-zA-Z]:"                                              # format C:
    r"|:\(\)\s*\{|:[^\n]*\{\s*\|[^\n]*\}\s*&"                               # fork bombs
    r"|\b(shutdown|reboot|poweroff|halt|init)\b"
    r"|\bchmod\b[^\n]*\s+777\s+[/\\]"                                       # chmod 777 /
    r"|\b(curl|wget)\b[^\n]*\|\s*\bsh\b"                                    # curl|sh / wget|sh
    r"|\b(del|rd|rmdir)\b\s+[/\\]\s*s\b",                                   # del /s /f, rd /s /q
    re.IGNORECASE,
)

# Hard deny-by-verb list.  The command is tokenized with ``shlex`` and every
# token's executable name is checked against this list, so flags/targets are
# irrelevant: ``rm -rf /``, ``rd /q /s .`` and ``del /s *`` are all denied.
_DENIED_VERBS = frozenset({
    # File deletion / destruction
    "rm", "rmdir", "del", "erase", "rd", "deltree", "rdtree", "shred",
    # Disk / filesystem
    "format", "mkfs", "mkfs.ext4", "mkfs.btrfs", "mkswap", "wipefs",
    "fdisk", "parted", "sfdisk", "dd",
    # Power / reboot
    "shutdown", "reboot", "poweroff", "halt", "init", "telinit",
    # PowerShell destructive cmdlets
    "remove-item", "del-item", "clear-recyclebin",
})


def executable_name(token: str) -> str:
    """Strip quotes, directory prefixes and extensions from a token."""
    name = token.strip()
    if len(name) >= 2 and name[0] == name[-1] and name[0] in "\"'":
        name = name[1:-1]
    name = name.split("/")[-1].split("\\")[-1].lower()
    for ext in (".exe", ".com", ".bat", ".cmd", ".ps1"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    return name


def separator_index(command: str) -> int:
    """Index of the first shell-level command separator, or -1.

    Quote-aware, so ``;``/``&``/``|`` inside quotes (e.g.
    ``python -c "a;b"``) are not treated as separators.
    """
    i, n, quote = 0, len(command), ""
    while i < n:
        ch = command[i]
        if quote:
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            continue
        if ch in ";&|\n":
            return i
        i += 1
    return -1


def check_cd(tokens: list[str], cwd: Path, workspace_root: Path) -> str | None:
    """Reject ``cd`` to absolute paths or targets that escape the workspace."""
    for i, tok in enumerate(tokens):
        if executable_name(tok) != "cd":
            continue
        if i + 1 >= len(tokens):
            continue
        dest = tokens[i + 1].strip("\"'")
        if not dest:
            continue
        if Path(dest).is_absolute():
            return f"cd to absolute path '{dest}' is not allowed"
        if not is_safe_path((cwd / dest).resolve(), workspace_root):
            return f"cd to '{dest}' escapes the workspace root"
    return None


def check_redirects(command: str, cwd: Path, workspace_root: Path) -> str | None:
    """Reject ``>``/``>>`` redirects whose target escapes the workspace root."""
    i, n, quote = 0, len(command), ""
    while i < n:
        ch = command[i]
        if quote:
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            continue
        if ch != ">":
            i += 1
            continue
        j = i + 1
        if j < n and command[j] == ">":
            j += 1
        while j < n and command[j] in " \t":
            j += 1
        target = ""
        q = ""
        while j < n:
            c2 = command[j]
            if q:
                target += c2
                if c2 == q:
                    q = ""
            elif c2 in "\"'":
                q = c2
                target += c2
            elif c2 in " \t;|&<>":
                break
            else:
                target += c2
            j += 1
        target = target.strip().strip("\"'")
        if target and (
            Path(target).is_absolute()
            or not is_safe_path((cwd / target).resolve(), workspace_root)
        ):
            return f"redirect target '{target}' escapes the workspace root"
        i = j
    return None


def deny_reason(command: str, cwd: Path, workspace_root: Path) -> str | None:
    """Return a reason to deny *command*, or ``None`` if it may run."""
    if _DENIED_PATTERNS.search(command):
        return "command matches a blocked pattern"
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        return "command has unbalanced quotes"
    for tok in tokens:
        if executable_name(tok) in _DENIED_VERBS:
            return f"destructive command '{executable_name(tok)}' is blocked"
    if separator_index(command) != -1:
        return "command chaining/separators are not allowed"
    cd_err = check_cd(tokens, cwd, workspace_root)
    if cd_err:
        return cd_err
    redirect_err = check_redirects(command, cwd, workspace_root)
    if redirect_err:
        return redirect_err
    return None
