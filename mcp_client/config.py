from __future__ import annotations

import os

from mcp import StdioServerParameters


def build_params(
    script: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> StdioServerParameters:
    """Build StdioServerParameters from a script path, handling USE_UV."""
    if os.getenv("USE_UV", "0") == "1":
        command = "uv"
        cmd_args = ["run", script]
    else:
        command = "python"
        cmd_args = [script]
    if args:
        cmd_args.extend(args)
    return StdioServerParameters(command=command, args=cmd_args, env=env)


class ServerConfig:
    """Encapsulates server command, arguments, and environment."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ):
        self.command = command
        self.args = args or []
        self.env = env

    def build_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env,
        )

    @classmethod
    def from_script(
        cls,
        script: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> ServerConfig:
        params = build_params(script, args, env)
        return cls(command=params.command, args=params.args, env=params.env)
