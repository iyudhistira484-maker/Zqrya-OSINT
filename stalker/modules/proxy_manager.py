"""HTTP client factory — stealth headers + retry transport + mobile-optimized limits.

DNS FIX: Uses httpx RetryTransport + mobile-aware connection limits.
On Termux: max 10 concurrent connections, 20s timeout, 3 retries on network errors.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict
import httpx

IS_TERMUX = Path("/data/data/com.termux").is_dir()


class _RetryTransport(httpx.AsyncHTTPTransport):
    """Retry transport that retries on DNS/connection errors."""

    def __init__(self, retries: int = 3, **kwargs):
        super().__init__(retries=retries, **kwargs)
        self._max_retries = retries

    async def handle_async_request(self, request):
        import asyncio
        last_exc = None
        for attempt in range(self._max_retries):
            try:
                return await super().handle_async_request(request)
            except (httpx.ConnectError, httpx.TimeoutException,
                    httpx.NetworkError, httpx.RemoteProtocolError) as e:
                last_exc = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise last_exc


def _get_limits() -> httpx.Limits:
    """Mobile-aware connection limits."""
    if IS_TERMUX:
        return httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=5,
        )
    return httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
        keepalive_expiry=30,
    )


def _get_timeout() -> httpx.Timeout:
    """Mobile-aware timeout."""
    if IS_TERMUX:
        return httpx.Timeout(
            connect=15.0,    # DNS + connect: longer for carrier DNS
            read=20.0,
            write=10.0,
            pool=5.0,
        )
    return httpx.Timeout(
        connect=10.0,
        read=30.0,
        write=10.0,
        pool=10.0,
    )


def prepare_client(**kwargs) -> httpx.AsyncClient:
    """Create httpx.AsyncClient with:
    - Stealth headers injection
    - Retry transport (3 retries on DNS/connection error)
    - Mobile-optimized connection limits for Termux
    - Proper timeouts for carrier DNS

    Usage:
        async with prepare_client(timeout=15) as client:
            resp = await client.get(url)
    """
    # Apply DNS patch for Termux
    if IS_TERMUX:
        try:
            from .dns_fix import patch_dns_for_termux
            patch_dns_for_termux()
        except ImportError:
            pass

    from stalker.config import Config

    user_headers: Dict = kwargs.pop("headers", None) or {}
    user_timeout = kwargs.pop("timeout", None)
    user_limits  = kwargs.pop("limits", None)

    # Headers
    headers = None
    if Config.STEALTH_RANDOM_UA:
        try:
            from . import stealth_profile
            headers = stealth_profile.random_headers(user_headers)
        except ImportError:
            headers = user_headers or None
    elif user_headers:
        headers = user_headers

    # Timeout: user override → mobile default → desktop default
    timeout = user_timeout if user_timeout is not None else _get_timeout()
    limits  = user_limits  if user_limits  is not None else _get_limits()

    # Retry transport (retries=3 built into httpx core transport)
    transport = _RetryTransport(retries=3)

    return httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        limits=limits,
        transport=transport,
        follow_redirects=True,
        **kwargs,
    )
