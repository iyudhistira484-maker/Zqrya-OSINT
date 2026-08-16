"""Google Dork search engine for people investigation.

Smart Dork: uses ALL extracted data (names, usernames, emails, blog URLs, company, bio keywords)
not just real names. Falls back to DuckDuckGo if Google rate-limits.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import asyncio
from ..config import Config
from .proxy_manager import prepare_client

try:
    from googlesearch import search as google_search
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

HAS_DDG = True  # built-in via httpx


DORK_TEMPLATES = {
    "linkedin": '"{name}" site:linkedin.com/in/',
    "facebook": '"{name}" site:facebook.com',
    "twitter": '"{name}" site:twitter.com OR site:x.com',
    "instagram": '"{name}" site:instagram.com',
    "github": '"{name}" site:github.com',
    "documents": '"{name}" filetype:pdf OR filetype:doc',
    "news": '"{name}" site:news.google.com',
    "general": '"{name}" -site:pinterest.com -site:youtube.com',
}


def build_dork_query(name: str, category: str = "general") -> str:
    """Build a Google dork query string for a person name."""
    template = DORK_TEMPLATES.get(category, DORK_TEMPLATES["general"])
    return template.format(name=name)



async def search_person(name: str, categories: List[str] = None) -> Dict[str, List[Dict[str, str]]]:
    """Search for a person across multiple dork categories."""
    if categories is None:
        categories = ["linkedin", "facebook", "twitter", "github", "general"]

    results = {}
    for cat in categories:
        dork = build_dork_query(name, cat)
        results[cat] = await _execute_search(dork)

    return results


async def _execute_search(query: str) -> List[Dict[str, str]]:
    """Execute a search query using available backends.

    Strategy: try Google first, fall back to DuckDuckGo if Google fails/returns empty.
    """
    results = []

    # Try Google first
    if HAS_GOOGLE:
        results = await _search_google(query)

    # Fall back to DDG if Google returned nothing or Google not available
    if not results and HAS_DDG:
        results = await _search_ddg(query)

    if not results and not HAS_GOOGLE:
        results = [{"title": "No search engine available. Install: pip install googlesearch-python", "url": "", "snippet": ""}]

    return results[:Config.DORK_MAX_RESULTS]


async def _search_google(query: str) -> List[Dict[str, str]]:
    """Search via Google."""
    loop = asyncio.get_event_loop()
    try:
        raw_results = await loop.run_in_executor(
            None,
            lambda: list(google_search(query, num_results=Config.DORK_MAX_RESULTS, advanced=True)),
        )
        return [
            {"title": getattr(r, "title", ""), "url": getattr(r, "url", ""), "snippet": getattr(r, "description", "")}
            for r in raw_results
        ]
    except Exception:
        return []


async def _search_ddg(query: str) -> List[Dict[str, str]]:
    """Search via DuckDuckGo HTML endpoint using httpx."""
    import re

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    try:
        async with prepare_client(timeout=15, follow_redirects=True, headers=headers) as client:
            resp = await client.post("https://html.duckduckgo.com/html/", data={"q": query})
            resp.raise_for_status()

        titles = re.findall(
            r'class="result__title"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            resp.text, re.DOTALL,
        )
        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</a>',
            resp.text, re.DOTALL,
        )

        results = []
        for i, (url, title) in enumerate(titles):
            if "duckduckgo.com/y.js" in url or "duckduckgo.com/l/" in url:
                continue
            title = re.sub(r"<[^>]+>", "", title).strip()
            snip = re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else ""
            results.append({"title": title, "url": url, "snippet": snip})

        return results[:Config.DORK_MAX_RESULTS]
    except Exception:
        return []


# ============================================================
#  SMART DORK — uses ALL extracted data
# ============================================================


async def smart_dork(extracted_data: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """Search using ALL extracted data, not just real name.

    Builds dork queries from:
      - Real names (fullname, name, nickname)
      - Other usernames found
      - Email addresses
      - Blog/website URLs
      - Company name
      - Bio keywords
      - Location

    Falls back to DuckDuckGo if Google blocks.

    Returns:
        {query_label: [search_results]}
    """
    queries = _build_smart_queries(extracted_data)

    if not queries:
        return {}

    # Run all queries in parallel
    tasks = [_execute_search(q) for q in queries.values()]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    results = {}
    for label, res in zip(queries.keys(), results_raw):
        if isinstance(res, Exception):
            results[label] = []
        else:
            results[label] = res

    return results


def _build_smart_queries(data: Dict[str, Any]) -> Dict[str, str]:
    """Build multiple dork queries from extracted data."""
    queries = {}

    # Collect all identifiers
    names = set()
    usernames = set()
    emails = set()
    websites = set()
    companies = set()
    locations = set()
    keywords = set()

    # From real_names list
    for name in data.get("real_names", []):
        if name and len(str(name).strip()) > 1:
            names.add(str(name).strip())

    # From found_sites
    for site in data.get("found_sites", []):
        name = site.get("real_name")
        if name and len(str(name).strip()) > 1:
            names.add(str(name).strip())

        # Other usernames
        for uname in site.get("other_usernames", {}):
            if uname and uname.lower() != data.get("username", "").lower():
                usernames.add(uname)

        # Bio keywords
        bio = site.get("bio")
        if bio:
            for word in str(bio).split():
                w = word.strip("@.,#!?")
                if len(w) > 4 and w.lower() not in ("https", "http", "www"):
                    keywords.add(w)

        # Company
        company = site.get("ids_data", {}).get("company") or site.get("ids_data", {}).get("is_company")
        if company and len(str(company)) > 2:
            companies.add(str(company))

        # Location
        loc = site.get("location") or site.get("ids_data", {}).get("location")
        if loc and len(str(loc)) > 2:
            locations.add(str(loc))

        # Blog/website
        blog = site.get("ids_data", {}).get("blog_url") or site.get("ids_data", {}).get("website")
        if blog:
            websites.add(str(blog))

        # Emails
        for key, val in site.get("ids_data", {}).items():
            if "email" in key.lower() and val:
                emails.add(str(val))

    # From custom API data
    for platform, pdata in data.get("custom_profiles", {}).items():
        if not pdata.get("success"):
            continue
        name = pdata.get("real_name")
        if name and len(str(name).strip()) > 1:
            names.add(str(name).strip())
        company = pdata.get("company")
        if company:
            companies.add(str(company))
        loc = pdata.get("location")
        if loc:
            locations.add(str(loc))
        blog = pdata.get("blog")
        if blog:
            websites.add(str(blog))

    # Build queries
    # 1. Real name searches
    for name in list(names)[:3]:
        queries[f"name:{name}"] = f'"{name}"'

    # 2. Name + location
    for name in list(names)[:2]:
        for loc in list(locations)[:1]:
            queries[f"name+loc:{name}+{loc}"] = f'"{name}" "{loc}"'

    # 3. Name + company
    for name in list(names)[:2]:
        for company in list(companies)[:1]:
            queries[f"name+company:{name}+{company}"] = f'"{name}" "{company}"'

    # 4. Other usernames (search each on Google)
    for uname in list(usernames)[:3]:
        if uname.lower() != data.get("username", "").lower():
            queries[f"username:{uname}"] = f'"{uname}" -site:{data.get("username", "")}.com'

    # 5. Email searches
    for email in list(emails)[:3]:
        queries[f"email:{email}"] = f'"{email}"'

    # 6. Website/blog searches
    for site_url in list(websites)[:2]:
        domain = site_url.replace("https://", "").replace("http://", "").split("/")[0]
        queries[f"site:{domain}"] = f'site:{domain} OR "{domain}"'

    # 7. Name + keywords from bio
    for name in list(names)[:1]:
        for kw in list(keywords)[:3]:
            queries[f"name+kw:{name}+{kw}"] = f'"{name}" "{kw}"'

    # 8. Username on specific platforms
    username = data.get("username", "")
    if username:
        queries[f"{username}:linkedin"] = f'"{username}" site:linkedin.com/in/'
        queries[f"{username}:facebook"] = f'"{username}" site:facebook.com'
        queries[f"{username}:docs"] = f'"{username}" filetype:pdf OR filetype:doc'

    return queries
