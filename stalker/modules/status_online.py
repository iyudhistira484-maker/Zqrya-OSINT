#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Status Online Checker — Telegram & WhatsApp last-seen/online (best-effort).

- Telegram: scrape halaman publik t.me (last seen recently / online) tanpa key.
- WhatsApp: cek keberadaan akun via wa.me.
"""

from __future__ import annotations

import re
from typing import Dict

from .proxy_manager import prepare_client
from .phone_scanner import check_whatsapp


async def telegram_status(username: str) -> Dict:
    """Check Telegram public profile + last-seen hint via t.me page."""
    user = re.sub(r"^@", "", (username or "").strip())
    if not user:
        return {"username": username, "error": "username kosong"}
    url = f"https://t.me/{user}"
    out: Dict = {"username": user, "url": url, "exists": False, "status": None}
    try:
        async with prepare_client(timeout=12, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                out["error"] = f"HTTP {r.status_code}"
                return out
            text = r.text
            out["exists"] = "tgme_page_title" in text

            # judul & deskripsi profil
            m = re.search(r'<div class="tgme_page_title"[^>]*>.*?<span[^>]*>([^<]+)</span>', text, re.S)
            if not m:
                m = re.search(r'<meta property="og:title" content="([^"]+)"', text)
            if m:
                out["display_name"] = m.group(1).strip()

            # indikasi last seen / online
            if re.search(r"\bonline\b", text, re.I):
                out["status"] = "online"
            elif re.search(r"last seen recently", text, re.I):
                out["status"] = "last seen recently"
            elif re.search(r"last seen within a (week|month)", text, re.I):
                mm = re.search(r"last seen within a (week|month)", text, re.I)
                out["status"] = mm.group(0)
            elif re.search(r"last seen a long time ago", text, re.I):
                out["status"] = "last seen a long time ago"
            elif out.get("exists") and not out.get("status"):
                # Profil publik ada tapi halaman tidak menampilkan last-seen —
                # Telegram menyembunyikannya untuk user biasa (privasi).
                out["status"] = "profil ada — last seen disembunyikan (privasi Telegram)"
                out["note"] = ("Status last-seen hanya tampil kalau pemilik akun membukanya "
                                "untuk publik; akun ini menyembunyikannya.")

            desc = re.search(r'<meta property="og:description" content="([^"]+)"', text)
            if desc:
                out["description"] = desc.group(1)[:200]
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


async def whatsapp_status(phone: str) -> Dict:
    """WhatsApp: keberadaan akun via wa.me."""
    wa = await check_whatsapp(phone)
    digits = re.sub(r"[^0-9]", "", phone)
    registered = bool(wa.get("registered", False))
    return {
        "phone": phone,
        "account_exists": registered,
        "wa_link": f"https://wa.me/{digits}",
        # status: terdaftar / tidak terdaftar / gagal cek
        "status": ("terdaftar di WhatsApp" if registered
                   else (wa.get("error") and "gagal cek") or "tidak terdaftar"),
        "note": wa.get("error"),
    }


async def check_status(target: str, kind: str = "auto") -> Dict:
    """One-shot: deteksi jenis target (username telegram / nomor WA) lalu cek."""
    t = (target or "").strip()
    if kind == "auto":
        kind = "phone" if re.match(r"^\+?[0-9]{7,15}$", t.replace(" ", "").replace("-", "")) else "telegram"
    if kind == "phone":
        return await whatsapp_status(t)
    return await telegram_status(t)


def summary(res: Dict) -> Dict:
    return {
        "exists": res.get("exists", res.get("account_exists", False)),
        "status": res.get("status"),
        "display_name": res.get("display_name", ""),
    }
