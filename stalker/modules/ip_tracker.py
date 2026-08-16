"""IP Tracker & Threat Intelligence Module.

Features:
- IP geolocation (konsensus 8 sumber: 3 DB lokal + 5 API online + resolver wilayah — free, no key)
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
from .ip_intel import reverse_ip_lookup, check_cins_army


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
    """Geolocate IP via konsensus 8 sumber (3 DB lokal + 5 API online + resolver wilayah)."""
    if is_private(ip):
        return {"ip": ip, "private": True, "country": "LAN", "error": "Private IP"}
    try:
        from modules.geoip_consensus import geolocate as _geo

        async with prepare_client(timeout=10) as c:
            async def get_json(url: str):
                r = await c.get(url)
                if r.status_code == 200:
                    return r.json()
                return None

            g = await _geo(ip, get_json)
        if not g:
            return {"ip": ip, "error": "no response"}
        return {
            "ip": ip,
            "country": g.get("country", ""),
            "country_code": g.get("country_code", ""),
            "region": g.get("region", ""),
            "city": g.get("city", ""),
            "zip": g.get("zip", ""),
            "lat": g.get("lat"),
            "lon": g.get("lon"),
            "timezone": g.get("timezone", ""),
            "isp": g.get("isp", ""),
            "org": g.get("org", ""),
            "asn": g.get("asn", ""),
            "as_name": g.get("asn_name", ""),
            "is_mobile": g.get("is_mobile", False),
            "is_proxy": g.get("is_proxy", False),
            "is_hosting": g.get("is_hosting", False),
            "geo_confidence": g.get("geo_confidence"),
            "geo_note": g.get("geo_note", ""),
            "map_url": f"https://www.google.com/maps?q={g.get('lat')},{g.get('lon')}" if g.get('lat') else "",
        }
    except Exception as e:
        return {"ip": ip, "error": str(e)}


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
    """Full IP investigation: geo + shodan + reverse DNS + reverse IP + threat."""
    geo, shodan, reverse_ip, threat = await asyncio.gather(
        geolocate(ip), check_shodan_free(ip), reverse_ip_lookup(ip),
        check_cins_army(ip), return_exceptions=True)

    result = {"ip": ip}
    if isinstance(geo, dict):
        result.update(geo)
    if isinstance(shodan, dict) and shodan:
        result["shodan"] = shodan
    if isinstance(reverse_ip, dict) and reverse_ip:
        result["reverse_ip"] = reverse_ip
    if isinstance(threat, dict) and threat:
        result["threat"] = threat

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
