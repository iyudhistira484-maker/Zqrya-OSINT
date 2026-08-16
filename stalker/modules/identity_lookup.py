"""Identity enrichment from keyless public sources: Keybase.

Untuk email/username, cari orang di baliknya via Keybase (gratis, tanpa API key):
- lookup berdasarkan username -> nama lengkap + identity proof terverifikasi
- lookup berdasarkan email (jika tersedia)
"""

from __future__ import annotations
from typing import Dict, Any, List
from .proxy_manager import prepare_client

KB_API = "https://keybase.io/_/api/1.0"


def _parse_user(d: Dict) -> Dict[str, Any]:
    them = (d.get("them") or [])[0] if d.get("them") else None
    if not them:
        return {"found": False}
    basics = them.get("basics") or {}
    profile = them.get("profile") or {}
    proofs = them.get("proofs_summary") or {}
    all_proofs = proofs.get("all") or []
    return {
        "found": True,
        "username": basics.get("username", ""),
        "full_name": profile.get("full_name", ""),
        "location": profile.get("location", ""),
        "bio": profile.get("bio", ""),
        "profile_url": f"https://keybase.io/{basics.get('username', '')}",
        "proofs": [
            {
                "type": p.get("proof_type", ""),
                "name": p.get("nametag", ""),
                "service_url": p.get("service_url", ""),
            }
            for p in all_proofs[:10]
        ],
    }


async def lookup_keybase(username: str) -> Dict[str, Any]:
    """Keybase lookup by username -> full name + verified proofs."""
    try:
        async with prepare_client(timeout=12) as c:
            r = await c.get(f"{KB_API}/user/lookup.json", params={"usernames": username})
            if r.status_code == 200:
                return _parse_user(r.json())
    except Exception:
        pass
    return {"found": False}


async def lookup_keybase_by_email(email: str) -> Dict[str, Any]:
    """Keybase lookup by email (jika Keybase masih membuka endpoint ini)."""
    try:
        async with prepare_client(timeout=12) as c:
            r = await c.get(f"{KB_API}/user/lookup.json", params={"email": email})
            if r.status_code == 200:
                d = r.json()
                if d.get("them"):
                    return _parse_user(d)
    except Exception:
        pass
    return {"found": False}


def summary(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "found": data.get("found", False),
        "full_name": data.get("full_name", ""),
        "location": data.get("location", ""),
        "proofs": [p.get("type", "") for p in data.get("proofs", [])],
    }
