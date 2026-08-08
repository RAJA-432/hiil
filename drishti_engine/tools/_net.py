"""SSRF-guarded URL validation for Drishti Engine network tools.

Re-exported from ``hiil_common.utils.ssrf`` (which unifies the validation
logic from ``veda_engine.tools.web`` and the original ``_net`` module).
Kept as a module so existing imports keep working unchanged.
"""

from __future__ import annotations

from hiil_common.utils.ssrf import validate_public_http_url

__all__ = ["validate_public_http_url"]
