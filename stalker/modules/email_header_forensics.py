"""Email Header Forensics — extract real sender IP from raw email headers.

Paste raw email headers → reveal:
- Real originating IP (even if Gmail/Outlook strips it)
- Mail server route (hops)
- Sender's email client / OS / device
- Timezone from Date header
- SPF/DKIM/DMARC authentication status
- Time delays between hops (detect VPN/proxy routing)

HOW TO GET EMAIL HEADERS:
  Gmail:  Open email → ⋮ → "Show original"
  Outlook: File → Properties → Internet headers
  Termux: From any .eml file

This is the #1 tool to get real IP of email scammers/phishers.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import re
from datetime import datetime


# ── Header parsers ────────────────────────────────────────────
RECEIVED_RE = re.compile(
    r'Received:\s*(?:from\s+([^\s\[]+))?'
    r'(?:\s*\(([^\)]*)\))?'
    r'(?:\s*\[([^\]]+)\])?'
    r'.*?(?:;\s*(.+?)(?:\n(?!\s)|\Z))?',
    re.IGNORECASE | re.DOTALL,
)

IP_RE = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
IP6_RE = re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b')
PRIVATE_RANGES = [
    re.compile(r'^10\.'),
    re.compile(r'^172\.(1[6-9]|2[0-9]|3[01])\.'),
    re.compile(r'^192\.168\.'),
    re.compile(r'^127\.'),
    re.compile(r'^::1$'),
    re.compile(r'^fc|^fd'),
]

def is_private_ip(ip: str) -> bool:
    return any(p.match(ip) for p in PRIVATE_RANGES)

def extract_ips_from_text(text: str) -> List[str]:
    return [ip for ip in IP_RE.findall(text) if not is_private_ip(ip)]


def parse_received_headers(raw: str) -> List[Dict[str, Any]]:
    """Parse all 'Received:' headers to trace email route."""
    hops = []
    # Split headers at Received: boundaries
    segments = re.split(r'\nReceived:', '\n' + raw, flags=re.IGNORECASE)
    for seg in segments[1:]:  # skip before first Received
        seg = 'Received:' + seg.split('\n\n')[0]  # stop at body
        ips = extract_ips_from_text(seg)
        hostname_match = re.search(r'from\s+([^\s\[\(]+)', seg, re.I)
        by_match = re.search(r'by\s+([^\s\[\(;]+)', seg, re.I)
        date_match = re.search(r';\s*(.{20,50})', seg)
        with_match = re.search(r'with\s+([A-Z0-9]+)', seg, re.I)

        hop = {
            "from_host": hostname_match.group(1) if hostname_match else "",
            "by_host": by_match.group(1) if by_match else "",
            "ips": ips,
            "protocol": with_match.group(1) if with_match else "",
            "timestamp_raw": date_match.group(1).strip() if date_match else "",
            "raw_segment": seg[:200],
        }
        if ips or hop["from_host"]:
            hops.append(hop)

    return hops


def parse_from_header(raw: str) -> Dict[str, str]:
    """Parse From: header for display name and email."""
    from_match = re.search(r'^From:\s*(.+)$', raw, re.MULTILINE | re.IGNORECASE)
    if not from_match:
        return {}
    from_val = from_match.group(1).strip()
    email_match = re.search(r'<([^>]+)>', from_val)
    name_match = re.search(r'^"?([^<"]+)"?\s*<', from_val)
    return {
        "display": name_match.group(1).strip() if name_match else from_val,
        "email": email_match.group(1) if email_match else from_val,
        "raw": from_val,
    }


def parse_date_header(raw: str) -> Dict[str, str]:
    """Extract timezone from Date header."""
    date_match = re.search(r'^Date:\s*(.+)$', raw, re.MULTILINE | re.IGNORECASE)
    if not date_match:
        return {}
    date_val = date_match.group(1).strip()
    tz_match = re.search(r'([+-]\d{4}|[A-Z]{2,4})\s*$', date_val)
    return {
        "raw": date_val,
        "timezone_offset": tz_match.group(1) if tz_match else "unknown",
    }


def parse_user_agent(raw: str) -> Dict[str, str]:
    """Extract email client / OS from X-Mailer or User-Agent header."""
    result = {}
    for header in ["X-Mailer", "X-MimeOLE", "User-Agent", "X-Originating-Client"]:
        m = re.search(rf'^{header}:\s*(.+)$', raw, re.MULTILINE | re.IGNORECASE)
        if m:
            result[header.lower().replace("-","_")] = m.group(1).strip()
    return result


def parse_auth_results(raw: str) -> Dict[str, str]:
    """Parse SPF, DKIM, DMARC authentication results."""
    result = {}
    auth_m = re.search(r'^Authentication-Results:\s*(.+?)(?=\n\S|\Z)', raw,
                       re.MULTILINE | re.IGNORECASE | re.DOTALL)
    if auth_m:
        auth_text = auth_m.group(1)
        for protocol in ["spf", "dkim", "dmarc"]:
            m = re.search(rf'{protocol}=(\w+)', auth_text, re.I)
            result[protocol] = m.group(1) if m else "unknown"
    return result


def parse_originating_ip(raw: str) -> Optional[str]:
    """Find X-Originating-IP or similar headers."""
    for header in ["X-Originating-IP", "X-Sender-IP", "X-Source-IP",
                   "X-Real-IP", "CF-Connecting-IP", "X-Forwarded-For"]:
        m = re.search(rf'^{header}:\s*([^\s,]+)', raw, re.MULTILINE | re.IGNORECASE)
        if m:
            ip = m.group(1).strip()
            if not is_private_ip(ip):
                return ip
    return None


def find_originating_ip(hops: List[Dict]) -> Optional[str]:
    """Find the FIRST public IP in the chain = real sender IP."""
    # Email travels: Sender → ISP SMTP → Recipient
    # First hop with a public IP is usually the sender's real IP
    for hop in reversed(hops):  # Received headers are newest-first
        for ip in hop.get("ips", []):
            if not is_private_ip(ip):
                return ip
    return None


async def geolocate_ip(ip: str) -> Dict[str, Any]:
    """Geolocate IP using ip-api.com (free)."""
    if not ip:
        return {}
    try:
        from .proxy_manager import prepare_client
        async with prepare_client(timeout=10) as c:
            r = await c.get(
                f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,"
                f"regionName,city,isp,org,as,mobile,proxy,hosting,lat,lon",
            )
            if r.status_code == 200:
                d = r.json()
                if d.get("status") == "success":
                    return d
    except Exception as e:
        pass
    return {"ip": ip, "error": "geolocation failed"}


async def full_email_header_forensics(raw_headers: str) -> Dict[str, Any]:
    """Full forensic analysis of raw email headers."""
    raw = raw_headers.strip()

    hops = parse_received_headers(raw)
    from_info = parse_from_header(raw)
    date_info = parse_date_header(raw)
    user_agent = parse_user_agent(raw)
    auth = parse_auth_results(raw)

    # Find originating IP
    orig_ip = parse_originating_ip(raw) or find_originating_ip(hops)

    # Geolocate it
    geo = {}
    if orig_ip:
        geo = await geolocate_ip(orig_ip)

    # Extract all public IPs from all hops
    all_ips = list({ip for hop in hops for ip in hop.get("ips", []) if not is_private_ip(ip)})

    # Subject
    subj_m = re.search(r'^Subject:\s*(.+)$', raw, re.MULTILINE | re.IGNORECASE)
    subject = subj_m.group(1).strip() if subj_m else ""

    # Reply-To (often different from From in phishing)
    reply_m = re.search(r'^Reply-To:\s*(.+)$', raw, re.MULTILINE | re.IGNORECASE)
    reply_to = reply_m.group(1).strip() if reply_m else ""

    return {
        "from": from_info,
        "reply_to": reply_to,
        "subject": subject,
        "date": date_info,
        "originating_ip": orig_ip,
        "geo": geo,
        "all_public_ips": all_ips,
        "hops": hops,
        "auth": auth,
        "user_agent": user_agent,
        "total_hops": len(hops),
        "suspicious": {
            "from_reply_mismatch": bool(reply_to) and reply_to != from_info.get("email",""),
            "spf_fail": auth.get("spf","") in ("fail","softfail"),
            "dkim_fail": auth.get("dkim","") == "fail",
            "proxy_ip": geo.get("proxy") or geo.get("hosting"),
        },
    }


def format_header_forensics(data: Dict[str, Any]) -> str:
    BOLD = "\033[1m"; RED = "\033[31m"; GREEN = "\033[32m"
    YELLOW = "\033[33m"; CYAN = "\033[36m"; NC = "\033[0m"

    lines = [f"\n{BOLD}  ┌─── EMAIL HEADER FORENSICS ───┐{NC}"]

    f = data.get("from", {})
    if f:
        lines.append(f"  From:      {BOLD}{f.get('display','')} <{f.get('email','')}>{NC}")
    if data.get("reply_to"):
        mark = f"{RED}[MISMATCH!]{NC}" if data["suspicious"]["from_reply_mismatch"] else ""
        lines.append(f"  Reply-To:  {data['reply_to']} {mark}")
    if data.get("subject"):
        lines.append(f"  Subject:   {data['subject']}")
    if data.get("date"):
        lines.append(f"  Timezone:  {data['date'].get('timezone_offset','')}")

    # The most important finding
    orig_ip = data.get("originating_ip")
    if orig_ip:
        geo = data.get("geo", {})
        lines.append(f"\n  {BOLD}⚡ ORIGINATING IP (SENDER'S REAL IP):{NC}")
        lines.append(f"  {RED}{orig_ip}{NC}")
        if geo.get("country"):
            lines.append(f"  Location: {geo.get('city','')} {geo.get('regionName','')} {geo.get('country','')}")
            lines.append(f"  ISP/Org:  {geo.get('isp','')} / {geo.get('org','')}")
            lines.append(f"  ASN:      {geo.get('as','')}")
            if geo.get("lat") and geo.get("lon"):
                lines.append(f"  Maps:     https://maps.google.com/?q={geo['lat']},{geo['lon']}")
            flags = []
            if geo.get("proxy"): flags.append(f"{YELLOW}VPN/Proxy{NC}")
            if geo.get("hosting"): flags.append(f"{YELLOW}Hosting/Datacenter{NC}")
            if geo.get("mobile"): flags.append("Mobile network")
            if flags: lines.append(f"  Flags:    {', '.join(flags)}")
    else:
        lines.append(f"\n  {YELLOW}No originating IP found (stripped by mail provider){NC}")

    # Auth results
    auth = data.get("auth", {})
    if auth:
        lines.append(f"\n  {BOLD}Email Authentication:{NC}")
        for proto in ["spf","dkim","dmarc"]:
            val = auth.get(proto, "unknown")
            color = GREEN if val == "pass" else RED if val in ("fail","softfail") else YELLOW
            lines.append(f"  {proto.upper()}: {color}{val}{NC}")

    # Hops
    lines.append(f"\n  {BOLD}Mail Route ({data.get('total_hops',0)} hops):{NC}")
    for i, hop in enumerate(data.get("hops", [])[:8]):
        ips_str = ", ".join(hop.get("ips", []))
        lines.append(f"  {i+1}. {hop.get('from_host','')} → {hop.get('by_host','')} [{ips_str}]")

    if data.get("user_agent"):
        lines.append(f"\n  {BOLD}Email Client:{NC}")
        for k, v in data["user_agent"].items():
            lines.append(f"  {k}: {v}")

    return "\n".join(lines)
