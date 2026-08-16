#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E-wallet OSINT — cek nomor di GoPay/OVO/DANA/ShopeePay dll.

- Normalisasi & analisis nomor (carrier via prefix).
- Panduan verifikasi andal: transfer nominal kecil → lihat nama pemilik.
- Link pencarian/dork untuk memperkuat jejak nomor.

Teknik transfer-kecil adalah standar anti-scam Indonesia: saat mengirim ke
nomor e-wallet, aplikasi menampilkan NAMA pemilik akun sebelum transfer selesai.
"""

from __future__ import annotations

import re
from typing import Dict, List

from .phone_scanner import analyze_number, lookup_provider

E_WALLETS = [
    {"id": "gopay", "name": "GoPay (Gojek)", "hint": "Aplikasi Gojek → Bayar → Transfer → ke nomor GoPay. Cek nama sebelum kirim."},
    {"id": "ovo", "name": "OVO", "hint": "Aplikasi OVO → Transfer → ke nomor OVO. Nama muncul sebelum konfirmasi."},
    {"id": "dana", "name": "DANA", "hint": "Aplikasi DANA → Kirim → ke nomor DANA. Cek nama penerima."},
    {"id": "shopeepay", "name": "ShopeePay", "hint": "Aplikasi Shopee → Transfer ShopeePay → ke nomor. Cek nama."},
    {"id": "linkaja", "name": "LinkAja", "hint": "Aplikasi LinkAja → Kirim → ke nomor. Cek nama penerima."},
    {"id": "sakuku", "name": "Sakuku (BCA)", "hint": "Aplikasi Sakuku → Transfer → ke nomor. Cek nama."},
]


def clean_phone(phone: str) -> str:
    return re.sub(r"[^0-9]", "", phone or "")


def _to_national(phone: str) -> str:
    digits = clean_phone(phone)
    if digits.startswith("62"):
        return "0" + digits[2:]
    return digits


async def check_ewallets(phone: str) -> Dict:
    """Check phone against e-wallets.

    Returns per-platform result with `status` = registered|not_registered|unknown.
    """
    digits = clean_phone(phone)
    national = _to_national(phone)
    carrier = lookup_provider(digits) or "Unknown"

    analysis = {}
    try:
        analysis = analyze_number(digits)
    except Exception:
        pass

    results = []
    for w in E_WALLETS:
        results.append({
            "platform": w["id"],
            "name": w["name"],
            "status": "unknown",
            "verify_how": w["hint"],
        })

    return {
        "phone": digits,
        "national": national,
        "carrier": carrier,
        "analysis": analysis,
        "ewallets": results,
    }


def manual_verify_guide() -> List[str]:
    """Panduan langkah anti-scam: cek nama pemilik via transfer nominal kecil."""
    return [
        "1. Buka aplikasi e-wallet (GoPay/OVO/DANA/ShopeePay/LinkAja).",
        "2. Pilih menu Transfer / Kirim Dana.",
        "3. Masukkan nomor target (format lokal 08xx).",
        "4. Aplikasi akan menampilkan NAMA pemilik akun SEBELUM transfer.",
        "5. Jangan kirim dana — cukup catat nama yang muncul, lalu batalkan.",
        "6. Bandingkan nama itu dengan data target (NIK/identitas) untuk konfirmasi.",
    ]


def ewallet_dorks(phone: str) -> List[Dict]:
    """Search links / dorks untuk memperkuat jejak nomor di e-wallet & marketplace."""
    digits = clean_phone(phone)
    national = _to_national(phone)
    q = re.escape(digits)
    queries = [
        f'"{digits}" gopay OR ovo OR dana OR shopeepay',
        f'"{national}" transfer OR rekening',
        f'"{digits}" site:facebook.com OR site:twitter.com OR site:instagram.com',
        f'"{digits}" site:olx.co.id OR site:tokopedia.com OR site:shopee.co.id OR site:bukalapak.com',
    ]
    from urllib.parse import quote
    return [{"query": d, "url": f"https://www.google.com/search?q={quote(d)}"} for d in queries]


def summary(res: Dict) -> Dict:
    return {
        "phone": res.get("phone"),
        "carrier": res.get("carrier"),
        "ewallets_checked": len(res.get("ewallets", [])),
    }
