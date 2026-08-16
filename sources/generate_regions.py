#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate `sources/indonesia_regions.json` from upstream open data.

Dataset yang dihasilkan dipakai oleh `modules/indonesia_regions.py` untuk
memetakan nama DESA/KECAMATAN (yang kadang dikembalikan sumber GeoIP) menjadi
KABUPATEN/KOTA yang benar — plus centroid kabupaten untuk memilih ketika nama
tempat ambigu (ada di beberapa kabupaten).

Sumber data (gratis, open data):
  1. Hirarki wilayah + kode Kemendagri:
     https://github.com/cahyadsn/wilayah  ->  db/wilayah.sql
     (Kepmendagri 2025: 38 provinsi, 514 kabupaten/kota,
      7.285 kecamatan, 83.762 desa/kelurahan)
  2. Centroid (titik tengah) 514 kabupaten/kota:
     https://github.com/quarcs-lab/indonesia514
     ->  maps/mapIndonesia514_new_points.geojson

Catatan pemetaan centroid:
  - Dipasangkan ke kode kabupaten (4 digit) Kemendagri terlebih dahulu.
  - Kode yang tidak cocok (kabupaten pemekaran yang nomornya diubah di
    Kepmendagri terbaru, mis. Papua) dipasangkan lewat NAMA kabupaten
    sebagai fallback, sehingga cakupan centroid tetap maksimal.

Hanya pakai standard library Python (tanpa dependensi pihak ketiga).

Cara pakai:
  python sources/generate_regions.py            # download ulang + rebuild
  python sources/generate_regions.py --check    # hanya hitung & validasi (tanpa tulis)
  python sources/generate_regions.py --offline  # pakai file cache lokal (tanpa download)

Output: sources/indonesia_regions.json  (skema lihat modules/indonesia_regions.py)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

# ── Sumber data ────────────────────────────────────────────────────────────
HIERARCHY_URL = (
    "https://raw.githubusercontent.com/cahyadsn/wilayah/master/db/wilayah.sql"
)
CENTROID_URL = (
    "https://raw.githubusercontent.com/quarcs-lab/indonesia514/"
    "main/maps/mapIndonesia514_new_points.geojson"
)

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "indonesia_regions.json"
CACHE_DIR = HERE / ".cache"

# Prefix pada nama kabupaten/kota yang dibuang sebelum dijadikan key lookup.
# Urutan penting: yang lebih panjang dulu (Kota Administrasi sebelum Kota).
KAB_PREFIXES = (
    "Kabupaten Administrasi ",
    "Kota Administrasi ",
    "Kabupaten ",
    "Kota ",
)

# Baris pada wilayah.sql:  ('11.01.02.2018','Pasi Kuala Ba''u')
_ROW_RE = re.compile(r"\(\s*'([0-9.]+)'\s*,\s*'((?:[^']|'')*)'\s*\)")


# ── Util ────────────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    """Normalisasi key lookup: lowercase + gabungkan spasi (sama dgn resolver)."""
    return re.sub(r"\s+", " ", s.strip().lower())


def _strip_kab_prefix(name: str) -> str:
    for p in KAB_PREFIXES:
        if name.startswith(p):
            return name[len(p):]
    return name


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "generate-regions/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())


def _get_source(url: str, cache_name: str, offline: bool) -> bytes:
    """Unduh sumber (atau baca cache lokal). Kembalikan bytes mentah."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache = CACHE_DIR / cache_name
    if not offline:
        try:
            _download(url, cache)
        except Exception as e:
            print(f"[warn] download gagal ({e}); pakai cache kalau ada", file=sys.stderr)
    if cache.exists():
        return cache.read_bytes()
    if offline:
        print(f"[err] mode --offline tapi cache tidak ada: {cache}", file=sys.stderr)
        sys.exit(1)
    return b""


# ── Parser hirarki ──────────────────────────────────────────────────────────
def parse_hierarchy(raw: bytes):
    """Parse wilayah.sql -> (prov, kab, kec, desa).

    prov : {prov_code: nama provinsi (title case)}
    kab  : {kab_code: nama kabupaten (normalized, prefix-stripped)}
    kec  : {kec_code: dict(kab_code, kab, kec, prov)}
    desa : list of dict(kab_code, kab, kec, prov, name)
    """
    text = raw.decode("utf-8", errors="ignore")
    prov: dict = {}
    kab: dict = {}
    kec: dict = {}
    desa: list = []

    for m in _ROW_RE.finditer(text):
        code = m.group(1).replace(".", "")          # '11.01.02.2018' -> '1101022018'
        name = m.group(2).replace("''", "'").strip()

        L = len(code)
        if L == 2:                                  # provinsi
            prov[code] = name
        elif L == 4:                                # kabupaten/kota
            kab[code] = _norm(_strip_kab_prefix(name))
        elif L == 6:                                # kecamatan
            p, k = code[:2], code[:4]
            kec[code] = {
                "kab_code": k,
                "kab": kab.get(k, ""),
                "kec": name,
                "prov": prov.get(p, ""),
            }
        elif L == 10:                               # desa/kelurahan
            p, k, kc = code[:2], code[:4], code[:6]
            desa.append({
                "kab_code": k,
                "kab": kab.get(k, ""),
                "kec": kec.get(kc, {}).get("kec", ""),
                "prov": prov.get(p, ""),
                "name": name,
            })

    return prov, kab, kec, desa


# ── Parser & pemetaan centroid ──────────────────────────────────────────────
def parse_centroids(raw: bytes) -> list:
    """Parse geojson points -> list of dict(code, province, district, lat, lon)."""
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    out = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        code = str(props.get("districtID", "")).replace(".", "").strip()
        lat = props.get("latitude")
        lon = props.get("longitude")
        if code and lat is not None and lon is not None:
            out.append({
                "code": code,
                "province": str(props.get("province", "")),
                "district": str(props.get("district", "")),
                "lat": float(lat),
                "lon": float(lon),
            })
    return out


def match_centroids(prov: dict, kab: dict, entries: list) -> dict:
    """Pasangkan centroid ke kode kabupaten Kemendagri.

    Prioritas: cocokkan kode dulu; kalau tidak ada, cocokkan lewat
    (provinsi, nama kabupaten) yang dinormalisasi. Kembalikan
    {kab_code: [lat, lon]}.
    """
    by_code = {e["code"]: e for e in entries}
    by_name: dict = {}
    for e in entries:
        by_name[(_norm(e["province"]), _norm(_strip_kab_prefix(e["district"])))] = e

    out: dict = {}
    for code, norm_kab_name in kab.items():
        e = by_code.get(code)
        if e is None:
            prov_name = prov.get(code[:2], "")
            e = by_name.get((_norm(prov_name), norm_kab_name))
        if e is not None:
            out[code] = [e["lat"], e["lon"]]
    return out


# ── Build JSON ──────────────────────────────────────────────────────────────
def build(prov: dict, kab: dict, kec: dict, desa: list, centroids: dict) -> dict:
    kabupaten: dict = {}
    kecamatan: dict = {}
    desa_map: dict = {}

    # kabupaten: normalized name -> {prov, kab_code}
    for code, norm_name in kab.items():
        if not norm_name:
            continue
        p_code = code[:2]
        kabupaten[norm_name] = {"prov": prov.get(p_code, ""), "kab_code": code}

    # kecamatan: normalized name -> list of {kab, kab_code, prov}
    for kc in kec.values():
        if not kc.get("kec"):
            continue
        key = _norm(kc["kec"])
        kecamatan.setdefault(key, []).append({
            "kab": kc["kab"],
            "kab_code": kc["kab_code"],
            "prov": kc["prov"],
        })

    # desa: normalized name -> list of {kab, kab_code, kec, prov}
    for d in desa:
        if not d.get("name"):
            continue
        key = _norm(d["name"])
        desa_map.setdefault(key, []).append({
            "kab": d["kab"],
            "kab_code": d["kab_code"],
            "kec": d["kec"],
            "prov": d["prov"],
        })

    return {
        "desa": desa_map,
        "kecamatan": kecamatan,
        "kabupaten": kabupaten,
        "centroid": centroids,
    }


def _atomic_write(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".regions-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate indonesia_regions.json")
    ap.add_argument("--check", action="store_true", help="hitung & validasi saja, tanpa menulis")
    ap.add_argument("--offline", action="store_true", help="pakai cache lokal, tanpa download")
    args = ap.parse_args()

    print("[1/4] Ambil data hirarki wilayah (wilayah.sql) ...")
    sql_raw = _get_source(HIERARCHY_URL, "wilayah.sql", args.offline)
    prov, kab, kec, desa = parse_hierarchy(sql_raw)

    print("[2/4] Ambil centroid kabupaten/kota (geojson) ...")
    geo_raw = _get_source(CENTROID_URL, "mapIndonesia514_new_points.geojson", args.offline)
    centroid_entries = parse_centroids(geo_raw)

    print("[3/4] Bangun dataset ...")
    centroids = match_centroids(prov, kab, centroid_entries)
    data = build(prov, kab, kec, desa, centroids)

    # ── Laporan ─────────────────────────────────────────────────────────────
    n_kab = len(kab)
    n_kec_total = len(kec)
    n_desa_total = len(desa)
    n_kab_uniq = len(data["kabupaten"])
    n_kec_uniq = len(data["kecamatan"])
    n_desa_uniq = len(data["desa"])
    n_centroid = len(centroids)

    print(f"      provinsi        : {len(prov)}")
    print(f"      kabupaten/kota  : {n_kab} (unique key: {n_kab_uniq})")
    print(f"      kecamatan       : {n_kec_total} (unique key: {n_kec_uniq})")
    print(f"      desa/kelurahan  : {n_desa_total} (unique key: {n_desa_uniq})")
    print(f"      centroid        : {n_centroid}/{n_kab}")

    missing_centroid = sorted(set(kab) - set(centroids))
    if missing_centroid:
        print(f"[warn] {len(missing_centroid)} kabupaten tanpa centroid (nama tidak cocok "
              f"dgn sumber): {missing_centroid[:12]}"
              f"{' ...' if len(missing_centroid) > 12 else ''}", file=sys.stderr)

    if n_desa_total < 80_000:
        print("[err] jumlah desa < 80.000 — data hirarki tampak tidak lengkap!",
              file=sys.stderr)
        return 1

    if args.check:
        print("[skip] mode --check, tidak menulis file.")
        return 0

    print(f"[4/4] Tulis {OUTPUT.name} ...")
    _atomic_write(OUTPUT, data)
    size = OUTPUT.stat().st_size / 1_000_000
    print(f"      selesai: {OUTPUT} ({size:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
