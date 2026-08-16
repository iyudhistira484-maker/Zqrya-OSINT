"""Text profiler — extract structured data from bio/text blobs.

Auto-extracts:
  - Email addresses
  - Phone numbers
  - Cryptocurrency addresses (BTC, ETH, SOL)
  - URLs / domains
  - Social media handles
  - Location hints
"""

from __future__ import annotations
from typing import Dict, Any, List
import re


PATTERNS = {
    "emails": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phones": re.compile(r"\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,6}"),
    "btc_addresses": re.compile(r"(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}"),
    "eth_addresses": re.compile(r"0x[a-fA-F0-9]{40}"),
    "sol_addresses": re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}"),
    "urls": re.compile(r"https?://[^\s<>\"{}|\\^`\[\]]+"),
    "instagram_handles": re.compile(r"@([a-zA-Z0-9._]{1,30})\b"),
    "tiktok_handles": re.compile(r"(?:tiktok\.com/|tiktok: ?)@?([a-zA-Z0-9._]{2,24})", re.IGNORECASE),
    "telegram_handles": re.compile(r"(?:t\.me/|telegram: ?)@?([a-zA-Z0-9_]{5,32})", re.IGNORECASE),
    "discord_handles": re.compile(r"(?:discord: ?|@)([a-zA-Z0-9_.]{2,32}#?\d{0,4})"),
    "github_handles": re.compile(r"(?:github\.com/|github: ?)([a-zA-Z0-9-]{1,39})", re.IGNORECASE),
}

LOCATION_HINTS = [
    "london", "nyc", "new york", "san francisco", "los angeles", "chicago",
    "berlin", "paris", "tokyo", "moscow", "amsterdam", "toronto",
    "singapore", "dubai", "mumbai", "bangalore", "sydney",
    "indonesia", "jakarta", "bandung", "surabaya", "bali",
    "united states", "united kingdom", "germany", "france", "japan",
]


def extract(text: str) -> Dict[str, Any]:
    """Extract all identifiable entities from a text block."""
    if not text:
        return {}

    results: Dict[str, Any] = {}

    for entity, pattern in PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            # Deduplicate
            seen = set()
            unique = []
            for m in matches:
                m_clean = str(m).strip().rstrip(".,;:")
                if m_clean and m_clean not in seen and len(m_clean) > 1:
                    seen.add(m_clean)
                    unique.append(m_clean)
            if unique:
                results[entity] = unique[:10]

    # Extract location hints
    text_lower = text.lower()
    locations = [loc for loc in LOCATION_HINTS if loc in text_lower]
    if locations:
        results["location_hints"] = locations

    return results


def extract_from_sites(found_sites: list) -> Dict[str, Any]:
    """Extract entities from all found site bios/names."""
    all_entities: Dict[str, List[str]] = {}
    for site in found_sites:
        text_parts = []
        if site.get("real_name"):
            text_parts.append(site["real_name"])
        if site.get("bio"):
            text_parts.append(site["bio"])
        if site.get("location"):
            text_parts.append(site["location"])
        combined = " ".join(text_parts)
        if combined:
            extracted = extract(combined)
            for key, vals in extracted.items():
                if key not in all_entities:
                    all_entities[key] = []
                for v in vals:
                    if v not in all_entities[key]:
                        all_entities[key].append(v)
    return all_entities
