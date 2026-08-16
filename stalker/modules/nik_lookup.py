#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NIK / KTP lookup — parse & validate Indonesian ID number (16 digit).

Fully offline & keyless:
- Parse NIK structure → province, kabupaten/kota, kecamatan (kode), gender,
  tanggal lahir, serial unik.
- Validasi struktural (panjang, kode wilayah valid, tanggal valid, gender).
- Cek status aktif/nonaktif: indikasi struktural + tautan verifikasi manual.

NIK format: PPKKBB-DDMMYY-SSSS
  PP = kode provinsi, KK = kode kab/kota, BB = kode kecamatan,
  DD = hari (perempuan +40), MM = bulan, YY = tahun, SSSS = serial.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

_REGIONS_PATH = Path(__file__).resolve().parent.parent.parent / "sources" / "indonesia_regions.json"

# 38 provinsi Indonesia (kode Kemendagri).
PROVINCE_CODES: Dict[str, str] = {
    "11": "Aceh", "12": "Sumatera Utara", "13": "Sumatera Barat", "14": "Riau",
    "15": "Jambi", "16": "Sumatera Selatan", "17": "Bengkulu", "18": "Lampung",
    "19": "Kepulauan Bangka Belitung", "21": "Kepulauan Riau",
    "31": "DKI Jakarta", "32": "Jawa Barat", "33": "Jawa Tengah",
    "34": "DI Yogyakarta", "35": "Jawa Timur", "36": "Banten",
    "51": "Bali", "52": "Nusa Tenggara Barat", "53": "Nusa Tenggara Timur",
    "61": "Kalimantan Barat", "62": "Kalimantan Tengah", "63": "Kalimantan Selatan",
    "64": "Kalimantan Timur", "65": "Kalimantan Utara",
    "71": "Sulawesi Utara", "72": "Sulawesi Tengah", "73": "Sulawesi Selatan",
    "74": "Sulawesi Tenggara", "75": "Gorontalo", "76": "Sulawesi Barat",
    "81": "Maluku", "82": "Maluku Utara",
    "91": "Papua Barat", "92": "Papua", "93": "Papua Selatan",
    "94": "Papua Tengah", "95": "Papua Pegunungan", "96": "Papua Barat Daya",
}

_KAB_CODE_MAP: Optional[Dict[str, Dict]] = None


def _load_kab_map() -> Dict[str, Dict]:
    """Build kab/kota code → {kab, prov} index (lazy, cached)."""
    global _KAB_CODE_MAP
    if _KAB_CODE_MAP is not None:
        return _KAB_CODE_MAP
    mapping: Dict[str, Dict] = {}
    try:
        with open(_REGIONS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for name, info in (data.get("kabupaten") or {}).items():
            code = info.get("kab_code")
            if code:
                mapping[code] = {"kab": name.title(), "prov": info.get("prov")}
        # lengkapi dari data desa (mencakup kab/kota yang tak ada di key kabupaten)
        for entries in (data.get("desa") or {}).values():
            for e in entries:
                code = e.get("kab_code")
                if code and code not in mapping:
                    mapping[code] = {"kab": e.get("kab", "").title(), "prov": e.get("prov")}
    except Exception:
        pass
    _KAB_CODE_MAP = mapping
    return mapping


def _title(s: str) -> str:
    return " ".join(w.capitalize() for w in (s or "").split())


def clean_nik(nik: str) -> str:
    """Strip non-digit characters."""
    return re.sub(r"[^0-9]", "", nik or "")


def parse_nik(nik: str) -> Dict:
    """Parse a 16-digit NIK into its components.

    Always returns a dict; `valid` indicates structural soundness.
    """
    raw = clean_nik(nik)
    out: Dict = {
        "nik": raw,
        "valid": False,
        "gender": None,
        "birth_date": None,
        "province_code": raw[:2] if len(raw) >= 2 else "",
        "province": None,
        "kab_code": raw[:4] if len(raw) >= 4 else "",
        "kabupaten": None,
        "kec_code": raw[:6] if len(raw) >= 6 else "",
        "serial": raw[12:16] if len(raw) >= 16 else "",
        "errors": [],
    }

    if len(raw) != 16 or not raw.isdigit():
        out["errors"].append("NIK harus 16 digit angka")
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
        out["kabupaten"] = kab.get("kab") or _title(kab.get("kab", ""))
        if not prov:
            out["province"] = kab.get("prov")
    else:
        out["errors"].append(f"kode kabupaten/kota tidak dikenal: {kab_code}")

    # Gender & tanggal lahir
    gender = "male"
    real_day = day
    if day > 40:
        gender = "female"
        real_day = day - 40
    out["gender"] = gender

    # Tahun: heuristik 2 digit (<= tahun sekarang → 20xx, selain itu 19xx)
    cur_yy = int(datetime.now().strftime("%y"))
    year = 2000 + year2 if year2 <= cur_yy else 1900 + year2
    out["birth_year"] = year

    if not (1 <= month <= 12):
        out["errors"].append(f"bulan tidak valid: {month}")
    if not (1 <= real_day <= 31):
        out["errors"].append(f"tanggal tidak valid: {real_day}")

    try:
        dt = datetime(year, month, real_day)
        out["birth_date"] = dt.strftime("%Y-%m-%d")
        out["birth_date_iso"] = dt.isoformat()
    except ValueError:
        out["errors"].append("tanggal lahir tidak valid (kombinasi hari/bulan)")

    out["age"] = _age_from_date(out.get("birth_date"))
    out["unique_code"] = out["serial"]
    out["valid"] = not out["errors"]
    return out


def _age_from_date(birth: Optional[str]) -> Optional[int]:
    if not birth:
        return None
    try:
        b = datetime.strptime(birth, "%Y-%m-%d")
        today = datetime.now()
        return today.year - b.year - ((today.month, today.day) < (b.month, b.day))
    except Exception:
        return None


def validate_nik(nik: str) -> Dict:
    """Full structural validation (same as parse_nik but returns a clear verdict)."""
    res = parse_nik(nik)
    verdict = "valid" if res.get("valid") else "invalid"
    return {
        "nik": res.get("nik"),
        "verdict": verdict,
        "valid": res.get("valid"),
        "errors": res.get("errors", []),
        "detail": res,
    }


async def check_active(nik: str) -> Dict:
    """Cek status NIK: indikasi struktural + tautan verifikasi manual."""
    res = parse_nik(nik)
    active = res.get("valid", False)
    return {
        "nik": res.get("nik"),
        "structurally_valid": active,
        "likely_active": active,
        "manual_check": {
            "bpjs": "https://bpjs-kesehatan.go.id",
            "dukcapil": "https://dukcapil.kemendagri.go.id",
        },
    }


def summary(res: Dict) -> Dict:
    """Compact summary for reports."""
    return {
        "nik": res.get("nik"),
        "valid": res.get("valid"),
        "gender": res.get("gender"),
        "birth_date": res.get("birth_date"),
        "age": res.get("age"),
        "province": res.get("province"),
        "kabupaten": res.get("kabupaten"),
    }
