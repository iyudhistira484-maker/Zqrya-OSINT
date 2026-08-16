"""Recursive username search.

After Maigret finds profiles, extract other usernames/IDs from the results
(e.g. twitter_username, gaia_id, yandex_public_id) and run Maigret again
on those new identifiers. Discovers accounts the target uses on other
platforms with a different username.

Maigret supports multiple id_types: username, yandex_public_id, gaia_id,
vk_id, ok_id, steam_id, etc.
"""

from __future__ import annotations
from typing import Dict, Any, List, Set, Tuple
import asyncio
import logging
import sys
from pathlib import Path

from ..config import Config
from ..reporters import terminal as term

# Supported Maigret id types (from checking.py SUPPORTED_IDS)
SUPPORTED_ID_TYPES = (
    "username",
    "yandex_public_id",
    "gaia_id",
    "vk_id",
    "ok_id",
    "wikimapia_uid",
    "steam_id",
    "uidme_uguid",
    "yelp_userid",
    "orcid",
)


async def recursive_search(
    username: str,
    maigret_data: Dict[str, Any],
    max_depth: int = 2,
    max_sites: int = None,
) -> Dict[str, Any]:
    """Run recursive Maigret search on newly discovered usernames/IDs.

    Args:
        username: Original username
        maigret_data: Results from first Maigret search
        max_depth: How many levels deep to recurse (1 = no recursion, 2 = one level)
        max_sites: Max sites per recursive search

    Returns:
        {
            "original_username": str,
            "discovered_usernames": [{username, id_type, source_site, depth}],
            "recursive_results": {username: maigret_result_dict},
            "all_found_sites": [merged list of all sites found across all levels],
        }
    """
    # Collect all discovered usernames from first search
    discovered: List[Dict[str, str]] = []
    seen_usernames: Set[str] = {username.lower()}

    for site in maigret_data.get("found_sites", []):
        # From ids_data
        ids = site.get("ids_data", {})
        for key, val in ids.items():
            if "username" in key.lower() and val:
                uname = str(val).strip()
                if uname.lower() not in seen_usernames and len(uname) > 1:
                    discovered.append({
                        "username": uname,
                        "id_type": "username",
                        "source_site": site.get("site_name", "?"),
                        "source_field": key,
                        "depth": 1,
                    })
                    seen_usernames.add(uname.lower())

        # From other_usernames dict (Maigret's parse_usernames output)
        for uname, id_type in site.get("other_usernames", {}).items():
            if uname.lower() not in seen_usernames and len(uname) > 1:
                discovered.append({
                    "username": uname,
                    "id_type": id_type if id_type in SUPPORTED_ID_TYPES else "username",
                    "source_site": site.get("site_name", "?"),
                    "source_field": "other_usernames",
                    "depth": 1,
                })
                seen_usernames.add(uname.lower())

        # From custom API data
        custom = site.get("custom_api_data", {})
        if custom.get("success"):
            # Twitter username from GitHub
            twitter_uname = custom.get("twitter_username") or custom.get("raw", {}).get("twitter_username")
            if twitter_uname and twitter_uname.lower() not in seen_usernames:
                discovered.append({
                    "username": twitter_uname,
                    "id_type": "username",
                    "source_site": site.get("site_name", "?"),
                    "source_field": "twitter_username",
                    "depth": 1,
                })
                seen_usernames.add(twitter_uname.lower())

    # Also check custom_profiles for usernames
    for platform, pdata in maigret_data.get("custom_profiles", {}).items():
        if not pdata.get("success"):
            continue
        uname = pdata.get("username")
        if uname and uname.lower() not in seen_usernames and uname.lower() != username.lower():
            discovered.append({
                "username": uname,
                "id_type": "username",
                "source_site": platform,
                "source_field": "custom_api",
                "depth": 1,
            })
            seen_usernames.add(uname.lower())

    if not discovered:
        term.print_warning("  Recursive: no new usernames discovered")
        return {
            "original_username": username,
            "discovered_usernames": [],
            "recursive_results": {},
            "all_found_sites": maigret_data.get("found_sites", []),
        }

    term.print_success(f"Recursive: discovered {len(discovered)} new username(s):")
    for d in discovered[:10]:
        term.print_warning(f"  {d['username']} (from {d['source_site']} via {d['source_field']})")

    # Run Maigret on each discovered username (parallel, but limited concurrency)
    recursive_results: Dict[str, Any] = {}

    # Import _run_maigret from pipeline (lazy import to avoid circular)
    from ..pipeline import _run_maigret

    # Run searches with limited concurrency (avoid overwhelming)
    semaphore = asyncio.Semaphore(3)

    async def _search_one(discovery: Dict) -> Tuple[str, Dict]:
        async with semaphore:
            uname = discovery["username"]
            term.print_warning(f"  Recursive: searching '{uname}'...")
            try:
                result = await _run_maigret(uname, max_sites=max_sites)
                return uname, result
            except Exception as e:
                term.print_warning(f"  Recursive: '{uname}' failed: {e}")
                return uname, {"found_sites": [], "total_checked": 0, "real_names": [], "avatar_urls": []}

    tasks = [_search_one(d) for d in discovered[:5]]  # max 5 recursive searches
    results = await asyncio.gather(*tasks)

    for uname, res in results:
        recursive_results[uname] = res

    # Merge all found sites
    all_sites = list(maigret_data.get("found_sites", []))
    all_names = set(maigret_data.get("real_names", []))
    all_avatars = list(maigret_data.get("avatar_urls", []))

    for uname, res in recursive_results.items():
        for site in res.get("found_sites", []):
            # Mark as recursive discovery
            site["discovered_via"] = uname
            all_sites.append(site)
        for name in res.get("real_names", []):
            all_names.add(name)
        for avatar in res.get("avatar_urls", []):
            if avatar not in all_avatars:
                all_avatars.append(avatar)

    term.print_success(
        f"Recursive complete: {len(all_sites)} total profiles, "
        f"{len(all_names)} names, {len(all_avatars)} avatars"
    )

    return {
        "original_username": username,
        "discovered_usernames": discovered,
        "recursive_results": recursive_results,
        "all_found_sites": all_sites,
        "all_real_names": list(all_names),
        "all_avatar_urls": all_avatars,
    }
