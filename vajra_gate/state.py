import subprocess
import threading
from typing import Any

_lock = threading.Lock()
_chat_process: subprocess.Popen | None = None
_chat: Any = None
_chat_stack: Any = None
