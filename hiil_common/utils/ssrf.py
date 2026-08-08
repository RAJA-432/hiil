"""SSRF-guarded URL validation shared by all H.I.I.L. network tools.

Unifies the logic from ``veda_engine.tools.web`` and ``drishti_engine.tools._net``:
only http/https schemes, a hostname blocklist, and a DNS resolution check that
rejects private, loopback, link-local, and reserved addresses (including
IPv4-mapped-IPv6). Network tools must also re-validate every redirect hop.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_BLOCKED_HOSTS = frozenset(
    {
        "169.254.169.254",
        "metadata.google.internal",
        "100.100.100.200",
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",  # noqa: S104 -- blocklist, not bind address
    }
)
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
_MAX_REDIRECTS = 5


def _resolve_blocks(host: str) -> tuple[str, ...]:
    """Resolve a hostname to all of its IP addresses, raising on resolution failure."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValueError(f"Could not resolve URL host '{host}'") from None
    return tuple(str(info[4][0]) for info in infos)


def validate_public_http_url(url: str) -> str:
    """Validate that ``url`` is an http(s) URL resolving only to public addresses.

    Rejects non-http(s) schemes and blocked hostnames, then resolves the hostname
    via DNS and rejects any private, loopback, link-local, or reserved address.
    Returns the URL unchanged when valid.
    """
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
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError(f"URL host '{host}' is in a private/reserved range and is blocked for security")
        for net in _PRIVATE_NETWORKS:
            if ip in net:
                raise ValueError(f"URL host '{host}' is in a private/reserved range and is blocked for security")
    return url


async def fetch_public_http(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_bytes: int = _MAX_RESPONSE_BYTES,
    timeout: float = 30.0,
) -> bytes:
    """Fetch ``url`` following redirects manually, re-validating every hop.

    Returns the raw body bytes, capped at ``max_bytes``. Every redirect target
    is re-validated against the SSRF rules before it is requested, so a
    redirect to a private or blocked address is rejected.
    """
    import httpx

    url = await asyncio.to_thread(validate_public_http_url, url)
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=timeout,
        limits=httpx.Limits(max_connections=10),
    ) as client:
        current_url = url
        redirects = 0
        while True:
            if redirects > _MAX_REDIRECTS:
                raise ValueError(f"Too many redirects while fetching {url}")
            async with client.stream("GET", current_url, headers=headers or {}) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise ValueError(f"Redirect from {current_url} is missing a Location header")
                    current_url = await asyncio.to_thread(
                        validate_public_http_url, urljoin(current_url, location)
                    )
                    redirects += 1
                    continue
                resp.raise_for_status()
                buffer = bytearray()
                async for chunk in resp.aiter_bytes():
                    buffer.extend(chunk)
                    if len(buffer) > max_bytes:
                        raise ValueError(f"Response exceeds the {max_bytes} byte limit")
                return bytes(buffer)


def extract_readable_text(raw: bytes, max_chars: int) -> str:
    """Strip HTML tags/scripts and collapse whitespace from a fetched page."""
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&#x27;", "'")
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text
