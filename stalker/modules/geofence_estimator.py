"""Geofence Estimator — estimate target's physical location from all data points.

Aggregates location clues from:
- Timezone estimation (Pattern of Life)
- Reddit location subreddits (r/jakarta, r/indonesia, etc.)
- Profile location fields (maigret found_sites)
- Language detection (Indonesian = Indonesia)
- Phone carrier (Indonesian carrier = Indonesia)
- EXIF GPS from profile photos
- IP geolocation from email headers
- Domain server location
- WhatsApp carrier data

Outputs: confidence-weighted location estimate.
No network calls — pure aggregation of already-collected data.
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from collections import Counter

# Indonesian city/region name patterns
ID_CITIES = {
    "jakarta": ("Jakarta", "DKI Jakarta", "Indonesia"),
    "bandung": ("Bandung", "Jawa Barat", "Indonesia"),
    "surabaya": ("Surabaya", "Jawa Timur", "Indonesia"),
    "medan": ("Medan", "Sumatera Utara", "Indonesia"),
    "makassar": ("Makassar", "Sulawesi Selatan", "Indonesia"),
    "semarang": ("Semarang", "Jawa Tengah", "Indonesia"),
    "palembang": ("Palembang", "Sumatera Selatan", "Indonesia"),
    "depok": ("Depok", "Jawa Barat", "Indonesia"),
    "tangerang": ("Tangerang", "Banten", "Indonesia"),
    "bekasi": ("Bekasi", "Jawa Barat", "Indonesia"),
    "yogyakarta": ("Yogyakarta", "DIY", "Indonesia"),
    "jogja": ("Yogyakarta", "DIY", "Indonesia"),
    "malang": ("Malang", "Jawa Timur", "Indonesia"),
    "bogor": ("Bogor", "Jawa Barat", "Indonesia"),
    "batam": ("Batam", "Riau", "Indonesia"),
    "pekanbaru": ("Pekanbaru", "Riau", "Indonesia"),
    "bali": ("Bali", "Bali", "Indonesia"),
    "denpasar": ("Denpasar", "Bali", "Indonesia"),
    "lombok": ("Lombok", "NTB", "Indonesia"),
    "kalimantan": ("Kalimantan", "Kalimantan", "Indonesia"),
    "balikpapan": ("Balikpapan", "Kalimantan Timur", "Indonesia"),
    "samarinda": ("Samarinda", "Kalimantan Timur", "Indonesia"),
    "pontianak": ("Pontianak", "Kalimantan Barat", "Indonesia"),
    "aceh": ("Aceh", "Aceh", "Indonesia"),
    "padang": ("Padang", "Sumatera Barat", "Indonesia"),
    "lampung": ("Lampung", "Lampung", "Indonesia"),
    "manado": ("Manado", "Sulawesi Utara", "Indonesia"),
    "kupang": ("Kupang", "NTT", "Indonesia"),
    "ambon": ("Ambon", "Maluku", "Indonesia"),
    "jayapura": ("Jayapura", "Papua", "Indonesia"),
}

COUNTRY_INDICATORS = {
    "indonesia": ("Indonesia", "ID", 90),
    "malaysia": ("Malaysia", "MY", 90),
    "singapore": ("Singapore", "SG", 90),
    "philippines": ("Philippines", "PH", 90),
    "thailand": ("Thailand", "TH", 90),
    "vietnam": ("Vietnam", "VN", 90),
    "india": ("India", "IN", 90),
    "australia": ("Australia", "AU", 90),
    "usa": ("United States", "US", 90),
    "uk": ("United Kingdom", "GB", 90),
    "germany": ("Germany", "DE", 90),
    "netherlands": ("Netherlands", "NL", 90),
    "japan": ("Japan", "JP", 90),
    "china": ("China", "CN", 90),
    "saudi": ("Saudi Arabia", "SA", 85),
    "uae": ("UAE", "AE", 85),
    "qatar": ("Qatar", "QA", 85),
}

TZ_TO_COUNTRY = {
    7: ("Indonesia (WIB)", "ID", 70),
    8: ("Indonesia/Singapore/Malaysia", "ID/SG/MY", 60),
    9: ("Indonesia (WIT)/Japan/Korea", "ID/JP/KR", 60),
    -5: ("USA East", "US", 60),
    -8: ("USA West", "US", 60),
    0: ("UK/West Europe", "GB/EU", 55),
    1: ("Central Europe", "EU", 55),
    5.5: ("India", "IN", 65),
    10: ("Australia East", "AU", 65),
    3: ("Moscow/Arab", "RU/SA", 55),
}

def _normalize(text: str) -> str:
    return text.lower().strip()


def collect_location_clues(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all location clues from investigation result."""
    clues = []

    def add(source: str, location: str, confidence: int, detail: str = ""):
        if location:
            clues.append({"source": source, "location": location,
                          "confidence": confidence, "detail": detail})

    # 1. Explicit profile location fields
    for site in result.get("maigret", {}).get("found_sites", []):
        loc = site.get("location") or site.get("ids_data", {}).get("location","")
        if loc and len(loc) > 1:
            add(f"profile:{site.get('site_name','')}", loc, 75, site.get("url_user",""))

    # 2. GitHub location
    gh_loc = result.get("github_intel", {}).get("profile", {}).get("location","")
    if gh_loc: add("github_profile", gh_loc, 80, "")

    # 3. WhatsApp carrier → country
    wa = result.get("whatsapp_intel", {})
    if wa.get("country", {}).get("country"):
        add("whatsapp_carrier", wa["country"]["country"], 70, wa["country"].get("carrier",""))

    # 4. Timezone estimation → country
    tz = result.get("pattern_of_life", {}).get("timezone", {})
    tz_offset = tz.get("utc_offset")
    if tz_offset is not None and tz.get("confidence_pct", 0) >= 40:
        tz_info = TZ_TO_COUNTRY.get(tz_offset)
        if tz_info:
            add("timezone_analysis", tz_info[0], tz_info[2],
                f"UTC{'+' if tz_offset >= 0 else ''}{tz_offset} peak activity")

    # 5. Reddit location subreddits
    activity = result.get("reddit_intel", {}).get("activity", {})
    for sub in activity.get("location_clues", []):
        sub_lower = _normalize(sub)
        for city_key, (city, province, country) in ID_CITIES.items():
            if city_key in sub_lower:
                add("reddit_subreddit", f"{city}, {province}, {country}", 65, f"r/{sub}")
                break
        for country_key, (country_name, code, conf) in COUNTRY_INDICATORS.items():
            if country_key in sub_lower:
                add("reddit_subreddit", country_name, 60, f"r/{sub}")
                break

    # 6. Language → country
    lang = result.get("writing_fingerprint", {}).get("aggregate", {}).get("language","")
    if lang == "Indonesian":
        add("language_detection", "Indonesia", 55, "Indonesian language detected in posts/bios")
    phone_carrier = wa.get("country", {}).get("carrier","")
    if "telkomsel" in phone_carrier.lower() or "xl" in phone_carrier.lower() or \
       "indosat" in phone_carrier.lower() or "tri" in phone_carrier.lower():
        add("phone_carrier", "Indonesia", 85, phone_carrier)

    # 7. IP geolocation from email headers
    header_geo = result.get("email_header_forensics", {}).get("geo", {})
    if header_geo.get("country"):
        add("email_header_ip", f"{header_geo.get('city','')} {header_geo['country']}".strip(),
            90, f"IP: {result.get('email_header_forensics',{}).get('originating_ip','')}")

    # 8. Domain server geo
    domain_geo = result.get("domain_intel", {}).get("server_geo", {})
    if domain_geo.get("country"):
        add("domain_server", domain_geo["country"], 40,
            f"Server IP: {domain_geo.get('ip','')}")

    # 9. Scan text in bios for city/country mentions
    all_bios = " ".join(
        [s.get("bio","") or "" for s in result.get("maigret",{}).get("found_sites",[])]
        + [result.get("telegram",{}).get("bio","") or ""]
    ).lower()
    for city_key, (city, province, country) in ID_CITIES.items():
        if city_key in all_bios:
            add("bio_text_scan", f"{city}, {province}, {country}", 70, f"Mentioned in bio")
    for country_key, (country_name, code, conf) in COUNTRY_INDICATORS.items():
        if country_key in all_bios:
            add("bio_text_scan", country_name, 60, "Mentioned in bio")

    return clues


def estimate_location(clues: List[Dict]) -> Dict[str, Any]:
    """Aggregate clues into best location estimate."""
    if not clues:
        return {"confidence": 0, "note": "No location clues found"}

    # Weight by confidence
    location_scores: Dict[str, float] = {}
    location_clues_map: Dict[str, List] = {}

    for clue in clues:
        loc = clue["location"]
        conf = clue["confidence"]
        location_scores[loc] = location_scores.get(loc, 0) + conf
        location_clues_map.setdefault(loc, []).append(clue)

    # Find highest scored location
    best_loc = max(location_scores, key=location_scores.get)
    best_score = location_scores[best_loc]
    max_possible = len(clues) * 90
    overall_confidence = min(95, int(best_score / max(max_possible, 1) * 100 * 2))

    # Extract city/country from best location
    parts = best_loc.split(",")
    city = parts[0].strip() if parts else best_loc
    country = parts[-1].strip() if len(parts) > 1 else best_loc

    return {
        "best_estimate": best_loc,
        "city": city,
        "country": country,
        "confidence_pct": overall_confidence,
        "supporting_clues": location_clues_map.get(best_loc, []),
        "all_scored": dict(sorted(location_scores.items(), key=lambda x: -x[1])[:5]),
        "total_clues": len(clues),
    }


def full_geofence(result: Dict[str, Any]) -> Dict[str, Any]:
    clues = collect_location_clues(result)
    estimate = estimate_location(clues)
    return {
        "clues": clues,
        "estimate": estimate,
    }


def format_geofence_report(data: Dict[str, Any]) -> str:
    BOLD="\033[1m"; CYAN="\033[36m"; YELLOW="\033[33m"; GREEN="\033[32m"; NC="\033[0m"
    est = data.get("estimate", {})
    clues = data.get("clues", [])

    lines = [f"\n{BOLD}  ┌─── GEOFENCE / LOCATION ESTIMATE ───┐{NC}"]
    if not est.get("best_estimate"):
        lines.append("  No location data collected"); return "\n".join(lines)

    conf = est.get("confidence_pct", 0)
    color = GREEN if conf >= 70 else YELLOW if conf >= 40 else ""
    lines.append(f"  Best estimate: {BOLD}{est.get('best_estimate','')}{NC}")
    lines.append(f"  Confidence:    {color}{conf}%{NC}")
    lines.append(f"  Total clues:   {est.get('total_clues',0)}")

    lines.append(f"\n  {BOLD}Evidence:{NC}")
    for clue in sorted(clues, key=lambda c: -c["confidence"])[:8]:
        lines.append(f"  [{clue['confidence']}%] {clue['source']}: {CYAN}{clue['location']}{NC}")
        if clue.get("detail"): lines.append(f"          {clue['detail'][:60]}")

    if est.get("all_scored") and len(est["all_scored"]) > 1:
        lines.append(f"\n  {BOLD}Alternative locations:{NC}")
        for loc, score in list(est["all_scored"].items())[1:4]:
            lines.append(f"  {loc} (score: {score:.0f})")

    return "\n".join(lines)
