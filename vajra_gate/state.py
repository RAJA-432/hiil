import subprocess
import threading
from typing import Any

_lock = threading.Lock()
_chat_process: subprocess.Popen | None = None
_pool: Any = None
_chat: Any = None
_chat_stack: Any = None
_prewarm_task: Any | None = None
_PREWARM_PENDING: Any | None = None


def _get_pool() -> Any:
    global _pool
    if _pool is None:
        from vajra_gate.chat_pool import ChatPool
        _pool = ChatPool()
    return _pool
