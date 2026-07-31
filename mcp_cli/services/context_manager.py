from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from mcp_cli.services.logging import get_logger
from mcp_cli.services.usage import count_tokens

if TYPE_CHECKING:
    pass

logger = get_logger("context_manager")


class ContextManager:
    def __init__(self, claude: Any, vector_store: Any, max_context_tokens: int = 200_000):
        self.claude = claude
        self.vector_store: Any = vector_store
        self.max_context_tokens = max_context_tokens
        self.compact_count = 0

    def message_tokens(self, messages: list[dict[str, Any]]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += count_tokens(content, self.claude.model)
        return total

    def trim(self, messages: list[dict[str, Any]], tools_token_count: int = 0) -> list[dict[str, Any]]:
        budget = self.max_context_tokens - tools_token_count
        if budget <= 0:
            return messages[-2:] if len(messages) > 2 else messages

        counts = [count_tokens(m.get("content", ""), self.claude.model) for m in messages]
        total_tokens = sum(counts)
        if total_tokens <= budget:
            return messages

        self.compact_count += 1
        summary_text = f"[compacted #{self.compact_count}: msgs trimmed]"
        target = budget - count_tokens(summary_text, self.claude.model)

        suffix = [0] * (len(messages) + 1)
        for i in range(len(messages)):
            suffix[i + 1] = suffix[i] + counts[len(messages) - 1 - i]

        lo, hi = 2, len(messages)
        best = 2
        while lo <= hi:
            mid = (lo + hi) // 2
            if suffix[mid] <= target:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1

        trimmed = messages[-best:]
        trimmed_counts = counts[len(messages) - best:]
        total_tokens = sum(trimmed_counts)

        truncated = False
        for _ in range(100):
            if total_tokens <= target:
                break
            candidates = [
                m for m in trimmed
                if m.get("role") in ("user",)
                or (m.get("role") == "assistant" and not m.get("tool_calls"))
            ]
            if not candidates:
                candidates = trimmed
            largest = max(candidates, key=lambda m: len(m.get("content", "")) if isinstance(m.get("content", ""), str) else len(json.dumps(m.get("content", ""))))
            c = largest.get("content", "")
            if not c:
                if len(trimmed) > 2:
                    total_tokens -= trimmed_counts[0]
                    trimmed.pop(0)
                    trimmed_counts.pop(0)
                break
            if isinstance(c, list):
                if len(trimmed) > 2:
                    total_tokens -= trimmed_counts[0]
                    trimmed.pop(0)
                    trimmed_counts.pop(0)
                break
            c_json = json.dumps(c)
            c_tokens = count_tokens(c_json, self.claude.model)
            excess = total_tokens - target
            trim_frac = max(0.05, min(0.5, excess * 1.2 / max(1, c_tokens)))
            target_tokens_c = max(1, int(c_tokens * (1 - trim_frac)))
            char_ratio = len(c) / max(1, c_tokens)
            target_chars = max(1, int(target_tokens_c * char_ratio))
            if target_chars >= len(c):
                break
            truncated = True
            trunc_content = c[:target_chars]
            last_space = trunc_content.rfind(" ")
            if last_space > 0:
                trunc_content = trunc_content[:last_space]
            largest["content"] = trunc_content
            new_json = json.dumps(largest["content"])
            new_tokens = count_tokens(new_json, self.claude.model)
            total_tokens += new_tokens - c_tokens
            for i, m in enumerate(trimmed):
                if m is largest:
                    trimmed_counts[i] = new_tokens
                    break

        summary_text = f"[compacted #{self.compact_count}: kept {len(trimmed)} of {len(messages)} msgs]"
        result = trimmed
        result.insert(0, {"role": "system", "content": summary_text})

        if truncated:
            cur_counts = [count_tokens(m.get("content", ""), self.claude.model) for m in result]
        else:
            cur_counts = [count_tokens(summary_text, self.claude.model)] + trimmed_counts
        total_tokens = sum(cur_counts)

        if total_tokens > budget:
            while len(result) > 2 and total_tokens > budget:
                total_tokens -= cur_counts[1]
                result.pop(1)
                cur_counts.pop(1)
            if total_tokens > budget:
                last = result[-1]
                c = last.get("content", "")
                if isinstance(c, str) and c:
                    half = len(c) // 2
                    last["content"] = c[:half]
        return result

    async def fetch_model_context(self, model: str) -> int | None:
        base_url = getattr(self.claude, "base_url", None)
        if not isinstance(base_url, str):
            return 8192
        api_key = getattr(self.claude, "api_key", None)
        if not isinstance(api_key, str):
            api_key = ""
        url = f"{base_url.rstrip('/')}/models"
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    for m in resp.json().get("data", []):
                        if m.get("id") == model:
                            ctx = (
                                m.get("context_length")
                                or m.get("max_context")
                                or m.get("max_context_window_tokens")
                                or m.get("max_total_tokens")
                            )
                            if ctx:
                                return int(ctx)
        except Exception:
            logger.warning("Failed to fetch model context from API, using fallback")
        return 8192

    async def auto_index(self, text: str, namespace: str = "messages") -> None:
        if not text or len(text) < 20:
            return
        existing = await self.vector_store.async_list_keys(namespace)
        key = f"msg_{len(existing)}"
        emb = await self.claude.embed(text[:2048])
        if emb:
            await self.vector_store.async_index(namespace, key, text[:2048], emb)

    async def semantic_search(self, query: str, namespace: str = "messages", limit: int = 5) -> list[dict[str, Any]]:
        emb = await self.claude.embed(query)
        if not emb:
            return []
        return await self.vector_store.async_search(emb, namespace=namespace, limit=limit)
