"""Phone number scanner — enhanced with cb-phonehunter features.

Registration checks on social platforms + Truecaller lookup + GetContact
links + Google phone dorks + E164 carrier/geo analysis via phonenumbers.

Adapted from ciberbrigada/cb-phonehunter and megadose/ignorant.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio
import hashlib
import hmac
import json
import urllib.parse
import re
import httpx
from .proxy_manager import prepare_client


# ============================================================
#  PHONENUMBERS ANALYSIS (Google libphonenumber)
# ============================================================

try:
    import phonenumbers as pn
    from phonenumbers import geocoder, carrier, timezone as pn_tz
    HAS_PHONENUMBERS = True
except ImportError:
    HAS_PHONENUMBERS = False

LINE_TYPES = {
    0: "Fixed Line", 1: "Mobile", 2: "Fixed or Mobile",
    3: "Toll Free", 4: "Premium Rate", 5: "Shared Cost",
    6: "VoIP", 7: "Personal Number", 8: "Pager",
    9: "UAN", 10: "Voicemail", 99: "Unknown",
}

COUNTRY_NAMES = {
    "ID": "Indonesia", "US": "United States", "MY": "Malaysia",
    "SG": "Singapore", "TH": "Thailand", "PH": "Philippines",
    "VN": "Vietnam", "IN": "India", "CN": "China", "JP": "Japan",
    "KR": "South Korea", "AU": "Australia", "GB": "United Kingdom",
    "DE": "Germany", "FR": "France", "BR": "Brazil", "RU": "Russia",
}


def analyze_number(phone_raw: str) -> Dict[str, Any]:
    """Analyze phone number via Google's libphonenumber.

    Returns: {e164, international, country, carrier, line_type, timezone, ...}
    """
    if not HAS_PHONENUMBERS:
        return {"error": "phonenumbers library not installed. Run: pip install phonenumbers"}

    try:
        parsed = pn.parse(phone_raw)
    except Exception:
        try:
            parsed = pn.parse(phone_raw, "ID")
        except Exception:
            return {"error": f"Could not parse: {phone_raw}"}

    e164 = pn.format_number(parsed, pn.PhoneNumberFormat.E164)
    international = pn.format_number(parsed, pn.PhoneNumberFormat.INTERNATIONAL)
    national = pn.format_number(parsed, pn.PhoneNumberFormat.NATIONAL)

    region = pn.region_code_for_number(parsed)
    country = COUNTRY_NAMES.get(region) or geocoder.description_for_number(parsed, "en") or "Unknown"

    carr = carrier.name_for_number(parsed, "en") or "Unknown"
    tz_list = list(pn_tz.time_zones_for_number(parsed))

    line_type = LINE_TYPES.get(pn.number_type(parsed), "Unknown")

    return {
        "e164": e164,
        "international": international,
        "national": national,
        "country_code": f"+{parsed.country_code}",
        "region": region,
        "country": country,
        "carrier": carr,
        "line_type": line_type,
        "timezone": ", ".join(tz_list) if tz_list else "Unknown",
        "valid": pn.is_valid_number(parsed),
        "possible": pn.is_possible_number(parsed),
    }


# ============================================================
#  INDONESIAN PREFIX DATABASE (fallback)
# ============================================================

PROVIDER_DB = {
    "0811": "Telkomsel", "0812": "Telkomsel", "0813": "Telkomsel",
    "0821": "Telkomsel", "0822": "Telkomsel", "0823": "Telkomsel",
    "0852": "Telkomsel", "0853": "Telkomsel",
    "0817": "XL", "0818": "XL", "0819": "XL",
    "0859": "XL", "0877": "XL", "0878": "XL",
    "0814": "Indosat", "0815": "Indosat", "0816": "Indosat",
    "0855": "Indosat", "0856": "Indosat", "0857": "Indosat", "0858": "Indosat",
    "0895": "Tri", "0896": "Tri", "0897": "Tri", "0898": "Tri",
    "0881": "Smartfren", "0882": "Smartfren", "0883": "Smartfren",
    "0884": "Smartfren", "0885": "Smartfren", "0886": "Smartfren",
    "0887": "Smartfren", "0888": "Smartfren", "0889": "Smartfren",
    "0831": "Axis", "0832": "Axis", "0833": "Axis", "0838": "Axis",
    "0828": "Ceria", "0851": "By.U", "0899": "By.U",
}

ALL_PREFIXES = sorted(PROVIDER_DB.keys(), key=len, reverse=True)


def lookup_provider(phone: str) -> str:
    """Look up carrier — phonenumbers first, fallback to ID prefix DB."""
    # Try phonenumbers for authoritative carrier data
    if HAS_PHONENUMBERS:
        try:
            parsed = pn.parse(phone, "ID")
            carr = carrier.name_for_number(parsed, "en")
            if carr:
                return carr
        except Exception:
            pass
    # Fallback: Indonesian prefix DB
    raw = re.sub(r"[^0-9]", "", phone)
    for prefix in ALL_PREFIXES:
        if raw.startswith(prefix):
            return PROVIDER_DB[prefix]
    return "Unknown"


REGION_DB = {
    "021": "Jakarta", "031": "Surabaya", "022": "Bandung",
    "024": "Semarang", "0274": "Yogyakarta", "061": "Medan",
    "0411": "Makassar", "0541": "Samarinda", "0511": "Banjarmasin",
    "0751": "Padang", "0711": "Palembang", "0731": "Jambi",
    "0761": "Pekanbaru", "0251": "Bogor", "0261": "Bandung Utara",
    "0271": "Solo", "0341": "Malang", "0361": "Denpasar",
    "0380": "Kupang", "0431": "Manado", "0451": "Palu",
    "0561": "Pontianak", "0651": "Banda Aceh", "0741": "Jambi",
    "0778": "Batam", "0951": "Jayapura", "0981": "Ambon",
    "0902": "Ternate", "0401": "Kendari",
    "0551": "Balikpapan", "0402": "Baubau",
    "0911": "Manokwari", "0901": "Timika",
}


def lookup_region(phone: str) -> str:
    """Get region from prefix (landline) or phonenumbers timezone (mobile)."""
    # Try phonenumbers if available (best: timezone-based region)
    if HAS_PHONENUMBERS:
        try:
            parsed = pn.parse(phone, "ID")  # default region = Indonesia
            tz_list = list(pn_tz.time_zones_for_number(parsed))
            if tz_list:
                return _timezone_region(tz_list[0])
        except Exception:
            pass

    # Fallback: landline prefix region map
    raw = re.sub(r"[^0-9+]", "", phone)
    for prefix, region in sorted(REGION_DB.items(), key=lambda x: -len(x[0])):
        if raw.startswith(prefix):
            return region

    # Mobile fallback
    if raw.startswith("08") or raw.startswith("628") or raw.startswith("+628"):
        return "Nasional (Indonesia)"
    return "Unknown"


TZ_REGION = {
    "Asia/Jakarta": "Indonesia (WIB)",
    "Asia/Pontianak": "Indonesia (WIB)",
    "Asia/Makassar": "Indonesia (WITA)",
    "Asia/Jayapura": "Indonesia (WIT)",
    "Asia/Singapore": "Singapore",
    "Asia/Kuala_Lumpur": "Malaysia",
    "Asia/Manila": "Philippines",
    "Asia/Tokyo": "Japan",
    "Asia/Seoul": "Korea",
    "Asia/Shanghai": "China",
    "Asia/Kolkata": "India",
    "Europe/London": "United Kingdom",
    "Europe/Berlin": "Germany",
    "America/New_York": "USA (Eastern)",
    "America/Chicago": "USA (Central)",
    "America/Los_Angeles": "USA (Pacific)",
    "Australia/Sydney": "Australia",
}


def _timezone_region(tz: str) -> str:
    if tz in TZ_REGION:
        return TZ_REGION[tz]
    return tz.replace("_", " ").split("/")[-1]


# ============================================================
#  TRUECALLER LOOKUP
# ============================================================

async def lookup_truecaller(phone: str) -> Dict[str, Any]:
    """Look up phone number on Truecaller (public web scrape)."""
    phone_clean = re.sub(r"[^0-9+]", "", phone)
    url = f"https://www.truecaller.com/search/id/{urllib.parse.quote(phone_clean)}"
    try:
        async with prepare_client(
            timeout=15, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        ) as c:
            resp = await c.get(url)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}"}

            html = resp.text
            result = {"success": True, "url": url}
            # Extract name from page title
            m = re.search(r'<title>([^<]*)</title>', html)
            if m:
                title = m.group(1).replace("| Truecaller", "").strip()
                if title and "Truecaller" not in title:
                    result["name"] = title
            # Try alternate patterns
            for pat in [r'"name":"([^"]+)"', r'data-name="([^"]+)"']:
                m = re.search(pat, html)
                if m and m.group(1):
                    result["name"] = m.group(1)
                    break
            return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
#  GETCONTACT + SOCIAL SEARCH LINKS
# ============================================================

def getcontact_links(phone: str) -> List[Dict[str, str]]:
    """Generate direct search links for phone number platforms."""
    phone_clean = re.sub(r"[^0-9]", "", phone)
    phone_e164 = re.sub(r"[^0-9+]", "", phone)

    return [
        {"platform": "Truecaller", "url": f"https://www.truecaller.com/search/id/{phone_clean}"},
        {"platform": "GetContact", "url": f"https://www.getcontact.com/"},
        {"platform": "CallApp", "url": f"https://callapp.com/lookup/{phone_e164}"},
        {"platform": "Sync.me", "url": f"https://sync.me/search/?number={phone_e164}"},
        {"platform": "SpyDialer", "url": f"https://spydialer.com/search?phone={phone_e164}"},
        {"platform": "NumLookup", "url": f"https://www.numlookup.com/{phone_e164}"},
        {"platform": "Whoscall", "url": f"https://whoscall.com/en-US/search/{phone_e164}"},
        {"platform": "ZLOOKUP", "url": f"https://www.zlookup.com/{phone_e164}"},
        {"platform": "EmobileTracker", "url": f"https://www.emobiletracker.com/search.html?keyword={phone_clean}"},
        {"platform": "PhoneInfoga", "url": f"https://demo.phoneinfoga.crvx.fr/?number={phone_e164}"},
    ]


def phone_dorks(phone: str, country: str = "") -> List[Dict[str, str]]:
    """Generate Google dork queries for phone numbers."""
    clean = re.sub(r"[^0-9]", "", phone)
    dorks = [
        f'"{clean}" site:facebook.com',
        f'"{clean}" site:instagram.com',
        f'"{clean}" site:twitter.com',
        f'"{clean}" site:linkedin.com',
        f'"{clean}" site:wa.me',
        f'"{clean}" site:t.me',
        f'"{clean}" site:loket.com OR site:tokopedia.com OR site:shopee.co.id',
        f'"{clean}" intitle:"contact" OR intitle:"about"',
        f'"{clean}" filetype:pdf OR filetype:xlsx',
        f'"{clean}" "phone" OR "whatsapp" OR "telegram"',
        f'"{clean}" site:carousell.sg OR site:olx.co.id',
        f'"{clean}" site:github.com OR site:gitlab.com',
    ]
    if country:
        dorks.append(f'"{clean}" location:{country}')
    return [{"query": d, "url": f"https://www.google.com/search?q={urllib.parse.quote(d)}"} for d in dorks]


# ============================================================
#  SOCIAL PLATFORM CHECKS (ignorant-based)
# ============================================================

async def check_instagram(phone: str, country_code: str = "") -> Dict[str, Any]:
    phone_raw = f"{country_code}{phone}"
    body = json.dumps({"login_attempt_count": "0", "directly_sign_in": "true",
                       "source": "default", "q": phone_raw, "ig_sig_key_version": "4"})
    sig_key = "e6358aeede676184b9fe702b30f4fd35e71744605e39d2181a34cede076b3c33"
    sig = hmac.new(sig_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    signed = f"ig_sig_key_version=4&signed_body={sig}.{urllib.parse.quote_plus(body)}"
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://i.instagram.com/api/v1/users/lookup/",
                headers={"User-Agent": "Instagram 101.0.0.15.120", "Content-Type": "application/x-www-form-urlencoded", "Accept-Language": "en-US"},
                content=signed)
            if r.status_code == 200:
                rj = r.json()
                return {"platform": "instagram", "registered": rj.get("message") != "No users found"}
    except: pass
    return {"platform": "instagram", "registered": False}


async def check_snapchat(phone: str, country_code: str = "") -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://accounts.snapchat.com/accounts/get_phone_verification_status",
                json={"phoneNumber": f"{country_code}{phone}", "countryCode": country_code or "US"},
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
            if r.status_code == 200:
                d = r.json()
                return {"platform": "snapchat", "registered": d.get("isVerified") or d.get("hasSnapchat", False)}
    except: pass
    return {"platform": "snapchat", "registered": False}


async def check_amazon(phone: str, country_code: str = "") -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://www.amazon.com/ap/register",
                data={"email": "", "passwordCheck": "", "create": "0", "phoneNumber": f"{country_code}{phone}", "metadata1": ""},
                headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
            return {"platform": "amazon", "registered": "exists" in r.text.lower()}
    except: pass
    return {"platform": "amazon", "registered": False}


async def check_whatsapp(phone: str, country_code: str = "") -> Dict[str, Any]:
    raw = re.sub(r"[^0-9]", "", f"{country_code}{phone}")
    try:
        async with prepare_client(timeout=10, follow_redirects=False) as c:
            r = await c.get(f"https://wa.me/{raw}", headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 302:
                return {"platform": "whatsapp", "registered": "phone=" in r.headers.get("location", "")}
            return {"platform": "whatsapp", "registered": r.status_code == 200}
    except: pass
    return {"platform": "whatsapp", "registered": False}


async def check_telegram(phone: str, country_code: str = "") -> Dict[str, Any]:
    raw = re.sub(r"[^0-9+]", "", phone)
    if not raw.startswith("+"): raw = f"+{raw}"
    try:
        async with prepare_client(timeout=10, follow_redirects=True) as c:
            r = await c.get(f"https://t.me/{raw}", headers={"User-Agent": "Mozilla/5.0"})
            return {"platform": "telegram", "registered": r.status_code == 200 and "tgme_page_title" in r.text}
    except: pass
    return {"platform": "telegram", "registered": False}


async def check_signal(phone: str, country_code: str = "") -> Dict[str, Any]:
    raw = re.sub(r"[^0-9+]", "", f"+{country_code}{phone}")
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get(f"https://signal.me/#p/{raw}", headers={"User-Agent": "Mozilla/5.0"})
            return {"platform": "signal", "registered": r.status_code == 200}
    except: pass
    return {"platform": "signal", "registered": False}


PHONE_CHECKS = [check_instagram, check_snapchat, check_amazon, check_whatsapp, check_telegram, check_signal]


# ============================================================
#  VERIPHONE API (free tier: 1000 req/mo, city-level for ID)
# ============================================================

async def lookup_veriphone(phone: str) -> Dict[str, Any]:
    """Get city-level geolocation via Veriphone API.

    Requires VERIPHONE_API_KEY in .env. Free tier: 1000 requests/month.
    Returns: {location, carrier, line_type, country, ...} or {}.
    Works for Indonesian phone numbers (unlike numverify free tier).
    """
    from ..config import Config
    key = Config.VERIPHONE_API_KEY
    if not key:
        return {}

    clean = re.sub(r"[^0-9]", "", phone)
    url = f"https://api.veriphone.io/v2/verify?phone={clean}&key={key}"

    try:
        async with prepare_client(timeout=10) as c:
            resp = await c.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "location": data.get("location", ""),
                    "carrier": data.get("carrier", ""),
                    "line_type": data.get("line_type", ""),
                    "country": data.get("country", ""),
                    "country_code": data.get("country_code", ""),
                }
    except Exception:
        pass
    return {}


# ============================================================
#  NUMVERIFY API (free tier: 1000 req/mo, ID limited location)
# ============================================================

async def lookup_numverify(phone: str) -> Dict[str, Any]:
    """Get city-level geolocation via numverify API (apilayer).

    Requires NUMVERIFY_API_KEY in .env. Free tier: 1000 requests/month.
    Returns: {location, carrier, line_type, country_name, ...} or {}.
    """
    from ..config import Config
    key = Config.NUMVERIFY_API_KEY
    if not key:
        return {}

    clean = re.sub(r"[^0-9]", "", phone)
    url = f"https://api.apilayer.com/number_verification/validate?apikey={key}&number={clean}"

    try:
        async with prepare_client(timeout=10) as c:
            resp = await c.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("valid"):
                    return {
                        "location": data.get("location", ""),
                        "carrier": data.get("carrier", ""),
                        "line_type": data.get("line_type", ""),
                        "country_name": data.get("country_name", ""),
                        "country_code": data.get("country_code", ""),
                        "local_format": data.get("local_format", ""),
                        "international_format": data.get("international_format", ""),
                    }
    except Exception:
        pass
    return {}


# ============================================================
#  MAIN API
# ============================================================

async def scan_phone(phone: str, country_code: str = "") -> List[Dict[str, Any]]:
    """Run all phone platform checks + analysis in parallel.

    Data flow:
      1. phonenumbers (always) → carrier, line_type, timezone, country, e164
      2. Veriphone (if key) → override region with city-level
      3. Numverify (fallback) → override region if veriphone failed
      4. Prefix DB (fallback) → if phonenumbers not installed
    """
    tfn = lambda f: f(phone, country_code)
    results = await asyncio.gather(*[tfn(c) for c in PHONE_CHECKS], return_exceptions=True)
    output = [r for r in results if isinstance(r, dict)]

    # Step 1: Base data — phonenumbers always if available
    if HAS_PHONENUMBERS:
        analysis = analyze_number(phone)
        carrier = analysis.get("carrier", "")
        region = lookup_region(phone)      # timezone-based
        line_type = analysis.get("line_type", "")
        country = analysis.get("country", "")
        timezone = analysis.get("timezone", "")
    else:
        carrier = lookup_provider(phone)   # hardcoded Indo prefix DB
        region = lookup_region(phone)      # "Nasional (Indonesia)"
        line_type = ""
        country = ""
        timezone = ""

    # Step 2: City-level enrichment — Veriphone (best for ID) → Numverify (fallback)
    veriphone = await lookup_veriphone(phone)
    if veriphone.get("location"):
        region = veriphone["location"]
        carrier = veriphone.get("carrier") or carrier
    else:
        numverify = await lookup_numverify(phone)
        if numverify.get("location"):
            region = numverify["location"]
            carrier = numverify.get("carrier") or carrier

    # Step 3: Inject into every platform result
    for r in output:
        r["carrier"] = carrier
        r["region"] = region
        r["line_type"] = line_type
        r["country"] = country
        r["timezone"] = timezone
        # Legacy compat
        r["provider"] = carrier

    return output


async def full_scan(phone: str) -> Dict[str, Any]:
    """Full phone investigation: analysis + scanner + Truecaller + links."""
    analysis = analyze_number(phone)
    platforms = await scan_phone(phone)
    truecaller = await lookup_truecaller(phone)
    links = getcontact_links(phone)
    dorks = phone_dorks(phone, analysis.get("country", ""))

    return {
        "phone": phone,
        "analysis": analysis,
        "platforms": platforms,
        "truecaller": truecaller,
        "search_links": links,
        "google_dorks": dorks,
    }


def summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    registered = [r["platform"] for r in results if r.get("registered")]
    return {
        "platforms_checked": len(results),
        "registered_count": len(registered),
        "registered_platforms": registered,
    }
