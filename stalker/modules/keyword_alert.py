"""Keyword Alert System — flag dangerous/scam/fraud indicators in profiles.

Scans all collected text (bios, posts, comments, profile data) for:
- Scam/fraud keywords (penipu, scammer, fraud, etc.)  
- Extremist / threat content
- Drug/illegal trade indicators
- Doxing / privacy violation indicators
- Suspicious behavioral patterns
- Indonesian-specific scam patterns (slot, judi, pinjol, dll)

Returns flagged content with severity levels.
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import re

# Severity: CRITICAL=4, HIGH=3, MEDIUM=2, LOW=1
KEYWORD_DB: Dict[str, List[Tuple[str, int]]] = {
    "scam_fraud": [
        ("scammer", 3), ("penipu", 3), ("penipuan", 3), ("fraud", 3),
        ("fake account", 3), ("akun palsu", 3), ("love scam", 3),
        ("money mule", 4), ("money transfer", 2), ("western union", 2),
        ("gift card", 2), ("bitcoin scam", 3), ("investment scam", 3),
        ("ponzi", 3), ("pyramid scheme", 3), ("skema ponzi", 3),
        ("penipu online", 4), ("tipu", 2), ("modus", 2),
    ],
    "gambling_illegal": [
        ("judi online", 3), ("slot gacor", 3), ("togel", 2), ("bandar", 2),
        ("situs judi", 3), ("casino online", 2), ("betting", 2),
        ("perjudian", 3), ("rtp slot", 3), ("maxwin", 2),
    ],
    "pinjol_predatory": [
        ("pinjol", 3), ("pinjaman online", 2), ("pinjaman cepat", 2),
        ("kredit tanpa jaminan", 2), ("bunga harian", 3), ("debt collector", 2),
        ("penagihan", 2), ("illegal lending", 3),
    ],
    "threats_violence": [
        ("will kill", 4), ("death threat", 4), ("ancam bunuh", 4),
        ("ancaman", 2), ("saya akan", 2), ("hack you", 3),
        ("doxxed", 3), ("swat", 3), ("bomb", 3),
    ],
    "illegal_trade": [
        ("jual akun", 2), ("jual followers", 2), ("jual data", 3),
        ("data bocor", 3), ("database leak", 3), ("sell account", 2),
        ("carding", 4), ("cc dump", 4), ("fullz", 4), ("cvv shop", 4),
        ("phishing kit", 4), ("malware", 3), ("rat tool", 3),
        ("exploit", 2), ("zero day", 3), ("botnet", 3),
    ],
    "extremist": [
        ("jihad", 2), ("takfir", 3), ("kafir", 1),
        ("infidel", 1), ("die in a fire", 3), ("terrorist", 2),
    ],
    "doxxing": [
        ("ktp", 2), ("no hp", 2), ("alamat rumah", 3), ("dox", 3),
        ("personal info", 2), ("home address", 3), ("leaked identity", 3),
        ("foto ktp", 4), ("nomor rekening", 2),
    ],
    "impersonation": [
        ("official account", 1), ("akun resmi", 1), ("bukan saya", 1),
        ("impersonating", 3), ("fake celebrity", 3), ("verified fake", 3),
    ],
}

ALL_KEYWORDS = [(kw, sev, cat) for cat, pairs in KEYWORD_DB.items() for kw, sev in pairs]


def scan_text(text: str, source: str = "unknown") -> List[Dict[str, Any]]:
    """Scan text for keyword alerts. Returns list of findings."""
    if not text: return []
    text_lower = text.lower()
    findings = []
    for kw, severity, category in ALL_KEYWORDS:
        if kw.lower() in text_lower:
            idx = text_lower.find(kw.lower())
            context = text[max(0, idx-30):idx+len(kw)+30].strip()
            findings.append({
                "keyword": kw, "category": category, "severity": severity,
                "context": context, "source": source,
            })
    return findings


def scan_all(investigation_result: Dict[str, Any]) -> Dict[str, Any]:
    """Scan all text sources from investigation result."""
    all_findings: List[Dict] = []

    # Maigret bios
    for site in investigation_result.get("maigret", {}).get("found_sites", []):
        bio = site.get("bio", "") or ""
        if bio: all_findings.extend(scan_text(bio, source=f"bio:{site.get('site_name','')}"))

    # Custom APIs bios
    for platform, data in investigation_result.get("custom_apis", {}).items():
        if isinstance(data, dict) and data.get("bio"):
            all_findings.extend(scan_text(data["bio"], source=f"bio:{platform}"))

    # Telegram bio
    tg = investigation_result.get("telegram", {})
    if tg.get("bio"): all_findings.extend(scan_text(tg["bio"], source="telegram_bio"))

    # Reddit posts/comments
    reddit = investigation_result.get("reddit_intel", {})
    for post in reddit.get("recent_posts", []):
        if post.get("title"): all_findings.extend(scan_text(post["title"], source="reddit_post"))
    for comment in reddit.get("recent_comments", []):
        if comment.get("body"): all_findings.extend(scan_text(comment["body"], source="reddit_comment"))

    # Deduplicate by keyword+source
    seen = set()
    unique = []
    for f in all_findings:
        key = f"{f['keyword']}:{f['source']}"
        if key not in seen:
            seen.add(key)
            unique.append(f)

    # Sort by severity descending
    unique.sort(key=lambda x: -x["severity"])

    max_severity = max((f["severity"] for f in unique), default=0)
    categories = list(set(f["category"] for f in unique))

    LEVEL_MAP = {0: "CLEAN", 1: "INFO", 2: "SUSPICIOUS", 3: "HIGH RISK", 4: "CRITICAL"}
    COLORS = {0: "\033[32m", 1: "\033[36m", 2: "\033[33m", 3: "\033[31m", 4: "\033[35m"}

    return {
        "total_flags": len(unique),
        "max_severity": max_severity,
        "alert_level": LEVEL_MAP.get(max_severity, "UNKNOWN"),
        "alert_color": COLORS.get(max_severity, ""),
        "categories_flagged": categories,
        "findings": unique[:20],
    }


def format_alerts(data: Dict[str, Any]) -> str:
    BOLD = "\033[1m"; NC = "\033[0m"
    color = data.get("alert_color", "")
    level = data.get("alert_level", "CLEAN")
    total = data.get("total_flags", 0)

    if total == 0:
        return f"\n  {BOLD}Keyword Alert:{NC} {chr(10004)} CLEAN — no suspicious keywords detected"

    lines = [f"\n  {BOLD}Keyword Alert:{NC} {color}{level}{NC} — {total} flag(s)"]
    lines.append(f"  Categories: {', '.join(data.get('categories_flagged',[]))}")
    for f in data.get("findings", [])[:8]:
        sev_label = ["","[INFO]","[WARN]","[HIGH]","[CRIT]"][f["severity"]]
        lines.append(f"  {sev_label} \"{f['keyword']}\" in {f['source']}: ...{f['context']}...")
    return "\n".join(lines)
