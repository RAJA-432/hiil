"""
Prompt Manager
=============

This module provides a lightweight in‑memory prompt store that the
MCP server can expose to the CLI via the `/prompt` commands.

The API mirrors the interface described in the prompt‑management
specification and is intentionally minimal so it can be extended or
persisted later.
"""

from __future__ import annotations

from typing import Any


class PromptManager:
    """Simple prompt store.

    Attributes
    ----------
    prompts:
        Dictionary mapping a prompt name to a string template.
    """

    def __init__(self) -> None:
        self.prompts: dict[str, str] = {}

    async def list_prompts(self) -> list[str]:
        """Return a list of all prompt names.

        Returns
        -------
        list[str]
            Prompt names added via :meth:`load_prompt`.
        """
        return list(self.prompts.keys())

    async def get_prompt(self, name: str, args: dict[str, str]) -> list[dict[str, Any]]:
        """Return a prompt message list with variables interpolated.

        Parameters
        ----------
        name:
            Name of the prompt.
        args:
            Dictionary of keyword arguments to substitute into the prompt
            template using :py:meth:`str.format`.

        Returns
        -------
        list[dict[str, any]]
            A list containing a single message dictionary matching the
            OpenAI Chat API format with ``role='user'``.

        Raises
        ------
        ValueError
            If the requested prompt does not exist.
        """
        if name not in self.prompts:
            raise ValueError(f"Prompt '{name}' does not exist")

        template = self.prompts[name]
        try:
            interpolated = template.format(**args)
        except KeyError as exc:
            missing = exc.args[0]
            raise ValueError(f"Missing argument '{missing}' for prompt '{name}'")
        return [{"role": "user", "content": interpolated}]

    def load_prompt(self, name: str, template: str) -> None:
        """Store a prompt template.

        Parameters
        ----------
        name:
            Prompt identifier.
        template:
            String containing ``{}`` placeholders for variable interpolation.
        """
        self.prompts[name] = template


# Global prompt manager accessible by the server and CLI.
prompt_manager = PromptManager()
