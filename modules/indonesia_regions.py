#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolver wilayah Indonesia — memetakan nama tempat ke kabupaten/kota.

Dataset: sources/indonesia_regions.json (83.762 desa/kelurahan, 7.285 kecamatan,
514 kabupaten/kota + centroid kabupaten).

Tujuan: ketika sumber GeoIP mengembalikan nama DESA/KECAMATAN (mis. "Penambangan"
dari ip-api), padahal yang benar level KABUPATEN/KOTA, resolver ini mengubahnya
jadi kabupaten yang benar (mis. "Tuban") — bukan tebakan kota besar terdekat.

Nama yang ambigu (desa dengan nama sama di beberapa kabupaten) dipilih pakai
koordinat terdekat dari centroid kabupaten bila lat/lon tersedia.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional

_DATA_PATH = Path(__file__).resolve().parent.parent / "sources" / "indonesia_regions.json"

_IGNORE = {None, "", "Unknown", "-", "unknown"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _title(s: str) -> str:
    """Title-case nama kabupaten (bandar lampung -> Bandar Lampung)."""
    return " ".join(w.capitalize() for w in s.split())


class IndonesiaRegions:
    """Singleton loader + resolver nama tempat Indonesia."""

    _instance: Optional["IndonesiaRegions"] = None

    def __new__(cls) -> "IndonesiaRegions":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    @property
    def available(self) -> bool:
        return bool(getattr(self, "_data", None))

    def _load(self) -> None:
        try:
            with open(_DATA_PATH, encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def resolve(self, name: str, lat: Optional[float] = None,
                lon: Optional[float] = None) -> Optional[Dict]:
        """Petakan nama tempat ke kabupaten/kota.

        Return dict {city, kec, kab, prov, level, specific} atau None.
        `level`: 'kabupaten' | 'kecamatan' | 'desa'.
        `specific`: True bila nama adalah desa/kecamatan (sinyal lebih presisi
                    daripada tebakan kota besar).
        """
        if not self.available or name in _IGNORE:
            return None
        n = _norm(name)
        if not n:
            return None

        # 1) Sudah level kabupaten/kota? (mis. "Surabaya", "Tuban")
        kab = self._data.get("kabupaten", {}).get(n)
        if kab:
            return {
                "city": _title(n), "kec": None, "kab": _title(n),
                "prov": kab.get("prov"), "level": "kabupaten", "specific": False,
            }

        # 2) Nama kecamatan?
        kc = self._data.get("kecamatan", {}).get(n)
        if kc:
            best = self._pick(kc, lat, lon)
            if best:
                return {
                    "city": _title(best["kab"]), "kec": _title(n),
                    "kab": _title(best["kab"]), "prov": best.get("prov"),
                    "level": "kecamatan", "specific": True,
                }

        # 3) Nama desa/kelurahan?
        ds = self._data.get("desa", {}).get(n)
        if ds:
            best = self._pick(ds, lat, lon)
            if best:
                return {
                    "city": _title(best["kab"]), "kec": best.get("kec"),
                    "kab": _title(best["kab"]), "prov": best.get("prov"),
                    "level": "desa", "specific": True,
                }

        return None

    def _pick(self, candidates: List[Dict], lat: Optional[float],
              lon: Optional[float]) -> Optional[Dict]:
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        # Ambigu: pilih yang centroid kabupaten-nya terdekat dengan lat/lon.
        if lat is not None and lon is not None:
            centroids = self._data.get("centroid", {})

            def d(c: Dict) -> float:
                cc = centroids.get(c.get("kab_code", ""))
                if not cc:
                    return 1e9
                return math.hypot(cc[0] - lat, cc[1] - lon)

            return min(candidates, key=d)
        return None  # ambigu tanpa koordinat — jangan menebak
