#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QR / Barcode decoder — decode QR/barcode from an image file or URL.

Decoding order (no API key needed):
1. Local libraries if installed: OpenCV (cv2) → pyzbar → zxing-cpp.
2. Free API fallback: qrserver.com (POST file / fileurl) → zxing.org.

The decoded payload is classified (URL, email, phone, WiFi, vCard, crypto, dll)
and URLs are expanded (short-link / redirect chain) for phishing triage.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from .proxy_manager import prepare_client


def _local_cv2(path: str) -> Optional[List[str]]:
    try:
        import cv2
        img = cv2.imread(path)
        if img is None:
            return None
        det = cv2.QRCodeDetector()
        data, _, _ = det.detectAndDecode(img)
        return [data] if data else None
    except Exception:
        return None


def _local_pyzbar(path: str) -> Optional[List[str]]:
    try:
        from pyzbar import pyzbar
        from PIL import Image
        img = Image.open(path)
        vals = [d.data.decode("utf-8", "ignore") for d in pyzbar.decode(img)]
        return vals or None
    except Exception:
        return None


def _local_zxing(path: str) -> Optional[List[str]]:
    try:
        import zxingcpp
        vals = [r.text for r in zxingcpp.read_barcodes(path) if r.text]
        return vals or None
    except Exception:
        return None


async def _api_qrserver_file(path: str) -> Optional[List[str]]:
    try:
        import aiohttp
        form = aiohttp.FormData()
        form.add_field("file", open(path, "rb"), filename=Path(path).name)
        async with aiohttp.ClientSession() as s:
            async with s.post("https://api.qrserver.com/v1/read-qr-code/", data=form) as r:
                if r.status == 200:
                    d = await r.json()
                    out = []
                    for item in d:
                        sym = item.get("symbol", [])
                        if sym:
                            out.append(sym[0].get("data", ""))
                    return [x for x in out if x] or None
    except Exception:
        return None
    return None


async def _api_qrserver_url(url: str) -> Optional[List[str]]:
    try:
        from urllib.parse import quote
        async with prepare_client(timeout=15) as c:
            r = await c.get(f"https://api.qrserver.com/v1/read-qr-code/?fileurl={quote(url, safe='')}")
            if r.status_code == 200:
                d = r.json()
                out = []
                for item in d:
                    sym = item.get("symbol", [])
                    if sym:
                        out.append(sym[0].get("data", ""))
                return [x for x in out if x] or None
    except Exception:
        return None
    return None


def classify(text: str) -> Dict:
    """Guess the payload type of decoded QR content."""
    t = (text or "").strip()
    out = {"raw": t, "type": "text", "is_url": False}
    if not t:
        return out
    if re.match(r"^https?://", t, re.I):
        out.update(type="url", is_url=True)
    elif re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", t, re.I):
        out["type"] = "email"
    elif re.match(r"^\+?[0-9\s\-()]{7,15}$", t):
        out["type"] = "phone"
    elif t.upper().startswith("WIFI:"):
        out["type"] = "wifi"
        # parse SSID/pass
        ssid = re.search(r"S:([^;]+)", t, re.I)
        pwd = re.search(r"P:([^;]+)", t, re.I)
        if ssid:
            out["ssid"] = ssid.group(1).strip('"')
        if pwd:
            out["password"] = pwd.group(1).strip('"')
    elif t.upper().startswith(("BEGIN:VCARD", "MECARD:")):
        out["type"] = "vcard"
        name = re.search(r"(?:FN|N):([^;\r\n]+)", t, re.I)
        if name:
            out["name"] = name.group(1)
    elif re.match(r"^(bitcoin:|bc1|[13][a-km-zA-HJ-NP-Z1-9]{25,39}$)", t):
        out["type"] = "crypto"
    elif re.match(r"^geo:", t, re.I):
        out["type"] = "geo"
    elif t.lower().startswith(("tel:", "smsto:", "mailto:")):
        out["type"] = "uri-scheme"
    return out


async def expand_url(url: str, max_hops: int = 5) -> Dict:
    """Follow redirect chain to reveal the final URL (phishing triage)."""
    hops: List[str] = []
    cur = url
    try:
        async with prepare_client(timeout=15, follow_redirects=False) as c:
            for _ in range(max_hops):
                r = await c.get(cur, headers={"User-Agent": "Mozilla/5.0"})
                loc = r.headers.get("location")
                if r.status_code in (301, 302, 303, 307, 308) and loc:
                    hops.append(f"{cur} → {loc}")
                    cur = loc
                else:
                    break
    except Exception as e:
        return {"original": url, "final": cur, "hops": hops, "error": str(e)[:80]}
    return {"original": url, "final": cur, "hops": hops, "resolved": cur != url}


async def decode_qr(source: str) -> Dict:
    """Decode a QR/barcode from a local file path or an image URL."""
    results = None
    method = None

    is_url = re.match(r"^https?://", source, re.I)
    if not is_url:
        p = Path(source)
        if not p.exists():
            return {"source": source, "error": "file tidak ditemukan", "decoded": []}
        for name, fn in (("cv2", _local_cv2), ("pyzbar", _local_pyzbar), ("zxing", _local_zxing)):
            try:
                r = fn(str(p))
                if r:
                    results, method = r, f"local:{name}"
                    break
            except Exception:
                continue
        if results is None:
            results = await _api_qrserver_file(str(p))
            method = "api:qrserver" if results else None
    else:
        results = await _api_qrserver_url(source)
        method = "api:qrserver" if results else None

    if not results:
        return {
            "source": source,
            "decoded": [],
            "method": method,
            "note": "QR tidak terbaca (buram/rusak/bukan QR) atau butuh lib lokal (pip install opencv-python / pyzbar / zxing-cpp)",
        }

    classified = [classify(x) for x in results]
    return {"source": source, "method": method, "decoded": classified}


async def decode_and_expand(source: str) -> Dict:
    """Decode + expand any URL payload (one-shot convenience)."""
    res = await decode_qr(source)
    for item in res.get("decoded", []):
        if item.get("is_url"):
            item["redirect"] = await expand_url(item["raw"])
    return res
