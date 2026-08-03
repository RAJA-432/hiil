from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
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
    "localhost", "127.0.0.1", "::1", "0.0.0.0",  # noqa: S104 -- blocklist, not bind address
})
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _resolve_blocks(host: str) -> tuple[str, ...]:
    """Resolve a hostname to all of its IP addresses, raising on resolution failure."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValueError(f"Could not resolve URL host '{host}'") from None
    return tuple(info[4][0] for info in infos)


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"URL scheme '{parsed.scheme}' not allowed (only http/https)")
    host = parsed.hostname or ""
    if host in _BLOCKED_HOSTS or host.endswith(".internal"):
        raise ValueError(f"URL host '{host}' is blocked for security")
    try:
        candidates: list[str] = [ipaddress.ip_address(host).compressed]
    except ValueError:
        candidates = list(_resolve_blocks(host))
    for addr in candidates:
        if addr in _BLOCKED_HOSTS:
            raise ValueError(f"URL host '{host}' is blocked for security")
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        for net in _PRIVATE_NETWORKS:
            if ip in net:
                raise ValueError(f"URL host '{host}' is in a private/reserved range and is blocked for security")
    return url


async def web_fetch(
    url: str = Field(description="URL to fetch"),
    max_chars: int = Field(default=8000, description="Max characters to return", ge=500, le=50000),
) -> str:
    """Fetch a web page and extract its readable text content.

    The response body is streamed and hard-capped at ``_MAX_RESPONSE_BYTES``. The host is
    DNS-resolved once before the request; httpx follows redirects without re-validation, so
    a redirect to a private address is not re-checked (bounded only by the response cap).
    """
    url = await asyncio.to_thread(_validate_url, url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    truncated = False
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30, limits=httpx.Limits(max_connections=10)
    ) as client:
        async with client.stream("GET", url, headers=headers) as resp:
            resp.raise_for_status()
            buffer = bytearray()
            async for chunk in resp.aiter_bytes():
                buffer.extend(chunk)
                if len(buffer) > _MAX_RESPONSE_BYTES:
                    truncated = True
                    break
            raw = bytes(buffer)

    text = raw.decode("utf-8", errors="replace")

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

    if truncated:
        text += f"\n[truncated at {_MAX_RESPONSE_BYTES} bytes]"

    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    return text or f"Could not extract any text content from {url}"
