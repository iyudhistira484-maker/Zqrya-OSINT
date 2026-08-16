#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local GeoIP lookup — offline, tanpa API key, tanpa rate limit.

Mendukung MULTIPLE database .mmdb / .mmdb.gz sekaligus. Database dengan
prioritas tertinggi dipakai dulu; jika tidak punya data kota, dicari ke
database berikutnya yang punya kota, lalu fallback ke konsensus online.

Prioritas (berdasarkan nama file):
    1. GeoLite2-City.mmdb            (MaxMind — city-level penuh)
    2. IP2LOCATION-LITE-DB11*.mmdb   (IP2Location LITE DB11 — city-level)
    3. dbip-city-lite-*.mmdb.gz      (DB-IP Lite — tanpa akun)
    4. GeoLite2-Country.mmdb         (hanya negara, pelengkap)

Letakkan file di salah satu folder (nama file bebas, asal .mmdb/.mmdb.gz):

    project root/
    data/geoip/
    sources/geoip/
    geoip/

Unduh gratis:
- GeoLite2 City (cakupan kota Indonesia lebih lengkap):
  https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/
  → sign up (https://www.maxmind.com/en/geolite2/signup) → license key → download
- IP2Location LITE DB11 (vendor beda, mengisi celah GeoLite2 — butuh signup email):
  https://lite.ip2location.com/database/db11-ip-country-region-city-latitude-longitude-zipcode-timezone
  → Sign Up For Free → download format MMDB → taruh file apa adanya
- DB-IP Lite (tanpa daftar):
  https://db-ip.com/db/download/ip-to-city-lite

Butuh package: pip install maxminddb
Tanpa package/file DB, tool otomatis fallback ke konsensus API online.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Direktori pencarian file DB (relatif terhadap root project)
_BASE = Path(__file__).resolve().parent.parent
DB_DIRS = [
    _BASE,  # project root (lokasi umum hasil download)
    _BASE / "data" / "geoip",
    _BASE / "sources" / "geoip",
    _BASE / "geoip",
]

# Urutan prioritas (cocokkan substring nama file, case-insensitive)
_PRIORITY = (
    "geolite2-city",
    "db11",
    "dbip-city-lite",
    "geolite2-country",
)


class LocalGeoIP:
    """Pembaca beberapa database GeoIP lokal (maxminddb)."""

    def __init__(self) -> None:
        self._readers: List[Tuple[str, object]] = []
        self.source: Optional[str] = None
        self._load()

    @property
    def available(self) -> bool:
        return bool(self._readers)

    def _load(self) -> None:
        try:
            import maxminddb  # noqa: F401
        except ImportError:
            return

        found = []
        seen = set()
        for d in DB_DIRS:
            if not d.is_dir():
                continue
            candidates = [p for p in d.iterdir()
                          if p.is_file() and p.name.lower().endswith((".mmdb", ".mmdb.gz"))]
            candidates.sort(key=lambda p: p.name.lower())
            for p in candidates:
                stem = p.name[:-3] if p.name.lower().endswith(".gz") else p.name
                if stem in seen:
                    continue  # .mmdb cache sudah dipakai, lewati .gz duplikatnya
                seen.add(stem)
                path = self._ensure_plain(p)
                if not path:
                    continue
                try:
                    import maxminddb

                    found.append((p.name, maxminddb.open_database(str(path))))
                except Exception:
                    continue

        def _rank(item: Tuple[str, object]) -> int:
            name = item[0].lower()
            for i, key in enumerate(_PRIORITY):
                if key in name:
                    return i
            return len(_PRIORITY)

        found.sort(key=_rank)
        self._readers = found
        self.source = ", ".join(n for n, _ in found) or None

    @staticmethod
    def _ensure_plain(path: Path) -> Optional[Path]:
        """Jika .mmdb.gz, ekstrak ke .mmdb (cache) dan kembalikan path .mmdb."""
        if path.suffix.lower() != ".gz":
            return path
        out = path.with_suffix("")  # buang .gz -> .mmdb
        if out.is_file():
            return out
        import gzip
        import os
        import shutil
        import tempfile

        try:
            # tulis ke file di direktori tujuan (hindari cross-device rename /tmp)
            fd, tmp_path = tempfile.mkstemp(suffix=".mmdb", dir=str(out.parent))
            os.close(fd)
            try:
                with gzip.open(path, "rb") as fin, open(tmp_path, "wb") as fout:
                    shutil.copyfileobj(fin, fout)
                os.replace(tmp_path, str(out))
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            return out
        except Exception:
            return None

    def lookup_all(self, ip: str) -> List[Dict]:
        """Kembalikan semua record ternormalisasi (satu per DB), tanpa voting.

        Dipakai pemanggil yang ingin menggabungkan suara DB lokal dengan
        sumber lain (mis. API online) dalam satu majority vote.
        """
        if not self._readers:
            return []
        out: List[Dict] = []
        for name, reader in self._readers:
            try:
                rec = reader.get(ip)
            except Exception:
                continue
            if rec:
                d = self._normalize(rec)
                d["_db"] = name
                out.append(d)
        return out

    def lookup(self, ip: str) -> Optional[Dict]:
        """Ambil record hasil majority vote antar DB lokal.

        Kota/kode negara dipilih dari suara terbanyak antar database lokal,
        bukan sekadar 'DB prioritas tertinggi'. Metadata kesepakatan disertakan
        supaya pemanggil bisa melaporkan ketidaksepakatan dengan jujur:

          _db             : nama DB penyedia record final
          _local_count    : jumlah DB yang mengembalikan kota
          _local_agree    : jumlah DB yang setuju dengan kota terpilih
          _local_disagree : True jika DB-DB lokal saling beda kota
          _local_cities   : daftar kota berbeda yang dilaporkan DB lokal
        """
        dicts = self.lookup_all(ip)
        if not dicts:
            return None

        from collections import Counter

        cities = [r.get("city") for r in dicts if r.get("city")]
        city = Counter(cities).most_common(1)[0][0] if cities else None
        codes = [r.get("country_code") for r in dicts if r.get("country_code")]
        country_code = Counter(codes).most_common(1)[0][0] if codes else None

        distinct_cities = list(dict.fromkeys(cities))
        local_count = len(cities)
        local_agree = cities.count(city) if city else 0

        # Record final diambil dari DB yang setuju dengan hasil vote (konsisten region dll.)
        base = None
        for r in dicts:
            if r.get("city") == city:
                base = r
                break
        if base is None:
            for r in dicts:
                if r.get("country_code") == country_code:
                    base = r
                    break
        if base is None:
            base = dicts[0]

        out = dict(base)
        out["city"] = city
        out["country_code"] = country_code
        out["_local_count"] = local_count
        out["_local_agree"] = local_agree
        out["_local_disagree"] = len(distinct_cities) > 1
        out["_local_cities"] = distinct_cities
        return out

    @staticmethod
    def _normalize(rec: Dict) -> Dict:
        # Schema IP2Location (flat) — DB11 LITE MMDB
        if not isinstance(rec.get("country"), dict) and not isinstance(rec.get("city"), dict):
            return {
                "country": rec.get("country_name"),
                "country_code": rec.get("country_code"),
                "region": rec.get("region_name"),
                "city": rec.get("city_name"),
                "zip": rec.get("zip_code"),
                "lat": rec.get("latitude"),
                "lon": rec.get("longitude"),
                "timezone": rec.get("time_zone"),
                "accuracy_radius": None,
                "isp": None,
                "org": None,
                "asn": None,
                "asn_name": None,
            }

        # Schema MaxMind-style (nested) — GeoLite2 / DB-IP
        country = rec.get("country") or {}
        city = rec.get("city") or {}
        location = rec.get("location") or {}
        subs = rec.get("subdivisions") or []
        sub = subs[0] if subs else {}
        postal = rec.get("postal") or {}
        traits = rec.get("traits") or {}

        country_names = country.get("names") or {}
        city_names = city.get("names") or {}
        sub_names = sub.get("names") or {}

        return {
            "country": country_names.get("en") or country.get("iso_code"),
            "country_code": country.get("iso_code"),
            "region": sub_names.get("en") or sub.get("iso_code"),
            "city": city_names.get("en"),
            "zip": postal.get("code"),
            "lat": location.get("latitude"),
            "lon": location.get("longitude"),
            "timezone": location.get("time_zone"),
            "accuracy_radius": location.get("accuracy_radius"),
            "isp": traits.get("isp"),
            "org": traits.get("organization"),
            "asn": traits.get("autonomous_system_number"),
            "asn_name": traits.get("autonomous_system_organization"),
        }
