"""Breach check — Hudson Rock infostealer intelligence + HIBP email lookup.

Free APIs, httpx only, no extra deps.
"""

from __future__ import annotations
from typing import Dict, Any
import httpx
from .proxy_manager import prepare_client

HUDSON_ROCK_API = "https://cavalier.hudsonrock.com/api/json/v2/osint-tools"


async def check_hudson_rock(username: str = "", email: str = "") -> Dict[str, Any]:
    """Query Hudson Rock for infostealer infection data.

    Uses the free OSINT API — no API key needed.
    """
    results = {}
    async with prepare_client(timeout=15) as client:
        if email:
            url = f"{HUDSON_ROCK_API}/search-by-email?email={email}"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    stealers = data.get("stealers", [])
                    results["email"] = {
                        "total_infections": len(stealers),
                        "infections": [
                            {
                                "stealer_family": s.get("stealer_family", "?"),
                                "date_compromised": s.get("date_compromised", "?"),
                                "os": s.get("operating_system", "?"),
                                "computer_name": s.get("computer_name", "?"),
                                "antiviruses": s.get("antiviruses", []),
                                "logins": s.get("top_logins", [])[:5],
                            }
                            for s in stealers[:10]
                        ],
                    }
                else:
                    results["email"] = {"total_infections": 0, "infections": [], "error": f"HTTP {resp.status_code}"}
            except Exception as e:
                results["email"] = {"total_infections": 0, "infections": [], "error": str(e)}

        if username:
            url = f"{HUDSON_ROCK_API}/search-by-username?username={username}"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    stealers = data.get("stealers", [])
                    results["username"] = {
                        "total_infections": len(stealers),
                        "infections": [
                            {
                                "stealer_family": s.get("stealer_family", "?"),
                                "date_compromised": s.get("date_compromised", "?"),
                                "os": s.get("operating_system", "?"),
                            }
                            for s in stealers[:10]
                        ],
                    }
                else:
                    results["username"] = {"total_infections": 0, "infections": [], "error": f"HTTP {resp.status_code}"}
            except Exception as e:
                results["username"] = {"total_infections": 0, "infections": [], "error": str(e)}

    return results
