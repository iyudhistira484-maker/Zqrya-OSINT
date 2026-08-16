#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phone HLR Lookup — carrier/line-type/status nomor (best-effort).

1. Analisis offline (carrier, tipe, negara, timezone) via libphonenumber.
2. Enrich dari endpoint gratis (numlookupapi free / numverify bila key ada).
3. `live_status = unknown` bila tidak ada provider HLR.
"""

from __future__ import annotations

import re
from typing import Dict

from .proxy_manager import prepare_client
from .phone_scanner import analyze_number, lookup_provider


def clean(phone: str) -> str:
    return re.sub(r"[^0-9]", "", phone or "")


async def _numlookupapi(phone: str) -> Dict:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get(f"https://api.numlookupapi.com/v1/info/{clean(phone)}?apikey=numlookupapi-free")
            if r.status_code == 200:
                d = r.json()
                return {
                    "valid": d.get("valid", False),
                    "carrier": d.get("carrier", ""),
                    "line_type": d.get("line_type", ""),
                    "country": d.get("country_name", ""),
                    "location": d.get("location", ""),
                }
    except Exception:
        pass
    return {}


async def _numverify(phone: str) -> Dict:
    from ..config import Config
    key = Config.NUMVERIFY_API_KEY
    if not key:
        return {}
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get(f"https://api.apilayer.com/number_verification/validate?apikey={key}&number={clean(phone)}")
            if r.status_code == 200:
                d = r.json()
                if d.get("valid"):
                    return {
                        "valid": True,
                        "carrier": d.get("carrier", ""),
                        "line_type": d.get("line_type", ""),
                        "country": d.get("country_name", ""),
                        "location": d.get("location", ""),
                    }
    except Exception:
        pass
    return {}


async def hlr_lookup(phone: str) -> Dict:
    """HLR-style lookup (offline analysis + best-effort live enrich)."""
    digits = clean(phone)
    analysis = {}
    try:
        analysis = analyze_number(digits)
    except Exception:
        analysis = {"error": "phonenumbers tidak tersedia"}

    provider = {}
    for fn in (_numlookupapi, _numverify):
        try:
            provider = await fn(digits)
            if provider.get("carrier") or provider.get("valid"):
                break
        except Exception:
            continue

    carrier = provider.get("carrier") or analysis.get("carrier") or lookup_provider(digits) or "Unknown"
    line_type = provider.get("line_type") or analysis.get("line_type") or "Unknown"
    valid = provider.get("valid", analysis.get("valid", analysis.get("possible", None)))

    return {
        "phone": digits,
        "valid": valid,
        "carrier": carrier,
        "line_type": line_type,
        "country": provider.get("country") or analysis.get("country", "Unknown"),
        "location": provider.get("location", ""),
        "timezone": analysis.get("timezone", ""),
        "live_status": "unknown",
    }


def summary(res: Dict) -> Dict:
    return {
        "phone": res.get("phone"),
        "valid": res.get("valid"),
        "carrier": res.get("carrier"),
        "line_type": res.get("line_type"),
        "live_status": res.get("live_status"),
    }
