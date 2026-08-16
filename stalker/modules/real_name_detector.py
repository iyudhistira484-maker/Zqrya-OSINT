"""Real Name Detection Module for Stalker.

Detects if input is real name (e.g., "Zell Ishikawa") vs username.
Generates variants dan cari di semua platform.
Extracts real names dari profile data.
"""

from __future__ import annotations
from typing import Dict, Any, List, Set
import re
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def is_real_name(text: str) -> bool:
    """Detect if input is likely a real name (space + capital letters)."""
    text = text.strip()
    
    # Real names typically have:
    # 1. At least one space
    # 2. At least 2 words
    # 3. Most words start with capital letter
    # 4. No special chars except apostrophe/hyphen
    
    if " " not in text:
        return False
    
    # Check for invalid chars
    if re.search(r'[!@#$%^&*+=\[\]{};:"\',<>?/\\|`~]', text):
        return False
    
    words = text.split()
    if len(words) < 2:
        return False
    
    # Check if most words start with capital
    capital_words = sum(1 for w in words if w and w[0].isupper())
    if capital_words < len(words) - 1:  # Allow 1 lowercase word
        return False
    
    return True


def extract_name_parts(full_name: str) -> Dict[str, List[str]]:
    """Extract first, last, middle names dan generate variants."""
    parts = full_name.strip().split()
    
    result = {
        "full": [full_name],
        "first": [],
        "last": [],
        "middle": [],
        "variants": set(),
    }
    
    if len(parts) >= 1:
        result["first"] = [parts[0]]
    if len(parts) >= 2:
        result["last"] = [parts[-1]]
    if len(parts) >= 3:
        result["middle"] = parts[1:-1]
    
    # Generate variants
    variants = set()
    variants.add(full_name)  # Full name
    variants.add(full_name.lower())  # Lowercase
    variants.add(full_name.replace(" ", ""))  # No space
    variants.add(full_name.replace(" ", "_"))  # Underscore
    variants.add(full_name.replace(" ", "."))  # Dot
    variants.add(full_name.replace(" ", "-"))  # Dash
    
    if len(parts) >= 2:
        variants.add(f"{parts[0]}{parts[-1]}".lower())  # firstlast
        variants.add(f"{parts[0]}_{parts[-1]}".lower())  # first_last
        variants.add(f"{parts[0]}.{parts[-1]}".lower())  # first.last
        variants.add(f"{parts[-1]}{parts[0]}".lower())  # lastfirst
        variants.add(f"{parts[0][0]}{parts[-1]}".lower())  # flast
    
    # Add individual parts
    for part in parts:
        variants.add(part.lower())
    
    result["variants"] = sorted(list(variants))
    
    return result


def extract_real_names_from_profiles(found_sites: List[Dict[str, Any]]) -> Set[str]:
    """Extract real names dari profile data (ids_data)."""
    real_names = set()
    
    for site in found_sites:
        if not isinstance(site, dict):
            continue
        
        # Check ids_data for real name info
        ids_data = site.get("ids_data", {})
        if isinstance(ids_data, dict):
            # Common name fields
            for key in ["fullname", "full_name", "name", "display_name", "author"]:
                value = ids_data.get(key)
                if value and isinstance(value, str) and len(value) > 2:
                    real_names.add(value.strip())
    
    return real_names


async def generate_name_search_queries(full_name: str) -> Dict[str, List[str]]:
    """Generate Google Dork queries for a real name."""
    parts = extract_name_parts(full_name)
    
    queries = {
        "fullname": [],
        "variations": [],
        "email_search": [],
        "phone_search": [],
    }
    
    # Full name queries
    queries["fullname"] = [
        f'"{full_name}"',
        f'{full_name} site:linkedin.com',
        f'{full_name} site:facebook.com',
        f'{full_name} site:instagram.com',
        f'{full_name} site:twitter.com',
    ]
    
    # Variation queries
    first = parts["first"][0] if parts["first"] else ""
    last = parts["last"][0] if parts["last"] else ""
    
    if first and last:
        queries["variations"] = [
            f'{first} {last}',
            f'{first}_{last}',
            f'{last}_{first}',
            f'{first}.{last}',
        ]
    
    # Email variants (common patterns)
    if first and last:
        queries["email_search"] = [
            f'{first}@*',
            f'{first}.{last}@*',
            f'{first}_{last}@*',
        ]
    
    return queries


async def correlate_multiple_identities(found_sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Correlate multiple accounts to determine true identity."""
    correlations = {
        "likely_names": [],
        "account_connections": {},
        "confidence": 0.0,
        "bio_extracted_names": set(),
        "email_domains": set(),
    }
    
    # Extract names
    real_names = extract_real_names_from_profiles(found_sites)
    correlations["likely_names"] = sorted(list(real_names))
    
    # Extract emails dan domains
    emails = set()
    for site in found_sites:
        if not isinstance(site, dict):
            continue
        
        ids_data = site.get("ids_data", {})
        if isinstance(ids_data, dict):
            email = ids_data.get("email")
            if email and isinstance(email, str):
                emails.add(email)
                domain = email.split("@")[-1]
                correlations["email_domains"].add(domain)
    
    # Calculate confidence
    if len(real_names) > 0:
        correlations["confidence"] = min(len(real_names) * 0.2, 1.0)
    
    correlations["bio_extracted_names"] = list(real_names)
    
    return correlations


async def process_real_name_input(
    input_text: str,
    enable_variant_search: bool = True,
) -> Dict[str, Any]:
    """Main function: detect real name dan return variants + search config."""
    
    result = {
        "is_real_name": False,
        "original_input": input_text,
        "name_parts": {},
        "search_variants": [],
        "should_search_variants": False,
        "error": None,
    }
    
    try:
        if not is_real_name(input_text):
            result["is_real_name"] = False
            return result
        
        result["is_real_name"] = True
        result["name_parts"] = extract_name_parts(input_text)
        result["search_variants"] = result["name_parts"]["variants"]
        
        if enable_variant_search and len(result["search_variants"]) > 0:
            result["should_search_variants"] = True
    
    except Exception as e:
        result["error"] = str(e)
    
    return result
