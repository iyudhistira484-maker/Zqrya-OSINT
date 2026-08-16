"""Dark Web & Paste Site Checker.

Checks if username/email/phone appears in:
- Pastebin (via Google dork)
- GhostProject (free email breach search)
- LeakCheck public API
- IntelX (free tier)
- Psbdmp (pastebin dump search)
- BreachDirectory (free tier)

Termux-compatible: pure Python asyncio + httpx.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio
import re
import urllib.parse
import httpx
from .proxy_manager import prepare_client


async def check_ghostproject(email: str) -> Dict[str, Any]:
    """Check GhostProject for email in breach databases (free, no key)."""
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.post(
                "https://ghostproject.fr/search",
                data={"search": email},
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://ghostproject.fr/",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                follow_redirects=True,
            )
            if r.status_code == 200:
                html = r.text
                if "No results" in html or "not found" in html.lower():
                    return {"found": False, "source": "ghostproject"}
                # Count result rows
                count = html.count('<tr class="result')
                if count == 0:
                    count = html.count("result-row")
                return {
                    "found": count > 0 or "result" in html.lower(),
                    "count": count,
                    "source": "ghostproject",
                    "url": "https://ghostproject.fr/",
                }
    except Exception as e:
        return {"found": False, "source": "ghostproject", "error": str(e)}
    return {"found": False, "source": "ghostproject"}


async def check_psbdmp(query: str) -> Dict[str, Any]:
    """Search Psbdmp — pastebin dump index (free, no key)."""
    try:
        encoded = urllib.parse.quote(query)
        async with prepare_client(timeout=15) as c:
            r = await c.get(
                f"https://psbdmp.ws/api/v3/search/{encoded}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code == 200:
                data = r.json()
                pastes = data.get("data", [])
                return {
                    "found": len(pastes) > 0,
                    "count": len(pastes),
                    "pastes": [
                        {
                            "id": p.get("id", ""),
                            "url": f"https://pastebin.com/{p.get('id', '')}",
                            "time": p.get("time", ""),
                            "preview": p.get("text", "")[:200],
                        }
                        for p in pastes[:5]
                    ],
                    "source": "psbdmp",
                }
    except Exception as e:
        return {"found": False, "source": "psbdmp", "error": str(e)}
    return {"found": False, "source": "psbdmp"}


async def check_breachdirectory(term: str) -> Dict[str, Any]:
    """Check BreachDirectory API (free public tier)."""
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.get(
                f"https://breachdirectory.org/api?func=auto&term={urllib.parse.quote(term)}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    results = data.get("result", [])
                    return {
                        "found": len(results) > 0,
                        "count": len(results),
                        "breaches": [
                            {
                                "password_hint": r.get("password", "")[:4] + "***" if r.get("password") else "",
                                "has_password": bool(r.get("password")),
                                "sha1": r.get("sha1", ""),
                            }
                            for r in results[:5]
                        ],
                        "source": "breachdirectory",
                    }
    except Exception as e:
        return {"found": False, "source": "breachdirectory", "error": str(e)}
    return {"found": False, "source": "breachdirectory"}


async def check_leakcheck_free(email: str) -> Dict[str, Any]:
    """Check LeakCheck free public API (limited: source names only)."""
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.get(
                f"https://leakcheck.io/api/public?check={urllib.parse.quote(email)}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    sources = data.get("sources", [])
                    return {
                        "found": len(sources) > 0,
                        "count": len(sources),
                        "sources": sources[:10],
                        "source": "leakcheck",
                    }
    except Exception as e:
        return {"found": False, "source": "leakcheck", "error": str(e)}
    return {"found": False, "source": "leakcheck"}


async def check_intelx_free(query: str) -> Dict[str, Any]:
    """Check IntelX free public search (rate limited)."""
    try:
        async with prepare_client(timeout=20) as c:
            # Start search
            r = await c.post(
                "https://2.intelx.io/intelligent/search",
                json={
                    "term": query,
                    "buckets": [],
                    "lookuplevel": 0,
                    "maxresults": 10,
                    "timeout": 5,
                    "datefrom": "",
                    "dateto": "",
                    "sort": 4,
                    "media": 0,
                    "terminate": [],
                },
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "x-key": "PUBLIC",
                },
            )
            if r.status_code == 200:
                data = r.json()
                search_id = data.get("id", "")
                if not search_id:
                    return {"found": False, "source": "intelx"}

                await asyncio.sleep(2)

                # Get results
                r2 = await c.get(
                    f"https://2.intelx.io/intelligent/search/result?id={search_id}&limit=5&statistics=0",
                    headers={"User-Agent": "Mozilla/5.0", "x-key": "PUBLIC"},
                )
                if r2.status_code == 200:
                    data2 = r2.json()
                    records = data2.get("records", [])
                    return {
                        "found": len(records) > 0,
                        "count": len(records),
                        "results": [
                            {
                                "name": rec.get("name", ""),
                                "date": rec.get("date", ""),
                                "bucket": rec.get("bucket", ""),
                            }
                            for rec in records[:5]
                        ],
                        "source": "intelx",
                        "search_url": f"https://intelx.io/?s={urllib.parse.quote(query)}",
                    }
    except Exception as e:
        return {"found": False, "source": "intelx", "error": str(e)}
    return {"found": False, "source": "intelx"}


async def full_darkweb_check(query: str, query_type: str = "email") -> Dict[str, Any]:
    """Run all dark web checks in parallel.
    
    Args:
        query: email, username, or phone to search
        query_type: "email", "username", or "phone"
    """
    tasks = []

    if query_type == "email":
        tasks = [
            check_ghostproject(query),
            check_psbdmp(query),
            check_breachdirectory(query),
            check_leakcheck_free(query),
            check_intelx_free(query),
        ]
    else:
        # Username/phone: psbdmp + intelx only (others need email)
        tasks = [
            check_psbdmp(query),
            check_intelx_free(query),
        ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    output = {}
    for r in results:
        if isinstance(r, dict):
            source = r.get("source", "unknown")
            output[source] = r

    return output


def summary(results: Dict[str, Any]) -> Dict[str, Any]:
    total_found = sum(1 for r in results.values() if isinstance(r, dict) and r.get("found"))
    total_records = sum(
        r.get("count", 0) for r in results.values()
        if isinstance(r, dict) and r.get("found")
    )
    found_sources = [
        source for source, r in results.items()
        if isinstance(r, dict) and r.get("found")
    ]
    return {
        "sources_checked": len(results),
        "sources_found": total_found,
        "total_records": total_records,
        "found_in": found_sources,
    }
