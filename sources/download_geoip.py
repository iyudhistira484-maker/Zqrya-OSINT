#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download local GeoIP databases (MMDB) for offline lookup.

DB yang didukung (semua gratis, tanpa API key untuk lookup):

  1. DB-IP City Lite   — DOWNLOAD LANGSUNG tanpa akun (default, otomatis)
     https://db-ip.com/db/download/ip-to-city-lite
     URL: https://download.db-ip.com/free/dbip-city-lite-YYYY-MM.mmdb.gz

  2. GeoLite2 City     — butuh license key MaxMind (akun gratis)
     https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/
     Set env: MAXMIND_LICENSE_KEY=xxxxxxxxxxxxxxxx

  3. IP2Location LITE  — butuh token dari email signup
     https://lite.ip2location.com/database/db11-ip-country-region-city-latitude-longitude-zipcode-timezone
     Set env: IP2LOCATION_TOKEN=xxxxxxxxxxxxxxxx

Cara pakai:
    pip install maxminddb requests
    python sources/download_geoip.py                 # unduh DB-IP saja (tanpa akun)
    MAXMIND_LICENSE_KEY=xxx python sources/download_geoip.py --all
    python sources/download_geoip.py --all           # semua yang bisa (key ada atau tidak)

File disimpan ke: data/geoip/  (folder yang dicari modules/geoip_local.py)
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "geoip"

# ── URL sumber ──────────────────────────────────────────────────────
DBIP_BASE = "https://download.db-ip.com/free/dbip-city-lite-{ym}.mmdb.gz"

MAXMIND_URL = ("https://download.maxmind.com/app/geoip_download"
               "?edition_id=GeoLite2-City&license_key={key}&suffix=zip")

IP2LOCATION_URL = ("https://www.ip2location.com/download"
                   "?token={token}&file=DB11LITEBINMMDB")


def _need(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def _fetch(url: str, dest: Path) -> bool:
    """Download url → dest. Returns True on success."""
    import requests
    print(f"  ⬇️  {url}")
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            if r.status_code != 200:
                print(f"     ✗ HTTP {r.status_code}")
                return False
            total = int(r.headers.get("content-length", 0))
            done = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
                    done += len(chunk)
            print(f"     ✓ {done/1e6:.1f} MB → {dest.name}")
            return True
    except Exception as e:
        print(f"     ✗ {e}")
        return False


def _verify(path: Path) -> bool:
    """Cek file benar-benar MMDB yang bisa dibuka."""
    try:
        import maxminddb
        with maxminddb.open_database(str(path)) as db:
            reader = db.get("8.8.8.8")
            ok = reader is not None
            print(f"     ✓ valid MMDB (8.8.8.8 → {reader.get('country', {}).get('names', {}).get('en') if reader else '?'})")
            return ok
    except Exception as e:
        print(f"     ✗ tidak valid: {e}")
        return False


def download_dbip() -> Path | None:
    """DB-IP City Lite — tanpa akun. Coba bulan ini, mundur 3 bulan kalau 404."""
    out = OUT_DIR / "dbip-city-lite.mmdb.gz"
    today = date.today()
    for back in range(0, 4):
        ym = (today - timedelta(days=30 * back)).strftime("%Y-%m")
        url = DBIP_BASE.format(ym=ym)
        print(f"[DB-IP] mencoba rilis {ym}…")
        if _fetch(url, out):
            return out
    print("  ✗ semua rilis DB-IP gagal (jaringan? coba manual di db-ip.com)")
    return None


def download_maxmind(key: str) -> Path | None:
    """GeoLite2 City — butuh license key MaxMind (free account)."""
    print("[GeoLite2] memakai MAXMIND_LICENSE_KEY…")
    tmp = OUT_DIR / "_geolite2.zip"
    if not _fetch(MAXMIND_URL.format(key=key), tmp):
        return None
    try:
        with zipfile.ZipFile(tmp) as z:
            mmdb = next(n for n in z.namelist() if n.endswith(".mmdb"))
            z.extract(mmdb, OUT_DIR)
            dest = OUT_DIR / "GeoLite2-City.mmdb"
            shutil.move(str(OUT_DIR / mmdb), str(dest))
        tmp.unlink(missing_ok=True)
        return dest
    except Exception as e:
        print(f"  ✗ ekstrak gagal: {e}")
        tmp.unlink(missing_ok=True)
        return None


def download_ip2location(token: str) -> Path | None:
    """IP2Location LITE DB11 — butuh token dari email signup."""
    print("[IP2Location] memakai IP2LOCATION_TOKEN…")
    tmp = OUT_DIR / "_ip2l.zip"
    if not _fetch(IP2LOCATION_URL.format(token=token), tmp):
        return None
    try:
        with zipfile.ZipFile(tmp) as z:
            mmdb = next((n for n in z.namelist() if n.endswith(".mmdb")), None)
            if not mmdb:
                print("  ✗ tidak ada .mmdb dalam zip (token salah?)")
                tmp.unlink(missing_ok=True)
                return None
            z.extract(mmdb, OUT_DIR)
            dest = OUT_DIR / "IP2LOCATION-LITE-DB11.MMDB"
            shutil.move(str(OUT_DIR / mmdb), str(dest))
        tmp.unlink(missing_ok=True)
        return dest
    except Exception as e:
        print(f"  ✗ ekstrak gagal: {e}")
        tmp.unlink(missing_ok=True)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Unduh database GeoIP lokal (MMDB)")
    parser.add_argument("--all", action="store_true",
                        help="Unduh semua yang bisa (DB-IP + GeoLite2 + IP2Location, sesuai key)")
    parser.add_argument("--geoip2", action="store_true", help="Unduh GeoLite2 City saja")
    parser.add_argument("--ip2location", action="store_true", help="Unduh IP2Location LITE DB11 saja")
    args = parser.parse_args()

    if not _need("requests"):
        print("❌ Butuh requests:  pip install requests")
        return 1
    if not _need("maxminddb"):
        print("❌ Butuh maxminddb:  pip install maxminddb")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    key_mm = os.getenv("MAXMIND_LICENSE_KEY", "").strip()
    token_i2 = os.getenv("IP2LOCATION_TOKEN", "").strip()

    got = 0
    # DB-IP selalu dicoba (default) kecuali user minta yang spesifik
    if args.geoip2 or args.ip2location and not args.all:
        pass
    else:
        p = download_dbip()
        if p:
            got += 1
            print(f"  ✓ DB-IP → {p}")

    if args.all or args.geoip2:
        if key_mm:
            p = download_maxmind(key_mm)
            if p:
                got += 1
                print(f"  ✓ GeoLite2 → {p}")
        else:
            print("[GeoLite2] lewati — set MAXMIND_LICENSE_KEY untuk mengunduh ini")

    if args.all or args.ip2location:
        if token_i2:
            p = download_ip2location(token_i2)
            if p:
                got += 1
                print(f"  ✓ IP2Location → {p}")
        else:
            print("[IP2Location] lewati — set IP2LOCATION_TOKEN untuk mengunduh ini")

    print()
    print(f"✅ {got} database diunduh ke: {OUT_DIR}")
    if got == 0:
        print("⚠  Tidak ada yang terunduh. Cek jaringan / key di atas.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
