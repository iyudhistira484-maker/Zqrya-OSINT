"""Cyber Intelligence Risk Scorer.

Aggregates all investigation findings into a structured threat/risk profile.
Outputs:
- Risk score 0-100 (Minimal / Low / Moderate / High / Critical)
- Risk breakdown by category
- Key findings summary
- Recommended follow-up actions
- Threat indicators list (IOCs)
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from datetime import datetime

RISK_LEVELS = [
    (0,  20,  "MINIMAL",  "\033[32m"),   # green
    (21, 40,  "LOW",      "\033[36m"),   # cyan
    (41, 60,  "MODERATE", "\033[33m"),   # yellow
    (61, 80,  "HIGH",     "\033[31m"),   # red
    (81, 100, "CRITICAL", "\033[35m"),   # magenta
]

def get_risk_level(score: int) -> Tuple[str, str]:
    for lo, hi, label, color in RISK_LEVELS:
        if lo <= score <= hi:
            return label, color
    return "UNKNOWN", "\033[0m"

def calculate_risk(investigation_result: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate risk score from full investigation result.
    
    Scoring categories (max points each):
    - Digital footprint size     : 20 pts
    - Breach & credential leaks  : 25 pts
    - Dark web presence          : 15 pts
    - Personal data exposure     : 20 pts
    - Social engineering risk    : 10 pts
    - Stealth/evasion indicators : 10 pts
    """
    score = 0
    breakdown = {}
    findings = []
    iocs = []  # Indicators of Compromise / Interest
    recommendations = []

    # ── 1. Digital Footprint (0-20) ──────────────────────────
    fp_score = 0
    maigret = investigation_result.get("maigret", {})
    profiles_found = len(maigret.get("found_sites", []))
    custom_apis = investigation_result.get("custom_apis", {})
    api_success = sum(1 for v in custom_apis.values() if isinstance(v,dict) and v.get("success"))

    if profiles_found >= 50: fp_score += 20
    elif profiles_found >= 20: fp_score += 15
    elif profiles_found >= 10: fp_score += 10
    elif profiles_found >= 5: fp_score += 7
    elif profiles_found >= 1: fp_score += 4

    if api_success >= 3: fp_score += 5
    fp_score = min(fp_score, 20)
    breakdown["digital_footprint"] = {"score": fp_score, "max": 20, "detail": f"{profiles_found} profiles found across {maigret.get('total_checked',0)} platforms"}
    if profiles_found >= 20: findings.append(f"Extensive digital footprint: {profiles_found} social profiles")
    score += fp_score

    # ── 2. Breach & Credentials (0-25) ────────────────────────
    breach_score = 0
    breach = investigation_result.get("breach", {})
    hudson_infections = (breach.get("username", {}) or breach.get("email", {})).get("total_infections", 0)
    pw_leaks = investigation_result.get("password_leak", {}).get("leaked_count", 0)
    email_scan = investigation_result.get("email_scan", {})
    email_registered = sum(1 for v in email_scan.values() if isinstance(v,dict) and v.get("registered")) if isinstance(email_scan, dict) else 0

    if hudson_infections >= 5: breach_score += 20
    elif hudson_infections >= 2: breach_score += 15
    elif hudson_infections >= 1: breach_score += 10
    if pw_leaks >= 3: breach_score += 10
    elif pw_leaks >= 1: breach_score += 6
    breach_score = min(breach_score, 25)
    breakdown["breach_credentials"] = {"score": breach_score, "max": 25, "detail": f"{hudson_infections} infostealer infection(s), {pw_leaks} password leak(s)"}
    if hudson_infections > 0:
        findings.append(f"ACTIVE INFOSTEALER: {hudson_infections} Hudson Rock infection(s) — credentials likely compromised")
        iocs.append(f"hudson_rock_infections:{hudson_infections}")
        recommendations.append("Check HaveIBeenPwned and change all passwords immediately")
    if pw_leaks > 0:
        findings.append(f"Password leaks found ({pw_leaks}) — credential stuffing risk")
        recommendations.append("Enable 2FA on all accounts with leaked credentials")
    score += breach_score

    # ── 3. Dark Web Presence (0-15) ───────────────────────────
    dw_score = 0
    dark_web = investigation_result.get("dark_web", {})
    dw_found = sum(1 for v in dark_web.values() if isinstance(v,dict) and v.get("found")) if isinstance(dark_web, dict) else 0
    dw_records = sum(v.get("count",0) for v in dark_web.values() if isinstance(v,dict) and v.get("found")) if isinstance(dark_web, dict) else 0

    if dw_found >= 3: dw_score += 15
    elif dw_found >= 2: dw_score += 10
    elif dw_found >= 1: dw_score += 6
    if dw_records >= 10: dw_score += 5
    dw_score = min(dw_score, 15)
    breakdown["dark_web"] = {"score": dw_score, "max": 15, "detail": f"Found in {dw_found} dark web source(s) ({dw_records} records)"}
    if dw_found > 0:
        findings.append(f"Dark web presence: {dw_found} paste/breach source(s)")
        iocs.append(f"darkweb_sources:{dw_found}")
    score += dw_score

    # ── 4. Personal Data Exposure (0-20) ──────────────────────
    personal_score = 0
    text_profile = investigation_result.get("text_profile", {})
    phones_found = len(text_profile.get("phones", []))
    emails_found = len(text_profile.get("emails", []))
    crypto_found = len(text_profile.get("crypto", []))
    real_names = maigret.get("real_names", [])
    telegram = investigation_result.get("telegram", {})
    phone_scan = investigation_result.get("phone_scan", {})
    phone_platforms = sum(1 for v in phone_scan if isinstance(v,dict) and v.get("registered")) if isinstance(phone_scan, list) else 0

    if real_names: personal_score += 5
    if phones_found >= 1: personal_score += 5; iocs.append(f"exposed_phones:{phones_found}")
    if emails_found >= 2: personal_score += 4; iocs.append(f"exposed_emails:{emails_found}")
    if crypto_found >= 1: personal_score += 3; iocs.append(f"crypto_addresses:{crypto_found}")
    if telegram.get("success"): personal_score += 3
    if phone_platforms >= 3: personal_score += 5
    personal_score = min(personal_score, 20)
    breakdown["personal_data"] = {"score": personal_score, "max": 20, "detail": f"Real name(s): {len(real_names)}, phones: {phones_found}, emails: {emails_found}"}
    if phones_found > 0: findings.append(f"Phone number(s) exposed in public profiles: {phones_found}")
    if real_names: findings.append(f"Real name identified: {', '.join(real_names[:2])}")
    score += personal_score

    # ── 5. Social Engineering Risk (0-10) ─────────────────────
    social_score = 0
    face_search = investigation_result.get("face_search", {})
    reverse_image = investigation_result.get("reverse_image", {})
    avatar_urls = maigret.get("avatar_urls", [])
    linktree = investigation_result.get("linktree", {})
    recursive = investigation_result.get("recursive", {})

    if avatar_urls: social_score += 3
    if face_search: social_score += 3
    if linktree and linktree.get("found"): social_score += 2
    if recursive and recursive.get("discovered_usernames"): social_score += 2
    social_score = min(social_score, 10)
    breakdown["social_engineering"] = {"score": social_score, "max": 10, "detail": f"{len(avatar_urls)} avatar(s) found, face search: {'yes' if face_search else 'no'}"}
    if avatar_urls: recommendations.append("Run face search to find other accounts with same photo")
    score += social_score

    # ── 6. Stealth Indicators (0-10) ──────────────────────────
    stealth_score = 0
    # IP data from profiles
    ip_data = investigation_result.get("ip_track", {})
    if ip_data:
        proxy_ips = [ip for ip, d in ip_data.items() if isinstance(d,dict) and d.get("is_proxy")]
        if proxy_ips: stealth_score += 7; iocs.append(f"vpn_proxy_detected:{len(proxy_ips)}_ip(s)")
    # Stealth mode indicators in profile bios
    all_bios = " ".join(s.get("bio","") for s in maigret.get("found_sites",[]) if s.get("bio"))
    if any(kw in all_bios.lower() for kw in ["vpn","tor ","proxy","anon","anonymous","privacy"]):
        stealth_score += 3
    stealth_score = min(stealth_score, 10)
    breakdown["stealth_indicators"] = {"score": stealth_score, "max": 10, "detail": "VPN/proxy/anonymity tool usage detected" if stealth_score > 0 else "No stealth indicators found"}
    if stealth_score >= 7: findings.append("VPN/proxy/Tor usage detected — subject is privacy-conscious")
    score += stealth_score

    # ── Finalize ──────────────────────────────────────────────
    score = min(score, 100)
    level, color = get_risk_level(score)

    # Default recommendations if none added
    if not recommendations:
        if score >= 60:
            recommendations.append("Consider formal digital forensics investigation")
        elif score >= 40:
            recommendations.append("Monitor subject's digital activity regularly")
        else:
            recommendations.append("Limited digital footprint — continue monitoring for new activity")

    return {
        "score": score,
        "level": level,
        "color": color,
        "breakdown": breakdown,
        "key_findings": findings,
        "iocs": iocs,
        "recommendations": recommendations,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

def format_risk_report(risk: Dict[str, Any]) -> str:
    """Format risk report for terminal display."""
    NC = "\033[0m"
    BOLD = "\033[1m"
    lines = []
    color = risk.get("color", "")
    score = risk.get("score", 0)
    level = risk.get("level", "?")

    lines.append(f"\n{BOLD}  ┌─── CYBER INTELLIGENCE RISK SCORE ───┐{NC}")
    lines.append(f"{BOLD}  │  {color}{score}/100  {level}{NC}{BOLD}                        │{NC}")
    lines.append(f"{BOLD}  └─────────────────────────────────────┘{NC}")

    if risk.get("key_findings"):
        lines.append(f"\n{BOLD}  Key Findings:{NC}")
        for f in risk["key_findings"]:
            lines.append(f"  ⚡ {f}")

    lines.append(f"\n{BOLD}  Score Breakdown:{NC}")
    for cat, d in risk.get("breakdown", {}).items():
        bar_len = int((d["score"] / d["max"]) * 15) if d["max"] > 0 else 0
        bar = "█" * bar_len + "░" * (15 - bar_len)
        cat_name = cat.replace("_"," ").title()
        lines.append(f"  {cat_name:<22} [{bar}] {d['score']}/{d['max']}")
        lines.append(f"                         {d['detail']}")

    if risk.get("recommendations"):
        lines.append(f"\n{BOLD}  Recommended Actions:{NC}")
        for r in risk["recommendations"]:
            lines.append(f"  → {r}")

    if risk.get("iocs"):
        lines.append(f"\n{BOLD}  Indicators:{NC}")
        for ioc in risk["iocs"]:
            lines.append(f"  ⚠  {ioc}")

    lines.append(f"\n  Generated: {risk.get('generated_at','')}")
    return "\n".join(lines)
