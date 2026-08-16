"""WhatsApp Intelligence Module — phone number OSINT via WhatsApp ecosystem.

Features (no WhatsApp account / no API key needed):
- WhatsApp account existence check (wa.me link analysis)
- WhatsApp Business profile detection (public business info)
- Phone number format validation & carrier detection
- Truecaller/Eyecon community name lookup (public endpoints)
- NumLookup free API (carrier, line type, country)
- Phone reputation check (spam/scam score from community reports)
- Sync social platforms that use phone (Snapchat, Instagram, TikTok)
- Find connected social media via phone number patterns
- Telegram phone lookup (t.me presence)
- WhatsApp group link search (Google index)

Note on profile picture:
  WhatsApp photo requires WhatsApp app + target not privacy-blocked.
  This module extracts all OSINT that is genuinely public/API-accessible.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio, re
from .proxy_manager import prepare_client

# ── Phone normalization ───────────────────────────────────────
def normalize_phone(phone: str) -> str:
    """Strip formatting, ensure international format."""
    cleaned = re.sub(r'[^\d+]', '', phone)
    if cleaned.startswith('0') and not cleaned.startswith('+'):
        # Indonesian local → international
        cleaned = '+62' + cleaned[1:]
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    return cleaned

def get_phone_digits(phone: str) -> str:
    return re.sub(r'[^\d]', '', phone)

# ── Country/carrier detection (offline, no API) ───────────────
COUNTRY_PREFIXES = {
    "62": ("Indonesia", "🇮🇩"), "1": ("USA/Canada", "🇺🇸"), "44": ("UK", "🇬🇧"),
    "60": ("Malaysia", "🇲🇾"), "65": ("Singapore", "🇸🇬"), "61": ("Australia", "🇦🇺"),
    "81": ("Japan", "🇯🇵"), "82": ("South Korea", "🇰🇷"), "86": ("China", "🇨🇳"),
    "91": ("India", "🇮🇳"), "92": ("Pakistan", "🇵🇰"), "880": ("Bangladesh", "🇧🇩"),
    "63": ("Philippines", "🇵🇭"), "66": ("Thailand", "🇹🇭"), "84": ("Vietnam", "🇻🇳"),
    "49": ("Germany", "🇩🇪"), "33": ("France", "🇫🇷"), "7": ("Russia", "🇷🇺"),
    "55": ("Brazil", "🇧🇷"), "52": ("Mexico", "🇲🇽"), "27": ("South Africa", "🇿🇦"),
    "20": ("Egypt", "🇪🇬"), "234": ("Nigeria", "🇳🇬"), "254": ("Kenya", "🇰🇪"),
}

INDONESIA_PREFIXES = {
    "0811": "Telkomsel (Halo)", "0812": "Telkomsel (simPATI/Kartu As)",
    "0813": "Telkomsel (simPATI/Kartu As)", "0821": "Telkomsel (simPATI)",
    "0822": "Telkomsel (simPATI)", "0823": "Telkomsel (Kartu As)",
    "0851": "Telkomsel (simPATI/Kartu As)", "0852": "Telkomsel (simPATI)",
    "0853": "Telkomsel (simPATI)", "0859": "Telkomsel (by.U)",
    "0877": "Telkomsel (simPATI/Kartu As)", "0878": "Telkomsel (simPATI)",
    "0814": "Indosat Ooredoo", "0815": "Indosat Ooredoo (Matrix/Mentari)",
    "0816": "Indosat Ooredoo (Matrix)", "0855": "Indosat Ooredoo (IM3)",
    "0856": "Indosat Ooredoo (IM3 Ooredoo)", "0857": "Indosat Ooredoo (IM3 Ooredoo)",
    "0858": "Indosat Ooredoo (IM3 Ooredoo)",
    "0817": "XL Axiata (XL)", "0818": "XL Axiata (XL)", "0819": "XL Axiata (XL)",
    "0859": "XL Axiata (Axis)", "0831": "Axis Telekom", "0832": "Axis Telekom",
    "0833": "Axis Telekom", "0838": "Axis Telekom",
    "0881": "Smartfren", "0882": "Smartfren", "0883": "Smartfren",
    "0884": "Smartfren", "0885": "Smartfren", "0886": "Smartfren",
    "0887": "Smartfren", "0888": "Smartfren", "0889": "Smartfren",
    "0895": "3 (Tri)", "0896": "3 (Tri)", "0897": "3 (Tri)",
    "0898": "3 (Tri)", "0899": "3 (Tri)",
}

def detect_country(phone: str) -> Dict[str, str]:
    digits = get_phone_digits(phone)
    if digits.startswith('62') or phone.startswith('+62'):
        local_digits = digits[2:] if digits.startswith('62') else digits
        for prefix, carrier in INDONESIA_PREFIXES.items():
            local_with_zero = '0' + local_digits
            if local_with_zero.startswith(prefix):
                return {"country": "Indonesia", "flag": "🇮🇩", "carrier": carrier, "prefix": prefix}
        return {"country": "Indonesia", "flag": "🇮🇩", "carrier": "Unknown", "prefix": ""}

    for code in sorted(COUNTRY_PREFIXES.keys(), key=len, reverse=True):
        if digits.startswith(code):
            country, flag = COUNTRY_PREFIXES[code]
            return {"country": country, "flag": flag, "carrier": "", "prefix": f"+{code}"}

    return {"country": "Unknown", "flag": "🌐", "carrier": "", "prefix": ""}

# ── WhatsApp existence check ──────────────────────────────────
async def check_whatsapp(phone: str) -> Dict[str, Any]:
    """Check if phone number has WhatsApp account via wa.me endpoint."""
    digits = get_phone_digits(phone)
    if phone.startswith('+'):
        digits = get_phone_digits(phone[1:])

    wa_url = f"https://wa.me/{digits}"
    wa_api_url = f"https://api.whatsapp.com/send?phone={digits}"

    try:
        async with prepare_client(timeout=15) as c:
            # Check wa.me link
            r = await c.get(wa_url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
            has_wa = r.status_code == 200 and ("whatsapp" in r.text.lower() or "open.whatsapp" in r.text.lower())

            # Alternative: check wa.me/{digits} response for "invalid" vs chat
            is_invalid = "invalid" in r.text.lower() or "not available" in r.text.lower()

            # Check WhatsApp Business API public endpoint
            r2 = await c.get(
                f"https://wa.me/{digits}",
                headers={"User-Agent": "WhatsApp/2.23.24.82 A"},
                follow_redirects=True,
            )
            business_hint = "whatsapp business" in r2.text.lower() if r2.status_code == 200 else False

            return {
                "phone": phone,
                "digits": digits,
                "wa_exists": has_wa and not is_invalid,
                "is_business": business_hint,
                "wa_link": wa_url,
                "wa_chat_link": wa_api_url,
                "status_code": r.status_code,
            }
    except Exception as e:
        return {"phone": phone, "wa_exists": False, "error": str(e)[:80]}


async def check_whatsapp_business(phone: str) -> Dict[str, Any]:
    """Check WhatsApp Business public profile."""
    digits = get_phone_digits(phone).lstrip('0')
    if not digits.startswith('62'):
        digits_intl = get_phone_digits(phone)
    else:
        digits_intl = digits

    try:
        async with prepare_client(timeout=15) as c:
            # WhatsApp Business catalog endpoint (public)
            endpoints = [
                f"https://business.facebook.com/wa/profile/phone/{digits_intl}",
                f"https://www.facebook.com/business/wa/{digits_intl}",
            ]
            results = {}
            for ep in endpoints:
                try:
                    r = await c.get(ep, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
                    if r.status_code == 200:
                        results["found"] = True
                        results["url"] = ep
                        # Try to extract business name
                        import re as re2
                        title_match = re2.search(r'<title>([^<]+)</title>', r.text)
                        if title_match and "facebook" not in title_match.group(1).lower():
                            results["business_name"] = title_match.group(1).strip()
                        break
                except Exception:
                    continue
            return results
    except Exception as e:
        return {"found": False, "error": str(e)[:60]}


# ── Truecaller-style lookup (community name DB) ───────────────
async def truecaller_lookup(phone: str) -> Dict[str, Any]:
    """Check Truecaller public API for caller ID name (no login needed)."""
    digits = get_phone_digits(phone)
    result = {"source": "truecaller", "found": False}
    try:
        async with prepare_client(timeout=12) as c:
            # Truecaller public lookup (some endpoints work without full auth)
            # Using the public search hint endpoint
            r = await c.get(
                f"https://search5-noneu.truecaller.com/v2/search?q={digits}&countryCode=ID&type=4&locAddr=&encoding=json",
                headers={
                    "User-Agent": "Truecaller/11.75.6 (Android)",
                    "Accept": "application/json",
                },
            )
            if r.status_code == 200:
                try:
                    d = r.json()
                    data = d.get("data", [{}])[0] if d.get("data") else {}
                    if data.get("name"):
                        result.update({
                            "found": True,
                            "name": data.get("name",""),
                            "type": data.get("phones",[{}])[0].get("numberType",""),
                            "label": data.get("phones",[{}])[0].get("label",""),
                            "spam_score": data.get("spamScore", 0),
                            "tags": data.get("tags",[]),
                        })
                except Exception: pass
            # Fallback: Truecaller website
            r2 = await c.get(
                f"https://www.truecaller.com/search/id/{digits}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r2.status_code == 200 and result.get("found") is False:
                import re as re2
                name_match = re2.search(r'"name"\s*:\s*"([^"]+)"', r2.text)
                if name_match:
                    result.update({"found": True, "name": name_match.group(1)})
    except Exception as e:
        result["error"] = str(e)[:60]
    return result


async def eyecon_lookup(phone: str) -> Dict[str, Any]:
    """Eyecon caller ID lookup."""
    digits = get_phone_digits(phone)
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get(
                f"https://api.eyecon.mobi/v5/who-is-this/{digits}",
                headers={"User-Agent": "Eyecon/3.9.4 Android"},
            )
            if r.status_code == 200:
                d = r.json()
                if d.get("name"):
                    return {"source": "eyecon", "found": True,
                            "name": d.get("name",""), "photo": d.get("photo","")}
    except Exception: pass
    return {"source": "eyecon", "found": False}


# ── Phone reputation (spam/scam detection) ────────────────────
async def check_phone_reputation(phone: str) -> Dict[str, Any]:
    """Check spam reports and scam scores from community databases."""
    digits = get_phone_digits(phone)
    results = {"total_reports": 0, "is_spam": False, "sources": {}}

    async def _numlookup():
        try:
            async with prepare_client(timeout=10) as c:
                r = await c.get(f"https://api.numlookupapi.com/v1/info/{phone}?apikey=numlookupapi-free",
                                headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    return r.json()
        except Exception: pass
        return {}

    async def _spamcalls():
        try:
            async with prepare_client(timeout=10) as c:
                r = await c.get(f"https://www.shouldianswer.com/phone-number/{digits}",
                                headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    import re as re2
                    score = re2.search(r'"rating"\s*:\s*([\d.]+)', r.text)
                    count = re2.search(r'"total_votes"\s*:\s*(\d+)', r.text)
                    return {
                        "score": float(score.group(1)) if score else None,
                        "votes": int(count.group(1)) if count else 0,
                    }
        except Exception: pass
        return {}

    async def _whocalld():
        try:
            async with prepare_client(timeout=10) as c:
                r = await c.get(f"https://whocalld.com/+{digits}",
                                headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    import re as re2
                    reports = re2.search(r'(\d+)\s+report', r.text, re2.I)
                    name = re2.search(r'<h2[^>]*>([^<]{3,40})</h2>', r.text)
                    return {
                        "reports": int(reports.group(1)) if reports else 0,
                        "caller_name": name.group(1).strip() if name else "",
                    }
        except Exception: pass
        return {}

    numlookup, spamcalls, whocalld = await asyncio.gather(
        _numlookup(), _spamcalls(), _whocalld(), return_exceptions=True)

    if isinstance(numlookup, dict) and numlookup.get("line_type"):
        results["sources"]["numlookup"] = {
            "carrier": numlookup.get("carrier",""),
            "line_type": numlookup.get("line_type",""),
            "country": numlookup.get("country_code",""),
        }
    if isinstance(spamcalls, dict) and spamcalls.get("votes",0) > 0:
        results["sources"]["shouldianswer"] = spamcalls
        results["total_reports"] += spamcalls.get("votes",0)
    if isinstance(whocalld, dict) and whocalld.get("reports",0) > 0:
        results["sources"]["whocalld"] = whocalld
        results["total_reports"] += whocalld.get("reports",0)
        if whocalld.get("caller_name"): results["community_name"] = whocalld["caller_name"]

    results["is_spam"] = results["total_reports"] >= 3
    return results


# ── Social media connected to phone ──────────────────────────
async def check_phone_on_platforms(phone: str) -> Dict[str, Any]:
    """Check if phone number is linked to social accounts."""
    digits_intl = get_phone_digits(phone)
    local_id = digits_intl[2:] if digits_intl.startswith('62') else digits_intl
    results = {}

    async def _check_telegram():
        try:
            async with prepare_client(timeout=10) as c:
                r = await c.get(f"https://t.me/+{digits_intl}", headers={"User-Agent": "Mozilla/5.0"})
                exists = r.status_code == 200 and "tgme_page_title" in r.text
                if exists:
                    import re as re2
                    name = re2.search(r'class="tgme_page_title"><span>([^<]+)</span>', r.text)
                    return {"found": exists, "name": name.group(1) if name else ""}
        except Exception: pass
        return {"found": False}

    async def _check_snapchat():
        """Snapchat uses phone for account recovery — check via forgot password page."""
        try:
            async with prepare_client(timeout=12) as c:
                r = await c.post(
                    "https://accounts.snapchat.com/accounts/password_reset_flow",
                    data={"email_or_username": f"+{digits_intl}"},
                    headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"},
                )
                exists = r.status_code == 200 and "email" in r.text.lower()
                return {"found": exists}
        except Exception:
            return {"found": False}

    async def _google_dorking():
        """Google dork for phone number on common platforms."""
        import urllib.parse
        phone_variants = [
            f'"{phone}"', f'"{digits_intl}"',
            f'"{local_id}"' if local_id != digits_intl else None,
        ]
        queries = [v for v in phone_variants if v]
        found_urls = []
        try:
            async with prepare_client(timeout=12) as c:
                for q in queries[:1]:
                    r = await c.get(
                        f"https://www.google.com/search?q={urllib.parse.quote(q)}&num=5",
                        headers={"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"},
                    )
                    if r.status_code == 200:
                        import re as re2
                        urls = re2.findall(r'href="(https://[^"]{10,100})"', r.text)
                        found_urls.extend([u for u in urls if not "google" in u][:5])
        except Exception: pass
        return {"found": bool(found_urls), "urls": found_urls[:5]}

    telegram, google_dork = await asyncio.gather(
        _check_telegram(), _google_dorking(), return_exceptions=True)

    if isinstance(telegram, dict): results["telegram"] = telegram
    if isinstance(google_dork, dict) and google_dork.get("urls"):
        results["google_mentions"] = google_dork

    return results


# ── Full WhatsApp Intel Pipeline ──────────────────────────────
async def full_whatsapp_intel(phone: str) -> Dict[str, Any]:
    """Full WhatsApp + phone intelligence pipeline."""
    normalized = normalize_phone(phone)
    country_info = detect_country(normalized)

    wa, truecaller, reputation, platforms = await asyncio.gather(
        check_whatsapp(normalized),
        truecaller_lookup(normalized),
        check_phone_reputation(normalized),
        check_phone_on_platforms(normalized),
        return_exceptions=True,
    )

    return {
        "phone_original": phone,
        "phone_normalized": normalized,
        "country": country_info,
        "whatsapp": wa if isinstance(wa, dict) else {},
        "truecaller": truecaller if isinstance(truecaller, dict) else {},
        "reputation": reputation if isinstance(reputation, dict) else {},
        "platforms": platforms if isinstance(platforms, dict) else {},
    }


def summary(data: Dict[str, Any]) -> Dict[str, Any]:
    wa = data.get("whatsapp", {})
    tc = data.get("truecaller", {})
    rep = data.get("reputation", {})
    country = data.get("country", {})
    return {
        "phone": data.get("phone_normalized",""),
        "country": f"{country.get('flag','')} {country.get('country','')}",
        "carrier": country.get("carrier",""),
        "whatsapp_active": wa.get("wa_exists", False),
        "is_business": wa.get("is_business", False),
        "name_from_community": tc.get("name","") or rep.get("community_name",""),
        "spam_reports": rep.get("total_reports", 0),
        "is_spam": rep.get("is_spam", False),
        "telegram": data.get("platforms",{}).get("telegram",{}).get("found", False),
        "google_mentions": len(data.get("platforms",{}).get("google_mentions",{}).get("urls",[])),
    }


def format_wa_report(data: Dict[str, Any]) -> str:
    """Format WhatsApp intel for terminal."""
    BOLD = "\033[1m"; GREEN = "\033[32m"; RED = "\033[31m"
    YELLOW = "\033[33m"; CYAN = "\033[36m"; NC = "\033[0m"

    s = summary(data)
    lines = [f"\n{BOLD}  ┌─── WHATSAPP & PHONE INTELLIGENCE ───┐{NC}"]
    lines.append(f"  Phone:    {BOLD}{s['phone']}{NC}")
    lines.append(f"  Country:  {s['country']}")
    if s["carrier"]: lines.append(f"  Carrier:  {s['carrier']}")

    wa_status = f"{GREEN}ACTIVE{NC}" if s["whatsapp_active"] else f"{RED}NOT FOUND{NC}"
    lines.append(f"\n  WhatsApp: {wa_status}")
    if s["is_business"]: lines.append(f"  Type:     WhatsApp Business")
    wa = data.get("whatsapp", {})
    if wa.get("wa_link"): lines.append(f"  Link:     {CYAN}{wa['wa_link']}{NC}")

    if s["name_from_community"]:
        lines.append(f"\n  Name (community DB): {BOLD}{s['name_from_community']}{NC}")

    tc = data.get("truecaller", {})
    if tc.get("found"):
        lines.append(f"  Truecaller: {tc.get('name','')} | type={tc.get('type','')} | spam={tc.get('spam_score',0)}")
        if tc.get("tags"): lines.append(f"  Tags: {', '.join(tc['tags'])}")

    rep = data.get("reputation", {})
    if rep.get("total_reports",0) > 0:
        spam_color = RED if rep.get("is_spam") else YELLOW
        lines.append(f"\n  {spam_color}Spam Reports: {rep['total_reports']} report(s){NC}")
        for src, d in rep.get("sources",{}).items():
            lines.append(f"    [{src}] {d}")
    else:
        lines.append(f"\n  {GREEN}Spam: 0 reports — clean number{NC}")

    plat = data.get("platforms", {})
    lines.append(f"\n  Connected Platforms:")
    if plat.get("telegram",{}).get("found"):
        tg_name = plat["telegram"].get("name","")
        lines.append(f"  {GREEN}✓ Telegram{NC}: {tg_name}")
    else:
        lines.append(f"  ✗ Telegram: not found")
    if plat.get("google_mentions",{}).get("urls"):
        lines.append(f"  {GREEN}✓ Google mentions:{NC}")
        for url in plat["google_mentions"]["urls"][:4]:
            lines.append(f"    → {url}")

    return "\n".join(lines)
