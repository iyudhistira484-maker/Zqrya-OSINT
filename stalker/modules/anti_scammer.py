"""Anti-scammer toolkit — report + expose phone numbers on platforms.

Legal, ethical approach to making scammers jera (deter):
  1. Report to platforms (WhatsApp, Telegram)
  2. Report to Indonesian authorities (Polri Cyber, Telkomsel)
  3. Generate public-facing evidence report
  4. Single legal warning message via WhatsApp

No spam bombing. No illegal harassment.
"""

from __future__ import annotations
from typing import Dict, Any, List
import re
import webbrowser


def report_whatsapp(phone: str) -> str:
    """Get WhatsApp direct chat URL to report via App."""
    raw = re.sub(r"[^0-9]", "", phone)
    # Menggunakan wa.me agar otomatis membuka aplikasi WhatsApp 
    # di mana pengguna bisa langsung menekan tombol "Report/Block"
    return f"https://wa.me/{raw}"


def report_telegram(phone: str) -> str:
    """Get Telegram abuse report URL."""
    return "https://telegram.org/support"


def report_signal(phone: str) -> str:
    """Get Signal abuse report URL."""
    raw = re.sub(r"[^0-9+]", "", phone)
    if not raw.startswith("+"):
        raw = f"+{raw}"
    return f"https://signal.org/contact/?number={raw}"


def report_telkomsel() -> str:
    """Telkomsel abuse contact."""
    return "https://www.telkomsel.com/support/contact-us"


def report_polri_cyber() -> str:
    """Indonesian Cyber Police (Patroli Siber)."""
    return "https://patrolisiber.id"


def report_all(phone: str) -> List[Dict[str, str]]:
    """Get all report links for a phone number."""
    raw = re.sub(r"[^0-9]", "", phone)
    return [
        {"action": "Report to WhatsApp", "url": report_whatsapp(raw), "method": "Web form"},
        {"action": "Report via Telegram", "url": report_telegram(raw), "method": "Support form"},
        {"action": "Report to Signal", "url": report_signal(raw), "method": "Contact form"},
        {"action": "Report to Telkomsel", "url": report_telkomsel(), "method": "Customer service"},
        {"action": "Report to Polri Cyber", "url": report_polri_cyber(), "method": "Patroli Siber"},
        {"action": "GetContact Search", "url": f"https://www.getcontact.com/", "method": "App required"},
        {"action": "Truecaller Search", "url": f"https://www.truecaller.com/search/id/{raw}", "method": "Web search"},
    ]


def generate_warning_message(phone_info: Dict[str, Any]) -> str:
    """Generate a single legal warning message for the scammer."""
    analysis = phone_info.get("analysis", {})
    platforms = phone_info.get("platforms", [])
    registered = [p["platform"] for p in platforms if p.get("registered")]
    provider = analysis.get("carrier", "Unknown")

    lines = [
        "PERINGATAN — WARNING",
        "",
        f"Nomor ini ({analysis.get('international', phone_info.get('phone', ''))}) "
        "telah diidentifikasi sebagai nomor penipuan/scam.",
        "",
        f"Data Anda telah dikumpulkan melalui OSINT dan akan dilaporkan ke:",
        f"- WhatsApp / Telegram / Signal (platform tempat Anda terdaftar: {', '.join(registered[:3]) or 'none'})",
        f"- Provider ({provider})",
        f"- Polri Cyber Crime (patrolisiber.id)",
        f"- GetContact / Truecaller (public spam database)",
        "",
        "Hentikan aktivitas penipuan Anda segera.",
        "Bukti digital telah disimpan dan siap diserahkan ke pihak berwajib.",
        "",
        f"— Stalker OSINT Tool",
    ]
    return "\n".join(lines)


def exposure_report(phone_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a public-facing evidence report for authorities."""
    analysis = phone_info.get("analysis", {})
    platforms = phone_info.get("platforms", [])
    truecaller = phone_info.get("truecaller", {})
    links = phone_info.get("search_links", [])

    registered = [{
        "platform": p["platform"],
        "registered": p.get("registered", False),
        "provider": p.get("provider", ""),
        "region": p.get("region", ""),
    } for p in platforms]

    return {
        "phone": phone_info.get("phone", ""),
        "carrier": analysis.get("carrier", "Unknown"),
        "country": analysis.get("country", "Unknown"),
        "line_type": analysis.get("line_type", "Unknown"),
        "e164": analysis.get("e164", ""),
        "valid": analysis.get("valid", False),
        "registered_platforms": registered,
        "truecaller_name": truecaller.get("name", "Not found"),
        "report_links": report_all(phone_info.get("phone", "")),
        "google_dork_links": [
            {"query": d["query"], "url": d["url"]}
            for d in phone_info.get("google_dorks", [])
        ],
    }
