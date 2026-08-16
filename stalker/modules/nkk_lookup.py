#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NKK / Kartu Keluarga lookup — parse & validate Indonesian Family Card number.

Mirror of NIK lookup, tapi untuk Nomor Kartu Keluarga (16 digit).

Struktur NKK (16 digit):
  PP KK BB - DDMMYY - SSSS
  PP = kode provinsi, KK = kode kab/kota, BB = kode kecamatan,
  DDMMYY = tanggal penerbitan/pencatatan KK,
  SSSS = nomor urut keluarga (serial).

Catatan jujur:
- NKK TIDAK mengandung tanggal lahir/gender anggota (beda dengan NIK).
- Anggota keluarga (NIK, nama, status kawin, dll) hanya bisa didapat dari
  database lokal (SIAK) jika tersedia — bukan dari angka NKK itu sendiri.
- Status "masih hidup/aktif" tidak bisa diverifikasi dari sumber publik;
  yang bisa diberi hanya indikasi struktural + tautan cek manual.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Optional

# Pakai data wilayah yang sama dengan NIK (indonesia_regions.json)
from .nik_lookup import PROVINCE_CODES, _load_kab_map, _title


def clean_nkk(nkk: str) -> str:
    """Strip non-digit characters."""
    return re.sub(r"[^0-9]", "", nkk or "")


def parse_nkk(nkk: str) -> Dict:
    """Parse a 16-digit NKK into its components.

    Always returns a dict; `valid` indicates structural soundness.
    """
    raw = clean_nkk(nkk)
    out: Dict = {
        "nkk": raw,
        "valid": False,
        "issue_date": None,
        "province_code": raw[:2] if len(raw) >= 2 else "",
        "province": None,
        "kab_code": raw[:4] if len(raw) >= 4 else "",
        "kabupaten": None,
        "kec_code": raw[:6] if len(raw) >= 6 else "",
        "serial": raw[12:16] if len(raw) >= 16 else "",
        "errors": [],
    }

    if len(raw) != 16 or not raw.isdigit():
        out["errors"].append("NKK harus 16 digit angka")
        return out

    prov_code = raw[:2]
    kab_code = raw[:4]
    day = int(raw[6:8])
    month = int(raw[8:10])
    year2 = int(raw[10:12])

    # Provinsi
    prov = PROVINCE_CODES.get(prov_code)
    out["province"] = prov
    if not prov:
        out["errors"].append(f"kode provinsi tidak dikenal: {prov_code}")

    # Kab/kota
    kab = _load_kab_map().get(kab_code)
    if kab:
        out["kabupaten"] = _title(kab.get("kab", ""))
        if not prov:
            out["province"] = kab.get("prov")
    else:
        out["errors"].append(f"kode kabupaten/kota tidak dikenal: {kab_code}")

    # Tanggal penerbitan KK (DDMMYY) — tanpa aturan gender (beda NIK)
    cur_yy = int(datetime.now().strftime("%y"))
    year = 2000 + year2 if year2 <= cur_yy else 1900 + year2
    out["issue_year"] = year

    if not (1 <= month <= 12):
        out["errors"].append(f"bulan tidak valid: {month}")
    if not (1 <= day <= 31):
        out["errors"].append(f"tanggal tidak valid: {day}")

    try:
        dt = datetime(year, month, day)
        out["issue_date"] = dt.strftime("%Y-%m-%d")
        out["issue_date_iso"] = dt.isoformat()
    except ValueError:
        out["errors"].append("tanggal penerbitan tidak valid (kombinasi hari/bulan)")

    out["valid"] = not out["errors"]
    return out


def validate_nkk(nkk: str) -> Dict:
    """Full structural validation (same as parse_nkk but returns a clear verdict)."""
    res = parse_nkk(nkk)
    verdict = "valid" if res.get("valid") else "invalid"
    return {
        "nkk": res.get("nkk"),
        "verdict": verdict,
        "valid": res.get("valid"),
        "errors": res.get("errors", []),
        "detail": res,
    }


async def check_active(nkk: str) -> Dict:
    """Cek status NKK: indikasi struktural + tautan verifikasi manual.

    Jujur: status hidup/aktif kartu TIDAK bisa dicek dari sumber publik.
    Yang bisa diberi: validitas struktural + tautan resmi untuk cek manual.
    """
    res = parse_nkk(nkk)
    active = res.get("valid", False)
    return {
        "nkk": res.get("nkk"),
        "structurally_valid": active,
        "likely_active": active,
        "manual_check": {
            "dukcapil": "https://dukcapil.kemendagri.go.id",
            "bpjs": "https://bpjs-kesehatan.go.id",
        },
    }


def search_family(nkk: str) -> Dict:
    """Cari anggota keluarga by NKK di database lokal (SIAK dll).

    Returns {db: [anggota]} — tiap anggota berisi NIK, nama, status kawin,
    dll. Kosong kalau DB tidak tersedia atau tidak punya kolom NKK.
    """
    nkk = clean_nkk(nkk)
    if len(nkk) < 10:
        return {}
    try:
        from .localdb import search_by_nkk
        return search_by_nkk(nkk)
    except Exception:
        return {}


def summary(res: Dict) -> Dict:
    """Compact summary for reports."""
    return {
        "nkk": res.get("nkk"),
        "valid": res.get("valid"),
        "issue_date": res.get("issue_date"),
        "province": res.get("province"),
        "kabupaten": res.get("kabupaten"),
    }
