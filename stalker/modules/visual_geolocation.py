#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Visual Geolocation Assistant — bantu tentukan lokasi dari foto.

Alur (keyless):
1. GPS dari EXIF (PIL) → koordinat + link peta.
2. Tanpa GPS → reverse image search (Yandex/Google Lens/TinEye) + petunjuk lokasi.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List
from urllib.parse import quote


def _to_deg(val) -> float:
    """Convert EXIF rational (fraction/tuple) to float degrees."""
    try:
        if hasattr(val, "numerator") and hasattr(val, "denominator"):
            return float(val.numerator) / float(val.denominator)
        if isinstance(val, (tuple, list)) and len(val) == 2:
            return float(val[0]) / float(val[1])
        return float(val)
    except Exception:
        return 0.0


def extract_gps(image_path: str) -> Dict:
    """Extract GPS coordinates from EXIF (PIL, if available)."""
    p = Path(image_path)
    out: Dict = {"source": str(p), "found": False}
    if not p.exists():
        out["error"] = "file tidak ditemukan"
        return out
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
    except ImportError:
        out["error"] = "Pillow tidak terpasang (pip install Pillow)"
        return out

    try:
        img = Image.open(p)
        exif = img._getexif() or {}
    except Exception as e:
        out["error"] = f"tidak bisa baca EXIF: {e}"
        return out

    gps = None
    for tag, value in exif.items():
        name = TAGS.get(tag, tag)
        if name == "GPSInfo":
            gps = {GPSTAGS.get(k, k): v for k, v in value.items()}
            break
    if not gps:
        out["error"] = "tidak ada GPS di EXIF (metadata kemungkinan dihapus)"
        return out

    try:
        lat = _to_deg(gps.get("GPSLatitude", (0, 0, 0))[0]) + \
              _to_deg(gps.get("GPSLatitude", (0, 0, 0))[1]) / 60 + \
              _to_deg(gps.get("GPSLatitude", (0, 0, 0))[2]) / 3600
        lon = _to_deg(gps.get("GPSLongitude", (0, 0, 0))[0]) + \
              _to_deg(gps.get("GPSLongitude", (0, 0, 0))[1]) / 60 + \
              _to_deg(gps.get("GPSLongitude", (0, 0, 0))[2]) / 3600
        if str(gps.get("GPSLatitudeRef", "N")).upper() == "S":
            lat = -lat
        if str(gps.get("GPSLongitudeRef", "E")).upper() == "W":
            lon = -lon
        out["found"] = True
        out["lat"] = round(lat, 6)
        out["lon"] = round(lon, 6)
        out["map_url"] = f"https://www.google.com/maps?q={lat},{lon}"
    except Exception as e:
        out["error"] = f"gagal parse GPS: {e}"
    return out


def reverse_search_links(image_url: str) -> List[Dict]:
    """Generate reverse-image-search links (butuh URL publik; file lokal upload manual)."""
    q = quote(image_url, safe="")
    return [
        {"engine": "Yandex", "url": f"https://yandex.com/images/search?rpt=imageview&url={q}"},
        {"engine": "Google Lens", "url": f"https://lens.google.com/uploadbyurl?url={q}"},
        {"engine": "TinEye", "url": f"https://tineye.com/search?url={q}"},
        {"engine": "Bing", "url": f"https://www.bing.com/images/search?q=imgurl:{q}&view=detailv2"},
    ]


def _location_hints(text: str) -> List[str]:
    """Surface place-like tokens from arbitrary text (best-effort)."""
    hints = []
    for m in re.finditer(r"(?:in|at|near|located in)\s+([A-Z][A-Za-z ,'-]{2,40})", text):
        hints.append(m.group(1).strip())
    coords = re.findall(r"(-?\d{1,2}\.\d{2,6})\s*,\s*(-?\d{1,3}\.\d{2,6})", text)
    for lat, lon in coords[:3]:
        hints.append(f"{lat},{lon}")
    return list(dict.fromkeys(hints))[:8]


async def _gps_from_url(image_url: str) -> Dict:
    """Download image URL → temp file → extract GPS via Pillow (gratis, tanpa key)."""
    import asyncio
    import tempfile
    try:
        from .proxy_manager import prepare_client
        from pathlib import Path as _P
    except ImportError:
        return {"found": False, "error": "proxy_manager tidak tersedia"}
    try:
        async with prepare_client(timeout=20, follow_redirects=True) as c:
            r = await c.get(image_url)
            if r.status_code != 200:
                return {"found": False, "error": f"HTTP {r.status_code}"}
            suffix = _P(image_url.split("?")[0]).suffix.lower() or ".jpg"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(r.content)
                path = tmp.name
        try:
            return extract_gps(path)
        finally:
            try:
                _P(path).unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as e:
        return {"found": False, "error": str(e)[:100]}


async def geolocate_image(source: str) -> Dict:
    """Assist geolocation: EXIF GPS first (file lokal ATAU URL), then reverse-search links + hints."""
    p = Path(source)
    out: Dict = {"source": source}
    if p.exists():
        gps = extract_gps(str(p))
    elif re.match(r"^https?://", source, re.I):
        gps = await _gps_from_url(source)
    else:
        gps = {"found": False, "error": "bukan file lokal"}

    if gps.get("found"):
        out["gps"] = gps
        out["verdict"] = "gps"
        out["map_url"] = gps["map_url"]
        return out

    # Tanpa GPS → reverse search (butuh URL publik)
    out["gps"] = gps
    out["verdict"] = "heuristic"
    if re.match(r"^https?://", source, re.I):
        out["reverse_search_links"] = reverse_search_links(source)
    else:
        out["note"] = (
            "File lokal tidak bisa di-reverse-search langsung. Upload dulu ke "
            "imgur.com (atau host publik), lalu pakai URL-nya, atau jalankan: "
            "stalker reverseimg <file>"
        )
    out["location_hints"] = []
    out["manual_tip"] = (
        "Petunjuk visual: rambu jalan, plat kendaraan, bahasa papan nama, "
        "arsitektur, arah bayangan (matahari), dan vegetation — kunci OSINT geolokasi."
    )
    return out


def summary(res: Dict) -> Dict:
    gps = res.get("gps", {})
    return {
        "verdict": res.get("verdict"),
        "gps_found": gps.get("found", False),
        "lat": gps.get("lat"),
        "lon": gps.get("lon"),
        "map_url": res.get("map_url") or gps.get("map_url"),
    }
