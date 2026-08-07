from __future__ import annotations

"""Agent middleware package.

Contains the middleware framework (``base``) and all concrete middleware
implementations (``summarization``, ``todo``, ``code_interpreter``,
``quote_calculator``).

Only the base classes are re-exported here. Concrete implementations must be
imported from their explicit submodules (e.g.
``mcp_cli.services.agents.middleware.summarization``) to avoid circular
imports with ``mcp_cli.services.agents.models``.
"""

from mcp_cli.services.agents.middleware.base import AgentMiddleware, MiddlewarePipeline

__all__ = ["AgentMiddleware", "MiddlewarePipeline"]
