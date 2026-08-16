#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IG/TikTok Deep OSINT — followers, bio, avatar, verified (best-effort).

Keyless scraping of public profile pages:
- TikTok : __UNIVERSAL_DATA_FOR_REHYDRATION__ / SIGI_STATE JSON di halaman @user.
- Instagram: meta og:title / og:description (followers/following/posts).
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Dict

from .proxy_manager import prepare_client


def _find_user_dict(obj, depth: int = 0):
    """Recursively find a dict containing followerCount + a username-ish key."""
    if depth > 8 or not isinstance(obj, (dict, list)):
        return None
    if isinstance(obj, dict):
        if "followerCount" in obj and ("uniqueId" in obj or "nickname" in obj or "username" in obj):
            return obj
        for v in obj.values():
            r = _find_user_dict(v, depth + 1)
            if r:
                return r
    else:
        for v in obj:
            r = _find_user_dict(v, depth + 1)
            if r:
                return r
    return None


async def tiktok_lookup(username: str) -> Dict:
    """TikTok public profile stats (keyless scrape)."""
    user = (username or "").strip().lstrip("@")
    out: Dict = {"username": user, "found": False}
    try:
        async with prepare_client(timeout=15, follow_redirects=True) as c:
            r = await c.get(f"https://www.tiktok.com/@{user}",
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            if r.status_code != 200:
                out["error"] = f"HTTP {r.status_code}"
                return out
            text = r.text
            # Cari blob JSON
            blob = None
            for marker in ("__UNIVERSAL_DATA_FOR_REHYDRATION__", "SIGI_STATE"):
                idx = text.find(marker)
                if idx != -1:
                    start = text.find("{", idx)
                    # hentikan di </script>
                    end = text.find("</script>", idx)
                    if start != -1:
                        candidate = text[start:end if end != -1 else start + 200000]
                        try:
                            blob = json.loads(candidate)
                            break
                        except Exception:
                            blob = None
            if blob is None:
                out["error"] = "data profil tidak ditemukan (rate-limit/Cloudflare?)"
                return out
            u = _find_user_dict(blob)
            if not u:
                out["error"] = "struktur data berubah"
                return out
            out["found"] = True
            out["user_id"] = u.get("id")
            out["nickname"] = u.get("nickname")
            out["unique_id"] = u.get("uniqueId")
            out["bio"] = u.get("signature")
            out["verified"] = u.get("verified", False)
            out["followers"] = u.get("followerCount")
            out["following"] = u.get("followingCount")
            out["likes"] = u.get("heartCount") or u.get("heart")
            out["videos"] = u.get("videoCount")
            out["avatar"] = u.get("avatarLarger") or u.get("avatarThumb")
            out["profile_url"] = f"https://www.tiktok.com/@{user}"
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


async def instagram_lookup(username: str) -> Dict:
    """Instagram public profile (meta tag scrape, best-effort tanpa login)."""
    user = (username or "").strip().lstrip("@")
    out: Dict = {"username": user, "found": False}
    try:
        async with prepare_client(timeout=15, follow_redirects=True) as c:
            r = await c.get(f"https://www.instagram.com/{user}/",
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            if r.status_code != 200:
                out["error"] = f"HTTP {r.status_code}"
                return out
            text = r.text
            m = re.search(r'<meta property="og:title" content="([^"]+)"', text)
            if m:
                out["found"] = True
                out["title"] = m.group(1)
            d = re.search(r'<meta property="og:description" content="([^"]+)"', text)
            if d:
                out["found"] = True
                desc = d.group(1)
                out["description"] = desc
                nums = re.findall(r"([\d,.]+)\s*(Followers|Following|Posts)", desc)
                for val, label in nums:
                    try:
                        out[label.lower()] = int(val.replace(",", "").replace(".", ""))
                    except Exception:
                        out[label.lower()] = val
            if not out.get("found"):
                out["error"] = "profil tidak ditemukan / butuh login (Instagram membatasi scrape anonim)"
            out["profile_url"] = f"https://www.instagram.com/{user}/"
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


async def social_deep(username: str) -> Dict:
    """Jalankan IG + TikTok sekaligus."""
    tg, ig = await asyncio.gather(tiktok_lookup(username), instagram_lookup(username), return_exceptions=True)
    return {
        "username": username,
        "tiktok": tg if isinstance(tg, dict) else {"error": str(tg)},
        "instagram": ig if isinstance(ig, dict) else {"error": str(ig)},
    }


def summary(res: Dict) -> Dict:
    out = {"username": res.get("username")}
    tg = res.get("tiktok", {})
    if isinstance(tg, dict) and tg.get("found"):
        out["tiktok_followers"] = tg.get("followers")
        out["tiktok_verified"] = tg.get("verified")
    ig = res.get("instagram", {})
    if isinstance(ig, dict) and ig.get("found"):
        out["instagram_followers"] = ig.get("followers")
    return out
