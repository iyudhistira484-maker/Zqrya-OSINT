#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reverse Email — enrich email ke nama/telepon/alamat (best-effort).

Sumber publik gratis:
- emailrep.io  → reputasi email (keyless, JSON) — fraud/throwaway/history.
- fastpeoplesearch / thatsthem → nama + alamat (scrape).
- Link pencarian manual (Google, Hunter, IntelligenceX, DeHashed, BreachDirectory).
"""

from __future__ import annotations

import re
from typing import Dict, List

from .proxy_manager import prepare_client

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# TLD umum — `gmail.comm`, `gmail.c` dll itu typo, bukan domain valid.
_COMMON_TLDS = {
    "com", "net", "org", "id", "co", "io", "dev", "app", "xyz", "info", "biz",
    "me", "tv", "cc", "us", "uk", "au", "ca", "de", "fr", "jp", "cn", "in",
    "sg", "my", "ph", "th", "vn", "com.id", "co.id", "or.id", "ac.id", "go.id",
    "co.uk", "org.uk", "com.au", "co.in", "com.sg", "com.my", "com.ph", "ac.th",
    "edu", "gov", "mil", "pro", "name", "mobi", "online", "site", "store", "club",
}


def is_email(s: str) -> bool:
    """Valid email + TLD yang masuk akal (tolak typo seperti `gmail.comm`)."""
    s = (s or "").strip()
    if not EMAIL_RE.match(s):
        return False
    tld = s.rsplit(".", 1)[-1].lower()
    return tld in _COMMON_TLDS


async def emailrep(email: str) -> Dict:
    """emailrep.io — reputasi email. Keyless sekarang dinonaktifkan (429), jadi
    kalau ada EMAILREP_API_KEY dipakai; tanpa key kita laporkan jujur."""
    from ..config import Config
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    if getattr(Config, "EMAILREP_API_KEY", ""):
        headers["Key"] = Config.EMAILREP_API_KEY
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get(f"https://emailrep.io/{email}", headers=headers)
            if r.status_code == 200:
                d = r.json()
                return {
                    "reputation": d.get("reputation"),
                    "suspicious": d.get("suspicious"),
                    "references": d.get("references", 0),
                    "details": d.get("details", {}),
                }
            if r.status_code == 429:
                return {"error": "emailrep.io butuh API key (gratis) — set EMAILREP_API_KEY di .env", "disabled": True}
            return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)[:80]}
    return {}


async def _web_mentions(email: str) -> Dict:
    """Fallback keyless: jumlah sebutan email di web (Google dork).
    Lemah tapi gratis — indikator kasar seberapa tersebar email itu."""
    from .google_dork import _search_google, _search_ddg
    q = f'"{email}"'
    for fn in (_search_google, _search_ddg):
        try:
            res = await fn(q)
            if res:
                return {"mentions": len(res), "engine": fn.__name__,
                        "note": "jumlah sebutan di hasil pencarian web (perkiraan kasar)"}
        except Exception:
            continue
    return {"mentions": 0, "note": "tidak ada sebutan ditemukan / pencarian terblokir"}


def _extract_fields(text: str) -> Dict:
    """Extract names/phones/addresses from broker HTML (best-effort)."""
    out: Dict = {}
    # Nama — pola umum broker
    names = re.findall(r'<h1[^>]*>([^<]{2,40})</h1>', text)
    if names:
        out["name"] = names[0].strip()
    else:
        m = re.search(r'"name"\s*:\s*"([^"]+)"', text)
        if m:
            out["name"] = m.group(1)
    phones = re.findall(r'\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}', text)
    if phones:
        out["phones"] = list(dict.fromkeys(phones))[:3]
    addrs = re.findall(r'([A-Z][a-z]+ [A-Za-z .]+, [A-Z]{2} \d{5})', text)
    if addrs:
        out["addresses"] = list(dict.fromkeys(addrs))[:3]
    return out


async def fastpeoplesearch(email: str) -> Dict:
    try:
        async with prepare_client(timeout=12, follow_redirects=True) as c:
            r = await c.get(f"https://www.fastpeoplesearch.com/email/{email}",
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if r.status_code != 200:
                return {"found": False, "note": f"HTTP {r.status_code}"}
            fields = _extract_fields(r.text)
            return {"found": bool(fields), **fields, "source": "fastpeoplesearch"}
    except Exception as e:
        return {"found": False, "error": str(e)[:80], "source": "fastpeoplesearch"}


async def thatsthem(email: str) -> Dict:
    try:
        async with prepare_client(timeout=12, follow_redirects=True) as c:
            r = await c.get(f"https://thatsthem.com/email/{email}",
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if r.status_code != 200:
                return {"found": False, "note": f"HTTP {r.status_code}"}
            fields = _extract_fields(r.text)
            return {"found": bool(fields), **fields, "source": "thatsthem"}
    except Exception as e:
        return {"found": False, "error": str(e)[:80], "source": "thatsthem"}


def manual_links(email: str) -> List[Dict]:
    from urllib.parse import quote
    q = quote(email)
    return [
        {"platform": "Google", "url": f"https://www.google.com/search?q={q}"},
        {"platform": "Hunter", "url": f"https://hunter.io/email-finder/{q}"},
        {"platform": "IntelligenceX", "url": f"https://intelx.io/?s={q}"},
        {"platform": "DeHashed", "url": f"https://dehashed.com/search?query={q}"},
        {"platform": "BreachDirectory", "url": f"https://breachdirectory.org/search?term={q}"},
    ]


async def reverse_email(email: str) -> Dict:
    """Full reverse-email: reputation + broker name/phone + manual links."""
    if not is_email(email):
        return {"email": email, "error": "format email tidak valid"}

    rep, fps, tt, mentions = await _gather(email)
    rep = rep if isinstance(rep, dict) else {}
    return {
        "email": email,
        "reputation": rep,
        "reputation_error": rep.get("error") if rep.get("error") else None,
        "web_mentions": mentions if isinstance(mentions, dict) else {},
        "people": {
            "fastpeoplesearch": fps if isinstance(fps, dict) else {},
            "thatsthem": tt if isinstance(tt, dict) else {},
        },
        "found_name": None,
        "found_phones": [],
        "manual_links": manual_links(email),
    }


async def _gather(email: str):
    import asyncio
    return await asyncio.gather(
        emailrep(email), fastpeoplesearch(email), thatsthem(email), _web_mentions(email),
        return_exceptions=True,
    )


def enrich(reverse_result: Dict) -> Dict:
    """Populate found_name/found_phones from broker results (call after reverse_email)."""
    people = reverse_result.get("people", {})
    name = None
    phones: List[str] = []
    for src, data in people.items():
        if isinstance(data, dict):
            if not name and data.get("name"):
                name = data["name"]
            phones.extend(data.get("phones", []))
    reverse_result["found_name"] = name
    reverse_result["found_phones"] = list(dict.fromkeys(phones))
    return reverse_result


async def reverse_email_full(email: str) -> Dict:
    res = await reverse_email(email)
    return enrich(res)


def summary(res: Dict) -> Dict:
    rep = res.get("reputation", {})
    return {
        "email": res.get("email"),
        "reputation": rep.get("reputation"),
        "suspicious": rep.get("suspicious"),
        "found_name": res.get("found_name"),
        "found_phones": res.get("found_phones", []),
    }
