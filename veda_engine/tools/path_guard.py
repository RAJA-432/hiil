"""Path-traversal protection (re-exported from the shared ``hiil_common``).

Kept as a module so existing imports (``veda_engine.tools.path_guard``) keep
working unchanged.
"""

from __future__ import annotations

from hiil_common.utils.paths import canonicalize, is_safe_path, safe_relative, validate_path

__all__ = ["canonicalize", "is_safe_path", "safe_relative", "validate_path"]
