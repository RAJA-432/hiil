import subprocess
from typing import Any

_chat_process: subprocess.Popen | None = None
_chat: Any = None
_chat_stack: Any = None
