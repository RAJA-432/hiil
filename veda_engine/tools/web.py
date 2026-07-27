from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from pydantic import Field


async def web_search(
    query: str = Field(description="Search query"),
    max_results: int = Field(default=5, description="Number of results (1-10)", ge=1, le=10),
) -> str:
    """Search the web via DuckDuckGo. No API key required."""
    url = "https://html.duckduckgo.com/html/"
    params = {"q": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        resp = await client.post(url, data=params, headers=headers)
        resp.raise_for_status()

    snippets: list[str] = []
    # Extract result blocks from DuckDuckGo HTML
    for block in re.finditer(
        r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>.*?'
        r'<a class="result__snippet"(?:.*?)>(.*?)</a>',
        resp.text,
        re.DOTALL,
    ):
        link = block.group(1)
        title = re.sub(r"<[^>]+>", "", block.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", block.group(3)).strip()
        snippets.append(f"- [{title}]({link})\n  {snippet}")
        if len(snippets) >= max_results:
            break

    if not snippets:
        return f"No results found for '{query}'."

    return f"Web search results for '{query}':\n\n" + "\n\n".join(snippets)


_ALLOWED_SCHEMES = frozenset({"http", "https"})
_BLOCKED_HOSTS = frozenset({
    "169.254.169.254", "metadata.google.internal", "100.100.100.200",
    "localhost", "127.0.0.1", "::1", "0.0.0.0",
})


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"URL scheme '{parsed.scheme}' not allowed (only http/https)")
    host = parsed.hostname or ""
    if host in _BLOCKED_HOSTS or host.endswith(".internal"):
        raise ValueError(f"URL host '{host}' is blocked for security")
    return url


async def web_fetch(
    url: str = Field(description="URL to fetch"),
    max_chars: int = Field(default=8000, description="Max characters to return", ge=500, le=50000),
) -> str:
    """Fetch a web page and extract its readable text content."""
    url = _validate_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    text = resp.text

    # Strip <script> and <style> blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Strip all HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Decode common entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&#x27;", "'")

    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    return text or f"Could not extract any text content from {url}"
