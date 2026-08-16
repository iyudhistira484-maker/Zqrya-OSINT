"""Password leak checker — Pwned Passwords API (k-anonymity).

Free, no API key. Sends only first 5 chars of SHA-1 hash.
Returns count of how many times the password appears in breaches.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import hashlib
import httpx
import re
import asyncio

PWNED_API = "https://api.pwnedpasswords.com/range"


async def check_password_leak(password: str) -> Dict[str, Any]:
    """Check if a password appears in known data breaches.

    Uses k-anonymity: sends only SHA-1 hash prefix, never the full password.
    """
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{PWNED_API}/{prefix}",
                headers={"User-Agent": "Stalker-OSINT", "Add-Padding": "true"},
            )
            if resp.status_code != 200:
                return {"found": False, "count": 0, "error": f"HTTP {resp.status_code}"}

            for line in resp.text.splitlines():
                hash_suffix, count = line.split(":")
                if hash_suffix.strip() == suffix:
                    return {"found": True, "count": int(count.strip())}

            return {"found": False, "count": 0}
    except Exception as e:
        return {"found": False, "count": 0, "error": str(e)}


async def check_passwords_bulk(passwords: list[str]) -> list[Dict[str, Any]]:
    """Check multiple passwords against Pwned Passwords."""
    results = await asyncio.gather(
        *[check_password_leak(pw) for pw in passwords[:5]],
        return_exceptions=True,
    )
    output = []
    for pw, r in zip(passwords[:5], results):
        if isinstance(r, Exception):
            output.append({"password": "***", "found": False, "count": 0, "error": str(r)})
        else:
            r["password_hint"] = pw[:2] + "***"
            output.append(r)
    return output


async def check_from_text(text: str) -> Dict[str, Any]:
    """Extract potential password patterns from text and check them."""
    candidates = set()
    
    # Cari string yang tidak memiliki spasi dan panjangnya 6-30 karakter
    for m in re.finditer(r"\b\S{6,30}\b", text):
        pw = m.group()
        
        has_lower = any(c.islower() for c in pw)
        has_upper = any(c.isupper() for c in pw)
        has_digit = any(c.isdigit() for c in pw)
        has_special = any(not c.isalnum() for c in pw)
        
        # Logika Entropi: Kandidat harus memiliki angka + huruf + (huruf besar ATAU spesial karakter)
        if has_digit and (has_lower or has_upper):
            if has_special or (has_lower and has_upper):
                candidates.add(pw)

    if not candidates:
        return {"leaked_count": 0, "details": []}

    # Urutkan kandidat berdasarkan kompleksitasnya (variasi karakter unik + panjang)
    # Ini memastikan kita mengetes 5 kata sandi yang paling mungkin bocor/asli, bukan kata umum
    sorted_candidates = sorted(
        list(candidates), 
        key=lambda x: len(set(x)) + len(x), 
        reverse=True
    )

    results = await check_passwords_bulk(sorted_candidates[:5])
    
    leaked = [r for r in results if r.get("found")]
    return {
        "leaked_count": len(leaked),
        "details": results
    }

