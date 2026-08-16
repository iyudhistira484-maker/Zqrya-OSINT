"""Gravatar & Email-based Profile Lookup.

From just an email or username, extract:
- Gravatar avatar + profile data (display name, accounts linked)
- Libravatar fallback
- MD5 hash (useful for correlation)
- Linked accounts (GitHub, Twitter, etc.) from Gravatar profile
"""
from __future__ import annotations
import hashlib, asyncio
from typing import Dict, Any, List
from .proxy_manager import prepare_client

def email_to_hash(email: str) -> str:
    return hashlib.md5(email.strip().lower().encode()).hexdigest()

def username_to_hash(username: str) -> str:
    return hashlib.md5(username.strip().lower().encode()).hexdigest()

async def lookup_gravatar(email_or_hash: str, is_hash: bool = False) -> Dict[str, Any]:
    """Lookup Gravatar profile by email or MD5 hash."""
    h = email_or_hash if is_hash else email_to_hash(email_or_hash)
    result = {"hash": h, "avatar_url": f"https://www.gravatar.com/avatar/{h}?d=404&s=200"}
    try:
        async with prepare_client(timeout=12) as c:
            # Check if avatar exists
            r = await c.get(result["avatar_url"])
            result["has_avatar"] = r.status_code == 200

            # Fetch JSON profile
            r2 = await c.get(f"https://www.gravatar.com/{h}.json")
            if r2.status_code == 200:
                d = r2.json()
                entry = d.get("entry", [{}])[0] if d.get("entry") else {}
                result.update({
                    "found": True,
                    "display_name": entry.get("displayName",""),
                    "preferred_username": entry.get("preferredUsername",""),
                    "about": entry.get("aboutMe",""),
                    "location": entry.get("currentLocation",""),
                    "profile_url": entry.get("profileUrl",""),
                    "thumbnail": entry.get("thumbnailUrl",""),
                    "accounts": [
                        {"domain": acc.get("domain",""), "shortname": acc.get("shortname",""), "url": acc.get("url","")}
                        for acc in entry.get("accounts",[])
                    ],
                    "emails": [e.get("value","") for e in entry.get("emails",[]) if e.get("value")],
                    "phone_numbers": [p.get("value","") for p in entry.get("phoneNumbers",[])],
                    "ims": [i.get("value","") for i in entry.get("ims",[])],
                })
            else:
                result["found"] = result["has_avatar"]
    except Exception as e:
        result["found"] = False
        result["error"] = str(e)
    return result

async def check_avatar_exists(email: str) -> bool:
    h = email_to_hash(email)
    try:
        async with prepare_client(timeout=8) as c:
            r = await c.get(f"https://www.gravatar.com/avatar/{h}?d=404")
            return r.status_code == 200
    except Exception:
        return False

def summary(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "found": data.get("found", False),
        "has_avatar": data.get("has_avatar", False),
        "display_name": data.get("display_name",""),
        "linked_accounts": [a["domain"] for a in data.get("accounts",[])],
        "emails": data.get("emails", []),
        "location": data.get("location",""),
    }
