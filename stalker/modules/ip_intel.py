#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IP intelligence tambahan (keyless, tanpa API key).

- reverse_ip_lookup : IP -> daftar domain yang di-host di IP yang sama
                      (sumber: HackerTarget — API teks, gratis/keyless).
- check_cins_army   : cek apakah IP masuk daftar "bad guys" CINS Army
                      (daftar IP berbahaya berbasis laporan komunitas — gratis).

Keduanya dipakai oleh ip_tracker.track_ip() supaya laporan IP lebih lengkap.
"""

from __future__ import annotations

from typing import Dict, List
from pathlib import Path
import time

from .proxy_manager import prepare_client

HACKERTARGET_URL = "https://api.hackertarget.com/reverseiplookup/?q={}"
CINS_URLS = [
    "https://cinsscore.com/list/ci-badguys.txt",
    "http://cinsscore.com/list/ci-badguys.txt",
]
CINS_CACHE = Path("output/.ip_intel/cins_badguys.txt")
CINS_TTL = 6 * 3600  # refresh daftar tiap 6 jam


async def reverse_ip_lookup(ip: str) -> Dict:
    """Cari domain lain yang di-hosting di IP yang sama (reverse IP).

    Returns dict: {domains: [...], count: int, source: str, note: str|None}
    """
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.get(HACKERTARGET_URL.format(ip), headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return {"domains": [], "count": 0, "source": "hackertarget", "note": f"HTTP {r.status_code}"}
            text = r.text or ""
            if "API count exceeded" in text or "error" in text.lower() or "invalid" in text.lower():
                return {"domains": [], "count": 0, "source": "hackertarget", "note": text.strip()[:80]}
            domains = [d.strip() for d in text.splitlines()
                       if d.strip() and not d.strip().startswith("#")]
            return {"domains": domains, "count": len(domains), "source": "hackertarget", "note": None}
    except Exception as e:
        return {"domains": [], "count": 0, "source": "hackertarget", "note": str(e)[:80]}


def _cins_is_fresh() -> bool:
    try:
        return (time.time() - CINS_CACHE.stat().st_mtime) < CINS_TTL and CINS_CACHE.stat().st_size > 1000
    except Exception:
        return False


async def _download_cins_list() -> bool:
    """Unduh daftar bad-guys CINS Army ke cache (idempoten)."""
    if _cins_is_fresh():
        return True
    CINS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    for url in CINS_URLS:
        try:
            async with prepare_client(timeout=20) as c:
                r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and r.text and len(r.text) > 1000:
                    CINS_CACHE.write_text(r.text, encoding="utf-8")
                    return True
        except Exception:
            continue
    return False


async def check_cins_army(ip: str) -> Dict:
    """Cek apakah IP ada di daftar bad-guys CINS Army.

    Returns dict: {listed: bool, source: str, note: str|None}
    """
    ok = await _download_cins_list()
    if not ok:
        return {"listed": False, "source": "cins-army", "note": "daftar tidak tersedia"}
    try:
        ip_norm = ip.strip()
        with open(CINS_CACHE, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.strip() == ip_norm:
                    return {"listed": True, "source": "cins-army", "note": None}
    except Exception:
        pass
    return {"listed": False, "source": "cins-army", "note": None}
