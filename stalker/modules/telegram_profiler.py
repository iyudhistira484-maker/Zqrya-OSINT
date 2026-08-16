"""Telegram profiler — deep OSINT on Telegram users, groups, and channels.

Public Telegram methods via HTTP (mtproto proxy), no bot API needed.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import httpx
import re


async def profile(username: str) -> Dict[str, Any]:
    """Fetch public Telegram profile data for a username.

    Uses Telegram's public web interface (no API key needed).
    """
    username = username.lstrip("@")
    url = f"https://t.me/{username}"
    try:
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}", "username": username}

            html = resp.text
            result: Dict[str, Any] = {"success": True, "username": username, "type": "user"}

            # Check if it's a channel/supergroup
            if "tgme_page_title" in html:
                title = re.search(r'property="og:title" content="([^"]*)"', html)
                desc = re.search(r'property="og:description" content="([^"]*)"', html)
                image = re.search(r'property="og:image" content="([^"]*)"', html)
                result["display_name"] = title.group(1) if title else username
                result["bio"] = desc.group(1)[:500] if desc else ""
                result["avatar_url"] = image.group(1) if image else ""

                # Detect type
                if "subscribers" in html.lower() or "members" in html.lower():
                    result["type"] = "channel"
                    member_match = re.search(r'class="tgme_page_extra"[^>]*>(.*?)</div>', html)
                    if member_match:
                        result["members_text"] = member_match.group(1).strip()

            # Try the telegram embed JSON (more data)
            embed_url = f"https://t.me/{username}?embed=1&mode=tme"
            resp2 = await client.get(embed_url)
            if resp2.status_code == 200:
                html2 = resp2.text
                # Extract from page props
                num_id = re.search(r'data-peer-id="-?(\d+)"', html2)
                if num_id:
                    result["numeric_id"] = num_id.group(1)

            return result

    except Exception as e:
        return {"success": False, "error": str(e), "username": username}
