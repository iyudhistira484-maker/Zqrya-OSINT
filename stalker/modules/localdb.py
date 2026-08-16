"""Local database search engine — queries CSV-based databases.

Searches across 5 Indonesian databases:
  - idnpolice.csv (Police personnel)
  - myindihome_sample.csv (IndiHome customers)
  - npwp-10k-sample.csv (Tax ID records)
  - siak_clean_sample_1k.csv (Civil registry)
  - siak_full_sample_1k.csv (Civil registry full)

Zero external deps — uses built-in csv module.
In-memory cache after first load.
NIK/phone masking for privacy in output.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pathlib import Path
import csv

_CACHE: Dict[str, List[Dict[str, str]]] = {}
_LOADED = False

DB_FILES = [
    "idnpolice.csv",
    "myindihome_sample.csv",
    "npwp-10k-sample.csv",
    "siak_clean_sample_1k.csv",
    "siak_full_sample_1k.csv",
]


def _get_db_dir() -> Path:
    from ..config import Config
    return Path(Config.LOCALDB_DIR)


def _load_all() -> Dict[str, List[Dict[str, str]]]:
    """Load all CSV files into memory (cached after first call)."""
    global _CACHE, _LOADED
    if _LOADED:
        return _CACHE

    db_dir = _get_db_dir()
    if not db_dir.exists():
        _LOADED = True
        return {}

    for filename in DB_FILES:
        filepath = db_dir / filename
        if not filepath.exists():
            continue
        try:
            rows = []
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append({k.strip(): v.strip() if v else "" for k, v in row.items()})
            _CACHE[filename] = rows
        except Exception:
            pass

    _LOADED = True
    return _CACHE


def _mask_nik(nik: str) -> str:
    """Mask NIK: 337205******0006"""
    if not nik or len(nik) < 10:
        return nik or "?"
    return nik[:6] + "*" * (len(nik) - 10) + nik[-4:]


def _mask_phone(phone: str) -> str:
    """Mask phone: 0813*****908"""
    if not phone or len(phone) < 5:
        return phone or "?"
    return phone[:4] + "*" * (len(phone) - 7) + phone[-3:]


def search_by_name(name: str) -> Dict[str, List[Dict[str, Any]]]:
    """Fuzzy search for a name across all databases."""
    if not name or len(name) < 2:
        return {}
    name_lower = name.lower()
    results: Dict[str, List[Dict[str, Any]]] = {}
    dbs = _load_all()

    for filename, rows in dbs.items():
        matches = []
        for row in rows:
            full_name = row.get("NAMA") or row.get("NAMA_LGKP") or ""
            if name_lower in full_name.lower():
                match = _extract_row(filename, row)
                if match:
                    matches.append(match)
        if matches:
            results[filename] = matches[:20]
    return results


def search_by_nik(nik: str) -> Dict[str, List[Dict[str, Any]]]:
    """Exact NIK match across SIAK and NPWP databases."""
    nik = nik.strip()
    if len(nik) < 10:
        return {}
    results: Dict[str, List[Dict[str, Any]]] = {}
    dbs = _load_all()

    for filename in ("siak_clean_sample_1k.csv", "siak_full_sample_1k.csv", "npwp-10k-sample.csv"):
        if filename not in dbs:
            continue
        for row in dbs[filename]:
            row_nik = row.get("NIK", "").strip()
            if row_nik == nik:
                results.setdefault(filename, []).append(_extract_row(filename, row))
    return results


def search_by_email(email: str) -> Dict[str, List[Dict[str, Any]]]:
    """Search for email in IndiHome, NPWP, Police databases."""
    email = email.strip().lower()
    if "@" not in email:
        return {}
    results: Dict[str, List[Dict[str, Any]]] = {}
    dbs = _load_all()

    for filename, rows in dbs.items():
        matches = []
        for row in rows:
            row_email = (row.get("EMAIL") or row.get("email") or "").strip().lower()
            if row_email and email in row_email:
                match = _extract_row(filename, row)
                if match:
                    matches.append(match)
        if matches:
            results[filename] = matches[:20]
    return results


def search_by_phone(phone: str) -> Dict[str, List[Dict[str, Any]]]:
    """Search for phone in IndiHome, Police, NPWP databases."""
    phone = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
    if len(phone) < 7:
        return {}
    results: Dict[str, List[Dict[str, Any]]] = {}
    dbs = _load_all()

    for filename, rows in dbs.items():
        matches = []
        for row in rows:
            row_phone = (row.get("HP") or row.get("mobile") or row.get("TELP") or
                         row.get("SMS_PHONE") or "").strip().replace(" ", "").replace("-", "").replace("+", "")
            if row_phone and phone in row_phone:
                match = _extract_row(filename, row)
                if match:
                    matches.append(match)
        if matches:
            results[filename] = matches[:20]
    return results


def search_all(
    real_names: List[str] = None,
    emails: List[str] = None,
    phones: List[str] = None,
    niks: List[str] = None,
) -> Dict[str, Any]:
    """Smart search across ALL extracted data."""
    results: Dict[str, Any] = {}
    dbs = _load_all()
    if not dbs:
        return {}

    if real_names:
        names_result: Dict[str, List[Dict]] = {}
        for name in real_names[:5]:
            partial = search_by_name(name)
            for db, matches in partial.items():
                if db not in names_result:
                    names_result[db] = []
                for m in matches:
                    if m not in names_result[db]:
                        names_result[db].append(m)
        if names_result:
            results["by_name"] = names_result

    if emails:
        email_result: Dict[str, List[Dict]] = {}
        for email in emails[:5]:
            partial = search_by_email(email)
            for db, matches in partial.items():
                email_result.setdefault(db, []).extend(matches)
        if email_result:
            results["by_email"] = email_result

    if phones:
        phone_result: Dict[str, List[Dict]] = {}
        for phone in phones[:3]:
            partial = search_by_phone(phone)
            for db, matches in partial.items():
                phone_result.setdefault(db, []).extend(matches)
        if phone_result:
            results["by_phone"] = phone_result

    if niks:
        nik_result: Dict[str, List[Dict]] = {}
        for nik in niks[:3]:
            partial = search_by_nik(nik)
            for db, matches in partial.items():
                nik_result.setdefault(db, []).extend(matches)
        if nik_result:
            results["by_nik"] = nik_result

    return results


def _extract_row(filename: str, row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Extract key fields from a row, masking sensitive data."""
    base = filename.replace(".csv", "")

    if base == "idnpolice":
        return {
            "source": "Polri",
            "name": row.get("NAMA", "?"),
            "rank": row.get("PANGKAT", "?"),
            "role": row.get("TUGAS", "?")[:80],
            "phone": _mask_phone(row.get("HP", "")),
            "email": row.get("EMAIL", ""),
        }
    elif base == "myindihome_sample":
        return {
            "source": "IndiHome",
            "email": row.get("email", "") or row.get("EMAIL", ""),
            "phone": _mask_phone(row.get("mobile", "")),
            "customer_id": row.get("indihomenum", ""),
            "device": f"{row.get('devicetype', '?')} {row.get('osversion', '')}",
        }
    elif base == "npwp-10k-sample":
        return {
            "source": "NPWP",
            "name": row.get("NAMA", "?"),
            "nik": _mask_nik(row.get("NIK", "")),
            "npwp": row.get("NPWP", "?"),
            "address": f"{row.get('ALAMAT', '')}, {row.get('KELURAHAN', '')}, {row.get('KABKOT', '')}",
            "province": row.get("PROVINSI", ""),
            "phone": _mask_phone(row.get("TELP", "")),
            "email": row.get("EMAIL", ""),
            "birth": row.get("TTL", ""),
        }
    elif base in ("siak_clean_sample_1k", "siak_full_sample_1k"):
        entry = {
            "source": "SIAK",
            "name": row.get("NAMA_LGKP", "?"),
            "nik": _mask_nik(row.get("NIK", "")),
            "birth_place": row.get("TMPT_LHR", ""),
            "birth_date": row.get("TGL_LHR", "")[:10],
            "gender": "Male" if row.get("JENIS_KLMIN") == "1" else "Female",
            "religion": row.get("AGAMA", ""),
            "marital": row.get("STAT_KWN", ""),
            "education": row.get("PDDK_AKH", ""),
            "occupation": row.get("JENIS_PKRJN", ""),
        }
        if base == "siak_full_sample_1k":
            entry["email"] = row.get("EMAIL", "")
            entry["phone"] = _mask_phone(row.get("SMS_PHONE", ""))
        return entry
    return None


def db_count() -> int:
    """Return number of loaded database files."""
    return len(_load_all())


def summary(results: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize local database search results."""
    s = {"dbs_searched": db_count(), "total_matches": 0}
    for method, dbs in results.items():
        for db, matches in dbs.items():
            s["total_matches"] += len(matches)
    return s
