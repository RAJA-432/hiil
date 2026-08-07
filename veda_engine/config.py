from __future__ import annotations

import os
from pathlib import Path

_HIIL_WORKSPACE = os.environ.get("HIIL_WORKSPACE")
WORKSPACE_ROOT: Path = Path(_HIIL_WORKSPACE).resolve() if _HIIL_WORKSPACE else Path.cwd().resolve()
