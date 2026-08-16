"""Stealth browser profile — randomize HTTP headers to avoid detection.

Rotates User-Agent, Accept-Language, Sec-* headers.
Pure httpx — works on Termux and Windows, no browser/binary needed.
"""

from __future__ import annotations
from typing import List, Dict
import random


USER_AGENTS_CHROME = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]

USER_AGENTS_FIREFOX = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (X11; Linux i686; rv:131.0) Gecko/20100101 Firefox/131.0",
]

USER_AGENTS_SAFARI = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
]

USER_AGENTS_EDGE = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

ALL_AGENTS = USER_AGENTS_CHROME + USER_AGENTS_FIREFOX + USER_AGENTS_SAFARI + USER_AGENTS_EDGE

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en-US,en;q=0.9,fr;q=0.8",
    "en-US,en;q=0.9,de;q=0.8",
    "en-US,en;q=0.9,es;q=0.8,ja;q=0.7",
]

ACCEPT_ENCODINGS = [
    "gzip, deflate, br",
    "gzip, deflate",
    "br, gzip, deflate",
]

SEC_CH_UA = [
    '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    '"Chromium";v="131", "Google Chrome";v="131", "Not?A_Brand";v="99"',
    '"Chromium";v="129", "Google Chrome";v="129", "Not?A_Brand";v="99"',
]


def random_ua() -> str:
    return random.choice(ALL_AGENTS)


def random_headers(extra: Dict[str, str] = None) -> Dict[str, str]:
    """Generate a random set of browser-like headers."""
    h = {
        "User-Agent": random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept-Encoding": random.choice(ACCEPT_ENCODINGS),
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    # Firefox doesn't send Sec-Ch-Ua
    if "Chrome" in h["User-Agent"] and "Firefox" not in h["User-Agent"]:
        h["Sec-Ch-Ua"] = random.choice(SEC_CH_UA)
        h["Sec-Ch-Ua-Mobile"] = "?0"
        h["Sec-Ch-Ua-Platform"] = random.choice(['"Windows"', '"macOS"', '"Linux"'])
    if extra:
        h.update(extra)
    return h


def random_delay(base: float = 1.0, jitter: float = 0.5) -> float:
    """Return a random delay value for stealth timing."""
    return base + random.uniform(-jitter, jitter)
