# Everything Server

Test/debug MCP server via `@modelcontextprotocol/server-everything`. Provides echo, calculator, LLM sample, and utility tools.

## Tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `echo` | `(message: str) -> str` | Echo back the input message |
| `add` | `(a: int, b: int) -> int` | Add two integers |
| `longRunningOperation` | `(duration: int) -> str` | Block for `duration` seconds, then return |
| `sampleLLM` | `(prompt: str) -> str` | Mock LLM call; returns a placeholder response |
| `getTimezoneInfo` | `(timezone: str) -> str` | Return info about a timezone |
| `printEnv` | `() -> str` | Print environment variables (for debugging) |
| `getWeather` | `(city: str) -> str` | Return mock weather for a city |
| `getResourceList` | `() -> list` | List all available resources |
| `getResourceContents` | `() -> list` | Get contents of all resources |
| `getSubscriptionList` | `() -> list` | List all available subscriptions |

## Prompts

| Prompt | Description |
|--------|-------------|
| `sample_prompt` | A sample prompt demonstrating MCP prompt functionality |
