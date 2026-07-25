from typing import Any
import subprocess

_chat_process: subprocess.Popen | None = None
_chat: Any = None
_chat_stack: Any = None
