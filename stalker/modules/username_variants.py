"""Username Variants & Permutation Generator.

Generates username variations for deeper OSINT searches.
Common patterns: leetspeak, separators, prefixes, suffixes,
year appends, reversed, combined with common words.

Termux-compatible: pure Python, no C deps.
"""

from __future__ import annotations
from typing import List, Set
import itertools
import re


LEET_MAP = {
    'a': ['4', '@'],
    'e': ['3'],
    'i': ['1', '!'],
    'o': ['0'],
    's': ['5', '$'],
    't': ['7'],
    'l': ['1'],
    'g': ['9'],
    'b': ['8'],
}

SEPARATORS = ['', '_', '.', '-', '__']

COMMON_SUFFIXES = [
    '1', '2', '123', '12', '21', '11',
    'x', 'xx', 'xd', 'yt', 'tv', 'ig', 'rl',
    'id', 'idn', 'official', 'real', 'original',
    '2020', '2021', '2022', '2023', '2024', '2025',
    '99', '00', '01', '07', '69', '77', '88',
    '_id', '_ig', '_yt', '_official',
]

COMMON_PREFIXES = [
    'the', 'its', 'im', 'i_am', 'real', 'official',
    'mr', 'miss', 'sir', 'boss',
    'x', 'xx',
]

COMMON_WORDS = [
    'gaming', 'gamer', 'pro', 'noob', 'yt', 'tv', 'op',
    'king', 'queen', 'boss', 'dark', 'black', 'white',
    'official', 'real', 'original',
]


def _leet(word: str, depth: int = 1) -> List[str]:
    """Generate leetspeak variations (limited depth to prevent explosion)."""
    results = {word}
    for i, ch in enumerate(word.lower()):
        if ch in LEET_MAP and depth > 0:
            new_results = set()
            for existing in results:
                new_results.add(existing)
                for leet in LEET_MAP[ch]:
                    new_results.add(existing[:i] + leet + existing[i+1:])
            results = new_results
    return list(results - {word})


def _add_separators(parts: List[str]) -> List[str]:
    """Join parts with various separators."""
    if len(parts) < 2:
        return [''.join(parts)]
    results = []
    for sep in SEPARATORS:
        results.append(sep.join(parts))
    return results


def generate_variants(username: str, max_variants: int = 150) -> List[str]:
    """Generate username variations for OSINT searches.
    
    Returns deduplicated list of variants, sorted by likelihood.
    """
    base = username.lower().strip()
    # Remove leading/trailing separators
    base_clean = re.sub(r'^[_.\-]+|[_.\-]+$', '', base)
    
    variants: Set[str] = set()
    
    # Original + case variants
    variants.add(base_clean)
    variants.add(base_clean.upper())
    variants.add(base_clean.capitalize())
    
    # Leet variants (depth 1 only)
    for leet in _leet(base_clean, depth=1)[:20]:
        variants.add(leet)
    
    # Suffix variants
    for suffix in COMMON_SUFFIXES:
        for sep in SEPARATORS[:3]:
            variants.add(f"{base_clean}{sep}{suffix}")
    
    # Prefix variants
    for prefix in COMMON_PREFIXES:
        for sep in SEPARATORS[:3]:
            variants.add(f"{prefix}{sep}{base_clean}")
    
    # If username has parts (underscores/dots/dashes), try rejoining
    parts = re.split(r'[_.\-\s]+', base_clean)
    if len(parts) > 1:
        for sep in SEPARATORS:
            variants.add(sep.join(parts))
        # Reversed parts
        for sep in SEPARATORS[:2]:
            variants.add(sep.join(reversed(parts)))
        # First part alone
        variants.add(parts[0])
        variants.add(parts[-1])
    
    # Reversed
    variants.add(base_clean[::-1])
    
    # Remove the original from variants (we already have it)
    variants.discard(base_clean)
    
    # Sort by length (shorter = more likely to be real)
    result = sorted(variants, key=len)
    
    # Always put original first
    final = [base_clean] + result
    
    # Deduplicate preserving order
    seen = set()
    deduped = []
    for v in final:
        if v not in seen and len(v) >= 3:
            seen.add(v)
            deduped.append(v)
    
    return deduped[:max_variants]


def extract_username_clues(text: str) -> List[str]:
    """Extract potential usernames from bio/profile text."""
    # Match @username patterns
    at_pattern = re.findall(r'@([a-zA-Z0-9_\.]{3,30})', text)
    # Match handle patterns like "IG: username" or "TW: username"
    handle_pattern = re.findall(r'(?:ig|tw|fb|yt|tg|tt|sc|gh)[:：\s]+([a-zA-Z0-9_\.]{3,30})', text, re.IGNORECASE)
    # Match URLs for usernames
    url_pattern = re.findall(r'(?:instagram|twitter|tiktok|youtube|github|t\.me)\.com/([a-zA-Z0-9_\.]{3,30})', text, re.IGNORECASE)
    
    all_clues = list(set(at_pattern + handle_pattern + url_pattern))
    return [c for c in all_clues if not c.lower() in ('com', 'net', 'org', 'www')]


def summary(variants: List[str]) -> Dict:
    return {
        "total_variants": len(variants),
        "sample": variants[:10],
    }
