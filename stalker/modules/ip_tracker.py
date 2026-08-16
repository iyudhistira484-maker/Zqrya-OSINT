"""IP Tracker & Threat Intelligence Module.

Features:
- IP geolocation (ip-api.com - free, no key)
- ASN / ISP info
- Threat intelligence (AbuseIPDB public check)
- Reverse DNS lookup
- Tor/VPN/Proxy detection
- Extract IPs from text (bios, profiles)
- Termux-compatible (pure Python, no C deps)
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio
import re
import socket
import ipaddress
import httpx
from .proxy_manager import prepare_client


IP_RE = re.compile(
    r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
)

PRIVATE_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
]


def is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in PRIVATE_RANGES)
    except ValueError:
        return False


async def geolocate(ip: str) -> Dict[str, Any]:
    """Geolocate IP via ip-api.com (free, 45 req/min, no key needed)."""
    if is_private(ip):
        return {"ip": ip, "private": True, "country": "LAN", "error": "Private IP"}
    try:
        async with prepare_client(timeout=10) as c:
            fields = "status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,reverse,mobile,proxy,hosting,query"
            r = await c.get(f"http://ip-api.com/json/{ip}?fields={fields}")
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    return {
                        "ip": ip,
                        "country": data.get("country", ""),
                        "country_code": data.get("countryCode", ""),
                        "region": data.get("regionName", ""),
                        "city": data.get("city", ""),
                        "zip": data.get("zip", ""),
                        "lat": data.get("lat"),
                        "lon": data.get("lon"),
                        "timezone": data.get("timezone", ""),
                        "isp": data.get("isp", ""),
                        "org": data.get("org", ""),
                        "asn": data.get("as", ""),
                        "as_name": data.get("asname", ""),
                        "reverse_dns": data.get("reverse", ""),
                        "is_mobile": data.get("mobile", False),
                        "is_proxy": data.get("proxy", False),
                        "is_hosting": data.get("hosting", False),
                        "map_url": f"https://www.google.com/maps?q={data.get('lat')},{data.get('lon')}",
                    }
                return {"ip": ip, "error": data.get("message", "failed")}
    except Exception as e:
        return {"ip": ip, "error": str(e)}
    return {"ip": ip, "error": "no response"}


async def reverse_dns(ip: str) -> str:
    """Reverse DNS lookup for an IP."""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
        return result[0]
    except Exception:
        return ""


async def check_shodan_free(ip: str) -> Dict[str, Any]:
    """Check Shodan InternetDB (free, no key, returns open ports + vulns)."""
    if is_private(ip):
        return {}
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get(f"https://internetdb.shodan.io/{ip}")
            if r.status_code == 200:
                data = r.json()
                return {
                    "open_ports": data.get("ports", []),
                    "hostnames": data.get("hostnames", []),
                    "tags": data.get("tags", []),
                    "vulns": data.get("vulns", []),
                    "cpes": data.get("cpes", []),
                }
            elif r.status_code == 404:
                return {"open_ports": [], "note": "Not in Shodan"}
    except Exception:
        pass
    return {}


async def get_my_ip() -> str:
    """Get current public IP address."""
    for url in ["https://api.ipify.org", "https://checkip.amazonaws.com", "https://ipecho.net/plain"]:
        try:
            async with prepare_client(timeout=8) as c:
                r = await c.get(url)
                if r.status_code == 200:
                    return r.text.strip()
        except Exception:
            continue
    return ""


def extract_ips_from_text(text: str) -> List[str]:
    """Extract all public IP addresses from text."""
    found = IP_RE.findall(text)
    return [ip for ip in set(found) if not is_private(ip)]


async def track_ip(ip: str) -> Dict[str, Any]:
    """Full IP investigation: geo + shodan + reverse DNS."""
    geo_task = geolocate(ip)
    shodan_task = check_shodan_free(ip)
    geo, shodan = await asyncio.gather(geo_task, shodan_task, return_exceptions=True)

    result = {"ip": ip}
    if isinstance(geo, dict):
        result.update(geo)
    if isinstance(shodan, dict) and shodan:
        result["shodan"] = shodan

    rdns = result.get("reverse_dns", "")
    if not rdns and not is_private(ip):
        rdns = await reverse_dns(ip)
        result["reverse_dns"] = rdns

    return result


async def track_multiple(ips: List[str]) -> Dict[str, Dict[str, Any]]:
    """Track multiple IPs in parallel."""
    tasks = [track_ip(ip) for ip in ips[:10]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        ip: (r if isinstance(r, dict) else {"ip": ip, "error": str(r)})
        for ip, r in zip(ips, results)
    }


def summary(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    countries = list(set(r.get("country", "") for r in results.values() if r.get("country")))
    proxies = [ip for ip, r in results.items() if r.get("is_proxy")]
    hosting = [ip for ip, r in results.items() if r.get("is_hosting")]
    with_vulns = [ip for ip, r in results.items() if r.get("shodan", {}).get("vulns")]
    return {
        "total_ips": len(results),
        "countries": countries,
        "proxy_ips": proxies,
        "hosting_ips": hosting,
        "vulnerable_ips": with_vulns,
    }
