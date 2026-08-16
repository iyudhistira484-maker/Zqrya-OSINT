"""Deteksi Linktree, Bio.site, Carrd.co."""
import re
import aiohttp
from stalker.reporters import terminal as term

async def check_link_aggregators(username: str) -> dict:
    """Cek keberadaan dan ambil link dari aggregator."""
    platforms = [
        {"name": "Linktree", "url": f"https://linktr.ee/{username}"},
        {"name": "Bio.site", "url": f"https://bio.site/{username}"},
        {"name": "Carrd", "url": f"https://{username}.carrd.co"},
    ]
    found = {}
    for p in platforms:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(p["url"], timeout=10) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html)
                        found[p["name"]] = {"url": p["url"], "links": links[:20]}
                    else:
                        found[p["name"]] = {"url": p["url"], "status": resp.status}
        except Exception as e:
            found[p["name"]] = {"url": p["url"], "error": str(e)}
    return found
