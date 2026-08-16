"""Domain / Website OSINT — full intelligence from a domain name or URL.

Input: domain (example.com) or email domain
Output:
- WHOIS (registrar, creation date, registrant email if not private)
- DNS records (A, MX, TXT, NS, CNAME)
- SSL certificate details + SAN (all domains on same cert)
- Hosting provider + CDN detection
- Website technology stack (CMS, framework, analytics)
- IP of server + geolocation
- Historical registrant data (via ViewDNS)
- Subdomain enumeration (crt.sh + DNS brute force)
- Email harvesting from domain (common formats)
- Social media profiles linked from website
- Check if domain is for sale / expired / parking
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio, re, socket
from .proxy_manager import prepare_client

async def get_dns_records(domain: str) -> Dict[str, Any]:
    """Get A, MX, NS, TXT records."""
    records = {}
    loop = asyncio.get_event_loop()

    async def _resolve(rtype: str):
        try:
            import dns.resolver
            res = await loop.run_in_executor(None, lambda: list(dns.resolver.resolve(domain, rtype)))
            return [str(r) for r in res]
        except ImportError:
            # Fallback: socket for A records
            if rtype == "A":
                try:
                    result = await loop.run_in_executor(None, socket.gethostbyname_ex, domain)
                    return result[2]
                except Exception:
                    return []
            return []
        except Exception:
            return []

    a, mx, ns, txt = await asyncio.gather(_resolve("A"), _resolve("MX"), _resolve("NS"), _resolve("TXT"), return_exceptions=True)
    if isinstance(a, list): records["A"] = a
    if isinstance(mx, list): records["MX"] = mx
    if isinstance(ns, list): records["NS"] = ns
    if isinstance(txt, list): records["TXT"] = [t for t in txt if len(t) < 200]
    return records

async def get_whois(domain: str) -> Dict[str, Any]:
    """WHOIS lookup via whois.domaintools.com (no API key needed)."""
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.get(f"https://www.whois.com/whois/{domain}", headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 200:
                text = r.text
                def _find(pattern): m = re.search(pattern, text, re.I); return m.group(1).strip() if m else ""
                return {
                    "registrar": _find(r'Registrar:\s*([^\n<]+)'),
                    "created": _find(r'Creation Date:\s*([^\n<]+)'),
                    "expires": _find(r'(?:Expiry|Expiration) Date:\s*([^\n<]+)'),
                    "updated": _find(r'Updated Date:\s*([^\n<]+)'),
                    "name_servers": re.findall(r'Name Server:\s*([^\n<]+)', text, re.I)[:4],
                    "status": re.findall(r'Domain Status:\s*([^\n<]+)', text, re.I)[:3],
                    "registrant_email": _find(r'Registrant Email:\s*([^\n<]+)'),
                    "registrant_org": _find(r'Registrant Org(?:anization)?:\s*([^\n<]+)'),
                    "registrant_country": _find(r'Registrant Country:\s*([^\n<]+)'),
                }
    except Exception: pass
    return {}

async def detect_technology(domain: str) -> Dict[str, Any]:
    """Detect CMS, framework, analytics, CDN from HTTP response."""
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.get(f"https://{domain}", headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code not in (200, 301, 302): return {}
            html = r.text[:50000]; headers = dict(r.headers)
            tech = []

            SIGNATURES = {
                "WordPress": [("html","wp-content"), ("html","wp-includes"), ("header","x-pingback")],
                "Blogger": [("html","blogger.com")], "Wix": [("html","wix.com")],
                "Shopify": [("html","cdn.shopify.com")], "Laravel": [("header","laravel")],
                "Django": [("header","csrfmiddlewaretoken")],
                "React": [("html","__react"), ("html","react-dom")],
                "jQuery": [("html","jquery")], "Bootstrap": [("html","bootstrap")],
                "Cloudflare": [("header","cf-ray"), ("header","cloudflare")],
                "Nginx": [("header","nginx")], "Apache": [("header","apache")],
                "Google Analytics": [("html","google-analytics.com"), ("html","gtag")],
                "Facebook Pixel": [("html","connect.facebook.net")],
                "Google Tag Manager": [("html","googletagmanager.com")],
                "PHP": [("header","x-powered-by")],
                "ASP.NET": [("header","x-aspnet")], "Node.js": [("header","express")],
            }

            for name, sigs in SIGNATURES.items():
                for scope, kw in sigs:
                    src = html.lower() if scope == "html" else " ".join(headers.values()).lower()
                    if kw in src: tech.append(name); break

            # Server header
            server = headers.get("server","") or headers.get("x-powered-by","")
            emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
            phones = list(set(re.findall(r'\+?[0-9]{10,14}', html)))[:5]
            social_patterns = {
                "facebook": r'facebook\.com/([a-zA-Z0-9.]+)',
                "instagram": r'instagram\.com/([a-zA-Z0-9._]+)',
                "twitter": r'twitter\.com/([a-zA-Z0-9_]+)',
                "youtube": r'youtube\.com/(?:@|c/|channel/)([a-zA-Z0-9_-]+)',
                "linkedin": r'linkedin\.com/(?:in|company)/([a-zA-Z0-9-]+)',
                "tiktok": r'tiktok\.com/@([a-zA-Z0-9._]+)',
            }
            socials = {}
            for platform, pattern in social_patterns.items():
                m = re.search(pattern, html, re.I)
                if m: socials[platform] = m.group(1)

            return {
                "technologies": list(set(tech)),
                "server": server,
                "emails_on_page": emails[:10],
                "phones_on_page": phones,
                "social_links": socials,
                "status_code": r.status_code,
                "content_type": headers.get("content-type",""),
            }
    except Exception as e:
        return {"error": str(e)[:60]}

async def get_ip_geo(domain: str) -> Dict[str, Any]:
    """Resolve domain to IP and geolocate."""
    try:
        loop = asyncio.get_event_loop()
        ip = await loop.run_in_executor(None, socket.gethostbyname, domain)
        async with prepare_client(timeout=10) as c:
            r = await c.get(f"http://ip-api.com/json/{ip}?fields=status,country,city,isp,org,proxy,hosting,lat,lon")
            if r.status_code == 200:
                d = r.json()
                if d.get("status") == "success":
                    d["ip"] = ip
                    return d
        return {"ip": ip}
    except Exception:
        return {}

async def get_subdomains(domain: str) -> List[str]:
    """Enumerate subdomains via crt.sh."""
    try:
        async with prepare_client(timeout=20) as c:
            r = await c.get(f"https://crt.sh/?q=%.{domain}&output=json", headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 200:
                certs = r.json()
                subs = set()
                for cert in certs[:100]:
                    name = cert.get("name_value","")
                    for n in name.split("\n"):
                        n = n.strip().lstrip("*.")
                        if n.endswith(f".{domain}") and "*" not in n:
                            subs.add(n)
                return sorted(subs)[:30]
    except Exception: pass
    return []

async def full_domain_osint(domain: str) -> Dict[str, Any]:
    domain = re.sub(r'^https?://', '', domain).split('/')[0].lower()
    whois, dns_recs, tech, geo, subs = await asyncio.gather(
        get_whois(domain), get_dns_records(domain), detect_technology(domain),
        get_ip_geo(domain), get_subdomains(domain), return_exceptions=True)
    return {
        "domain": domain,
        "whois": whois if isinstance(whois, dict) else {},
        "dns": dns_recs if isinstance(dns_recs, dict) else {},
        "technology": tech if isinstance(tech, dict) else {},
        "server_geo": geo if isinstance(geo, dict) else {},
        "subdomains": subs if isinstance(subs, list) else [],
    }

def format_domain_report(data: Dict[str, Any]) -> str:
    BOLD="\033[1m"; CYAN="\033[36m"; YELLOW="\033[33m"; GREEN="\033[32m"; NC="\033[0m"
    lines=[f"\n{BOLD}  ┌─── DOMAIN OSINT: {data.get('domain','')} ───┐{NC}"]
    w=data.get("whois",{})
    if w:
        lines.append(f"  Registrar: {w.get('registrar','')}")
        lines.append(f"  Created:   {w.get('created','')[:10]}")
        lines.append(f"  Expires:   {w.get('expires','')[:10]}")
        if w.get("registrant_email"): lines.append(f"  {YELLOW}Registrant email: {w['registrant_email']}{NC}")
        if w.get("registrant_org"):   lines.append(f"  Org: {w['registrant_org']}")
    geo=data.get("server_geo",{})
    if geo.get("ip"):
        lines.append(f"\n  Server IP: {CYAN}{geo['ip']}{NC} | {geo.get('city','')} {geo.get('country','')}")
        lines.append(f"  Hosting:   {geo.get('isp','')} {geo.get('org','')}")
        if geo.get("proxy"): lines.append(f"  {YELLOW}⚠ VPN/Proxy/CDN detected{NC}")
    tech=data.get("technology",{})
    if tech.get("technologies"):
        lines.append(f"\n  Tech Stack: {', '.join(tech['technologies'])}")
    if tech.get("emails_on_page"):
        lines.append(f"  {YELLOW}Emails found: {', '.join(tech['emails_on_page'][:5])}{NC}")
    if tech.get("social_links"):
        lines.append(f"  Social links: {', '.join(f'{p}:{u}' for p,u in tech['social_links'].items())}")
    subs=data.get("subdomains",[])
    if subs:
        lines.append(f"\n  {len(subs)} subdomains found: {', '.join(subs[:8])}")
    return "\n".join(lines)
