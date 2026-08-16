"""FlareSolverr manager — detect if FlareSolverr is running.

Provides Cloudflare bypass configuration to Maigret.
"""

from __future__ import annotations
from typing import Optional, Dict, Any

import httpx

FLARESOLVERR_PORT = 8191
FLARESOLVERR_URL = f"http://localhost:{FLARESOLVERR_PORT}/v1"


async def detect() -> Optional[Dict[str, Any]]:
    """Check if FlareSolverr is running. Returns CF bypass config dict or None."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.post(
                FLARESOLVERR_URL,
                json={"cmd": "sessions.list"},
            )
            if resp.status_code == 200:
                return {
                    "trigger_protection": ["cf_js_challenge", "cf_firewall", "webgate"],
                    "modules": [
                        {
                            "name": "flaresolverr",
                            "method": "json_api",
                            "url": FLARESOLVERR_URL,
                            "max_timeout_ms": 60000,
                        }
                    ],
                    "session_prefix": "stalker_",
                }
    except Exception:
        pass
    return None
