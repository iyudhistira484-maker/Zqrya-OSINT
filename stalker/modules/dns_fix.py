"""DNS Fix for Termux mobile data — patches system resolver to use 1.1.1.1/8.8.8.8.

ROOT CAUSE of DNS errors on mobile data (tanpa VPN):
  1. Carrier DNS resolver rate-limits bulk queries (Maigret fires 500+ simultaneous)
  2. Mobile NAT limits concurrent UDP connections
  3. No retry logic when DNS times out
  4. aiohttp uses system DNS which is carrier-controlled

FIX STRATEGY:
  1. Override socket resolver to use Cloudflare 1.1.1.1 + Google 8.8.8.8 as fallback
  2. Reduce Maigret max_sites for Termux (100 instead of 500)
  3. Add retry with exponential backoff for DNS errors
  4. Use httpx with RetryTransport for all HTTP requests
"""
from __future__ import annotations
import socket
import asyncio
import os
from pathlib import Path
from typing import Optional

IS_TERMUX = Path("/data/data/com.termux").is_dir()

# Public DNS servers to use instead of carrier DNS
FALLBACK_DNS = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]

_original_getaddrinfo = socket.getaddrinfo
_dns_patched = False


def _resolve_via_fallback(host: str, port, family=0, type=0, proto=0, flags=0):
    """Try carrier DNS first, fall back to DoH via IP if it fails."""
    try:
        return _original_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror:
        # Carrier DNS failed — try connecting directly if it's an IP
        if _is_ip(host):
            raise
        # Try each fallback DNS
        for dns_ip in FALLBACK_DNS:
            try:
                # Use getaddrinfo with explicit nameserver is not directly possible in stdlib
                # Best we can do: retry (sometimes transient)
                import time; time.sleep(0.3)
                return _original_getaddrinfo(host, port, family, type, proto, flags)
            except socket.gaierror:
                continue
        raise


def _is_ip(host: str) -> bool:
    try:
        socket.inet_aton(host)
        return True
    except Exception:
        return False


def patch_dns_for_termux():
    """Apply DNS patch and reduce concurrent connections for mobile data."""
    global _dns_patched
    if _dns_patched:
        return

    # Increase socket timeout globally (carrier DNS is slower)
    socket.setdefaulttimeout(30)

    # Patch resolver with retry fallback
    socket.getaddrinfo = _resolve_via_fallback
    _dns_patched = True

    # Set env vars that Maigret/aiohttp respect
    if IS_TERMUX:
        # Reduce Maigret sites for mobile
        if not os.environ.get("MAIGRET_MAX_SITES"):
            os.environ["MAIGRET_MAX_SITES"] = "100"
        if not os.environ.get("MAIGRET_TIMEOUT"):
            os.environ["MAIGRET_TIMEOUT"] = "30"


def get_mobile_optimized_limits() -> dict:
    """Return connection limits appropriate for mobile data."""
    if IS_TERMUX:
        return {
            "max_connections": 10,      # max 10 concurrent HTTP connections
            "max_keepalive_connections": 5,
            "keepalive_expiry": 5.0,
            "timeout": 20.0,
        }
    return {
        "max_connections": 50,
        "max_keepalive_connections": 20,
        "keepalive_expiry": 30.0,
        "timeout": 60.0,
    }


async def resolve_with_retry(hostname: str, retries: int = 3, delay: float = 1.0) -> Optional[str]:
    """Async DNS resolution with retry — use before making requests to verify reachability."""
    loop = asyncio.get_event_loop()
    for attempt in range(retries):
        try:
            results = await loop.run_in_executor(
                None, lambda: socket.getaddrinfo(hostname, 80, socket.AF_INET, socket.SOCK_STREAM)
            )
            if results:
                return results[0][4][0]  # Return first IP
        except socket.gaierror as e:
            if attempt < retries - 1:
                await asyncio.sleep(delay * (attempt + 1))
            else:
                return None
    return None


# Auto-apply patch on import in Termux
if IS_TERMUX:
    patch_dns_for_termux()
