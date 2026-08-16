#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gaming OSINT — cari akun gaming: Steam, Roblox, Minecraft.

Keyless sources:
- Steam    : steamcommunity.com/id/<user>?xml=1  (steamID64, nama, lokasi,
             memberSince, VAC, avatar, summary — jika profil publik)
- Roblox   : users.roblox.com API (userId, displayName, created, friends count)
- Minecraft: api.mojang.com (UUID + riwayat ganti nama)
"""

from __future__ import annotations

import asyncio
import uuid as uuid_mod
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from .proxy_manager import prepare_client


async def steam_lookup(username: str) -> Dict:
    """Steam profile via community XML (keyless)."""
    user = (username or "").strip()
    out: Dict = {"username": user, "found": False}
    try:
        async with prepare_client(timeout=12, follow_redirects=True) as c:
            r = await c.get(f"https://steamcommunity.com/id/{user}/?xml=1",
                            headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200 or "steamID64" not in r.text:
                out["error"] = f"HTTP {r.status_code} / profil tidak ditemukan atau privat"
                return out
            root = ET.fromstring(r.text)
            def g(tag):
                el = root.find(tag)
                return (el.text or "").strip() if el is not None and el.text else ""
            out["found"] = True
            out["steamID64"] = g("steamID64")
            out["customURL"] = g("customURL")
            out["display_name"] = g("steamID")
            out["real_name"] = g("realName") or None
            out["location"] = g("location") or None
            out["member_since"] = g("memberSince") or None
            out["summary"] = (g("summary") or "")[:300] or None
            out["avatar"] = g("avatarFull") or None
            out["vac_banned"] = (g("vacBanned") or "").lower() == "1"
            out["profile_url"] = f"https://steamcommunity.com/id/{user}/"
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


async def roblox_lookup(username: str) -> Dict:
    """Roblox user via public API (keyless)."""
    user = (username or "").strip()
    out: Dict = {"username": user, "found": False}
    try:
        async with prepare_client(timeout=12) as c:
            r = await c.get("https://users.roblox.com/v1/users/search",
                            params={"keyword": user, "limit": 10})
            if r.status_code != 200:
                out["error"] = f"HTTP {r.status_code}"
                return out
            data = r.json().get("data", [])
            if not data:
                out["error"] = "tidak ditemukan"
                return out
            # exact match preferred
            match = next((u for u in data if u.get("name", "").lower() == user.lower()), data[0])
            uid = match.get("id")
            out["found"] = True
            out["user_id"] = uid
            out["display_name"] = match.get("displayName")
            out["profile_url"] = f"https://www.roblox.com/users/{uid}/profile"

            # detail + friends count
            r2 = await c.get(f"https://users.roblox.com/v1/users/{uid}")
            if r2.status_code == 200:
                d2 = r2.json()
                out["created"] = d2.get("created")
                out["description"] = (d2.get("description") or "")[:200] or None
            r3 = await c.get(f"https://friends.roblox.com/v1/users/{uid}/friends/count")
            if r3.status_code == 200:
                out["friends_count"] = r3.json().get("count", 0)
            r4 = await c.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=150x150&format=Png")
            if r4.status_code == 200:
                d4 = r4.json().get("data", [])
                if d4:
                    out["avatar"] = d4[0].get("imageUrl")
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


async def minecraft_lookup(username: str) -> Dict:
    """Minecraft UUID + name history via Mojang API (keyless)."""
    user = (username or "").strip()
    out: Dict = {"username": user, "found": False}
    try:
        async with prepare_client(timeout=12) as c:
            r = await c.get(f"https://api.mojang.com/users/profiles/minecraft/{user}")
            if r.status_code != 200:
                out["error"] = "tidak ditemukan (atau HTTP %s)" % r.status_code
                return out
            d = r.json()
            uuid_plain = d.get("id", "")
            out["found"] = True
            out["uuid"] = uuid_plain
            out["current_name"] = d.get("name")
            try:
                u = uuid_mod.UUID(uuid_plain)  # add dashes
                r2 = await c.get(f"https://api.mojang.com/user/profiles/{u}/names")
                if r2.status_code == 200:
                    out["name_history"] = r2.json()
            except Exception:
                pass
            out["profile_url"] = f"https://namemc.com/profile/{uuid_plain}"
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


async def gaming_osint(username: str, kinds: Optional[List[str]] = None) -> Dict:
    """Cek akun gaming di beberapa platform sekaligus."""
    kinds = kinds or ["steam", "roblox", "minecraft"]
    fns = {"steam": steam_lookup, "roblox": roblox_lookup, "minecraft": minecraft_lookup}
    tasks = [fns[k](username) for k in kinds if k in fns]
    names = [k for k in kinds if k in fns]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: Dict = {"username": username, "platforms": {}}
    for k, r in zip(names, results):
        out["platforms"][k] = r if isinstance(r, dict) else {"error": str(r)}
    return out


def summary(res: Dict) -> Dict:
    found = []
    for k, v in res.get("platforms", {}).items():
        if isinstance(v, dict) and v.get("found"):
            found.append(k)
    return {"username": res.get("username"), "found_platforms": found}
