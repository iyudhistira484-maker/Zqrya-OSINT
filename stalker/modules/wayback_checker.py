"""Wayback Machine / Archive.org — find deleted/cached profiles & content.

Features:
- Check if profile URL is archived in Wayback Machine
- Get first & last snapshot dates (when did they appear/disappear?)
- Find deleted social media profiles
- Check multiple platform profile URLs in parallel
- Extract text content from cached pages
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio
from .proxy_manager import prepare_client

WB_API = "http://archive.org/wayback/available"
WB_CDX = "http://web.archive.org/cdx/search/cdx"

PROFILE_URLS = {
    "twitter": "https://twitter.com/{username}",
    "instagram": "https://www.instagram.com/{username}/",
    "facebook": "https://www.facebook.com/{username}",
    "tiktok": "https://www.tiktok.com/@{username}",
    "github": "https://github.com/{username}",
    "linkedin": "https://www.linkedin.com/in/{username}/",
    "reddit": "https://www.reddit.com/user/{username}/",
    "youtube": "https://www.youtube.com/@{username}",
    "twitch": "https://www.twitch.tv/{username}",
    "telegram": "https://t.me/{username}",
    "pinterest": "https://www.pinterest.com/{username}/",
    "snapchat": "https://www.snapchat.com/add/{username}",
}

async def check_url_archived(url: str) -> Dict[str, Any]:
    """Check if a URL has any Wayback Machine snapshots."""
    try:
        async with prepare_client(timeout=12) as c:
            r = await c.get(f"{WB_API}?url={url}")
            if r.status_code == 200:
                d = r.json()
                snap = d.get("archived_snapshots", {}).get("closest", {})
                if snap.get("available"):
                    return {
                        "url": url, "archived": True,
                        "snapshot_url": snap.get("url",""),
                        "timestamp": snap.get("timestamp",""),
                        "status": snap.get("status",""),
                    }
    except Exception: pass
    return {"url": url, "archived": False}

async def get_snapshot_history(url: str) -> Dict[str, Any]:
    """Get first/last snapshot + total count from CDX API."""
    try:
        async with prepare_client(timeout=15) as c:
            # First snapshot
            r1 = await c.get(f"{WB_CDX}?url={url}&output=json&limit=1&fl=timestamp,statuscode&from=&to=")
            # Last snapshot
            r2 = await c.get(f"{WB_CDX}?url={url}&output=json&limit=1&fl=timestamp,statuscode&from=&to=&fastLatest=true")
            # Count
            r3 = await c.get(f"{WB_CDX}?url={url}&output=json&limit=1&showNumPages=true")

            first = last = None
            count = 0

            if r1.status_code == 200:
                d1 = r1.json()
                if len(d1) > 1: first = d1[1][0]  # skip header row

            if r2.status_code == 200:
                d2 = r2.json()
                if len(d2) > 1: last = d2[1][0]

            if r3.status_code == 200:
                try: count = int(r3.text.strip())
                except Exception: pass

            return {
                "first_seen": _fmt_ts(first), "last_seen": _fmt_ts(last),
                "total_snapshots": count, "has_history": bool(first),
            }
    except Exception:
        return {"has_history": False}

def _fmt_ts(ts: Optional[str]) -> str:
    if not ts or len(ts) < 8: return ""
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"

async def check_username_across_platforms(username: str) -> Dict[str, Any]:
    """Check if username profiles are archived across all platforms."""
    async def _check(platform: str, url_tpl: str):
        url = url_tpl.format(username=username)
        archived = await check_url_archived(url)
        if archived.get("archived"):
            history = await get_snapshot_history(url)
            return platform, {**archived, **history, "platform_url": url}
        return platform, {"archived": False, "platform_url": url}

    tasks = [_check(p, u) for p, u in PROFILE_URLS.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        platform: data
        for r in results if isinstance(r, tuple)
        for platform, data in [r]
    }

async def full_wayback_intel(username: str) -> Dict[str, Any]:
    """Full Wayback Machine investigation for a username."""
    results = await check_username_across_platforms(username)
    archived = {p: d for p, d in results.items() if d.get("archived")}
    return {
        "username": username,
        "platforms_archived": archived,
        "total_archived": len(archived),
        "platforms_checked": len(results),
    }

def summary(data: Dict[str, Any]) -> Dict[str, Any]:
    archived = data.get("platforms_archived", {})
    return {
        "total_archived": data.get("total_archived", 0),
        "archived_platforms": list(archived.keys()),
        "oldest_appearance": min(
            (d.get("first_seen","") for d in archived.values() if d.get("first_seen")),
            default=""
        ),
    }
