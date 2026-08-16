"""Correlation Engine — auto-link username ↔ email ↔ phone across all findings.

Extracts cross-platform identity links from:
- Maigret profiles (bio, email, phone fields)
- Custom API results
- Text profiler output
- GitHub commit emails
- Gravatar linked accounts
- Reddit posts
- Telegram profile

Builds a unified identity graph showing connections.
"""
from __future__ import annotations
from typing import Dict, Any, List, Set
import re

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'\+?[0-9]{10,15}')
HANDLE_RE = re.compile(r'@([a-zA-Z0-9_\.]{3,30})')
URL_RE = re.compile(r'https?://(?:www\.)?([a-zA-Z0-9.-]+)/([a-zA-Z0-9_\-\.]+)')


def extract_from_text(text: str) -> Dict[str, List[str]]:
    emails = list(set(EMAIL_RE.findall(text or "")))
    phones = list(set(PHONE_RE.findall(text or "")))
    handles = list(set(HANDLE_RE.findall(text or "")))
    return {"emails": emails, "phones": phones, "handles": handles}


def correlate(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all identity links from full investigation result.
    
    Returns unified identity with all correlated identifiers.
    """
    target = result.get("username", result.get("email", result.get("phone", "unknown")))
    
    emails: Set[str] = set()
    phones: Set[str] = set()
    usernames: Set[str] = set()
    real_names: Set[str] = set()
    links: List[Dict[str, str]] = []  # {from, to, via}

    # ── From Maigret found sites ──────────────────────────────
    maigret = result.get("maigret", {})
    for site in maigret.get("found_sites", []):
        bio = site.get("bio", "") or ""
        extracted = extract_from_text(bio)
        for e in extracted["emails"]: emails.add(e); links.append({"from": target, "to": e, "via": site.get("site_name","profile"), "type": "email"})
        for p in extracted["phones"]: phones.add(p); links.append({"from": target, "to": p, "via": site.get("site_name","profile"), "type": "phone"})
        for h in extracted["handles"]:
            if h.lower() != target.lower(): usernames.add(h); links.append({"from": target, "to": h, "via": site.get("site_name","profile"), "type": "username"})
        if site.get("real_name"): real_names.add(site["real_name"])
        if site.get("email"): emails.add(site["email"])

    # ── From GitHub intel ─────────────────────────────────────
    github = result.get("github_intel", {})
    for e in github.get("extracted_emails", []):
        email_val = e.get("email","") if isinstance(e, dict) else e
        if email_val: emails.add(email_val); links.append({"from": target, "to": email_val, "via": "github_commit", "type": "email"})
    gh_profile = github.get("profile", {})
    if gh_profile.get("email"): emails.add(gh_profile["email"])
    if gh_profile.get("name"): real_names.add(gh_profile["name"])
    if gh_profile.get("twitter"): usernames.add(gh_profile["twitter"]); links.append({"from": target, "to": gh_profile["twitter"], "via": "github_profile", "type": "username_twitter"})

    # ── From Gravatar ─────────────────────────────────────────
    gravatar = result.get("gravatar", {})
    for e in gravatar.get("emails", []):
        emails.add(e); links.append({"from": target, "to": e, "via": "gravatar", "type": "email"})
    for acc in gravatar.get("accounts", []):
        domain = acc.get("domain",""); shortname = acc.get("shortname","")
        if shortname: usernames.add(shortname); links.append({"from": target, "to": shortname, "via": f"gravatar_{domain}", "type": "username"})

    # ── From Text Profiler ────────────────────────────────────
    text_profile = result.get("text_profile", {})
    for e in text_profile.get("emails", []): emails.add(e); links.append({"from": target, "to": e, "via": "bio_text", "type": "email"})
    for p in text_profile.get("phones", []): phones.add(p); links.append({"from": target, "to": p, "via": "bio_text", "type": "phone"})

    # ── From Telegram ─────────────────────────────────────────
    telegram = result.get("telegram", {})
    if telegram.get("bio"):
        ext = extract_from_text(telegram["bio"])
        for e in ext["emails"]: emails.add(e)
        for p in ext["phones"]: phones.add(p)
    if telegram.get("display_name"): real_names.add(telegram["display_name"])

    # ── From Custom APIs ──────────────────────────────────────
    custom_apis = result.get("custom_apis", {})
    for platform, data in custom_apis.items():
        if not isinstance(data, dict) or not data.get("success"): continue
        if data.get("real_name"): real_names.add(data["real_name"])
        bio = data.get("bio","") or ""
        ext = extract_from_text(bio)
        for e in ext["emails"]: emails.add(e)
        for p in ext["phones"]: phones.add(p)

    # ── From Recursive search ─────────────────────────────────
    recursive = result.get("recursive", {})
    for u in recursive.get("discovered_usernames", []):
        if u and u.lower() != target.lower():
            usernames.add(u); links.append({"from": target, "to": u, "via": "recursive_search", "type": "username"})

    # ── Clean & deduplicate ───────────────────────────────────
    clean_emails = [e for e in emails if "noreply" not in e and len(e) > 5]
    clean_phones = [p for p in phones if len(p) >= 10]
    clean_users = [u for u in usernames if len(u) >= 3 and u.lower() != target.lower()]

    return {
        "target": target,
        "correlated_emails": sorted(set(clean_emails)),
        "correlated_phones": sorted(set(clean_phones)),
        "correlated_usernames": sorted(set(clean_users)),
        "real_names": sorted(real_names),
        "identity_links": links[:50],
        "total_links": len(links),
    }


def format_correlation(data: Dict[str, Any]) -> str:
    """Format correlation report for terminal."""
    BOLD = "\033[1m"; CYAN = "\033[36m"; YELLOW = "\033[33m"; NC = "\033[0m"
    lines = [f"\n{BOLD}  ┌─── IDENTITY CORRELATION ───┐{NC}"]
    lines.append(f"  Target: {BOLD}{data['target']}{NC}  ({data['total_links']} cross-links found)")
    if data["real_names"]:
        lines.append(f"\n  {BOLD}Real Names:{NC}")
        for n in data["real_names"][:5]: lines.append(f"  → {n}")
    if data["correlated_emails"]:
        lines.append(f"\n  {BOLD}Linked Emails:{NC}")
        for e in data["correlated_emails"][:8]: lines.append(f"  → {CYAN}{e}{NC}")
    if data["correlated_phones"]:
        lines.append(f"\n  {BOLD}Linked Phones:{NC}")
        for p in data["correlated_phones"][:5]: lines.append(f"  → {YELLOW}{p}{NC}")
    if data["correlated_usernames"]:
        lines.append(f"\n  {BOLD}Alt. Usernames:{NC}")
        for u in data["correlated_usernames"][:10]: lines.append(f"  → {u}")
    return "\n".join(lines)
