"""Certificate Transparency Lookup — crt.sh domain/email intelligence.

From an email domain or username, find:
- All SSL certificates issued (reveals subdomains, org names)
- Organization name from cert (real company name)
- Issuer (Let's Encrypt = personal/small site, DigiCert = corp)
- SAN (Subject Alternative Names = all domains covered)
- First/last certificate dates

No API key needed — crt.sh is fully public.
"""
from __future__ import annotations
from typing import Dict, Any, List
import asyncio
from .proxy_manager import prepare_client

CRT_API = "https://crt.sh"

async def search_domain(domain: str) -> List[Dict[str, Any]]:
    """Search crt.sh for certificates issued for a domain."""
    try:
        async with prepare_client(timeout=20) as c:
            r = await c.get(f"{CRT_API}/?q=%.{domain}&output=json", headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                certs = r.json()
                seen = set()
                results = []
                for cert in certs[:50]:
                    name = cert.get("name_value","").strip()
                    if name and name not in seen:
                        seen.add(name)
                        results.append({
                            "domain": name,
                            "issuer": cert.get("issuer_name",""),
                            "not_before": cert.get("not_before","")[:10],
                            "not_after": cert.get("not_after","")[:10],
                            "id": cert.get("id",""),
                        })
                return results
    except Exception: pass
    return []

async def search_email_domain(email: str) -> Dict[str, Any]:
    """Get certificate intelligence from email domain."""
    domain = email.split("@")[-1]
    certs = await search_domain(domain)
    subdomains = list(set(c["domain"] for c in certs if not c["domain"].startswith("*")))
    wildcards = [c["domain"] for c in certs if c["domain"].startswith("*")]
    issuers = list(set(c["issuer"] for c in certs if c.get("issuer")))
    return {
        "domain": domain, "total_certs": len(certs),
        "subdomains": sorted(subdomains)[:20],
        "wildcards": wildcards[:5], "issuers": issuers[:5],
        "first_cert": min((c["not_before"] for c in certs if c.get("not_before")), default=""),
        "last_cert": max((c["not_after"] for c in certs if c.get("not_after")), default=""),
    }

def summary(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "domain": data.get("domain",""), "total_certs": data.get("total_certs",0),
        "subdomains_count": len(data.get("subdomains",[])),
        "first_cert": data.get("first_cert",""),
    }
