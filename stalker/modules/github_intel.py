"""GitHub Intelligence — extract real emails from commits, profile deep dive."""
from __future__ import annotations
from typing import Dict, Any, List, Set, Optional
import asyncio
from .proxy_manager import prepare_client

GH_API = "https://api.github.com"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"}

async def _get(c, url):
    try:
        r = await c.get(url)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

async def get_profile(username: str) -> Dict[str, Any]:
    async with prepare_client(timeout=15, headers=H) as c:
        d = await _get(c, f"{GH_API}/users/{username}")
        if not d or "login" not in d:
            return {"found": False}
        return {
            "found": True, "username": d.get("login"), "name": d.get("name",""),
            "bio": d.get("bio",""), "email": d.get("email",""),
            "location": d.get("location",""), "company": d.get("company",""),
            "blog": d.get("blog",""), "twitter": d.get("twitter_username",""),
            "avatar_url": d.get("avatar_url",""),
            "public_repos": d.get("public_repos",0), "followers": d.get("followers",0),
            "created_at": d.get("created_at",""),
            "profile_url": f"https://github.com/{username}",
        }

async def extract_emails_from_commits(username: str, max_repos: int = 10) -> List[Dict]:
    """Extract real emails from commit history — most valuable GitHub intel."""
    found: List[Dict] = []
    seen: Set[str] = set()
    async with prepare_client(timeout=20, headers=H) as c:
        repos = await _get(c, f"{GH_API}/users/{username}/repos?per_page={max_repos}&sort=updated&type=owner")
        if not repos or not isinstance(repos, list):
            return found
        async def _repo(name):
            commits = await _get(c, f"{GH_API}/repos/{username}/{name}/commits?per_page=5&author={username}")
            if not commits or not isinstance(commits, list):
                return
            for cm in commits:
                a = cm.get("commit",{}).get("author",{})
                email = a.get("email","")
                if email and "noreply" not in email and email not in seen:
                    seen.add(email)
                    found.append({"email": email, "name": a.get("name",""), "repo": name,
                                  "sha": cm.get("sha","")[:8], "date": a.get("date",""), "source": "github_commit"})
        await asyncio.gather(*[_repo(r.get("name","")) for r in repos[:max_repos] if r.get("name")], return_exceptions=True)
    return found

async def get_organizations(username: str) -> List[Dict]:
    async with prepare_client(timeout=10, headers=H) as c:
        orgs = await _get(c, f"{GH_API}/users/{username}/orgs")
        if not orgs or not isinstance(orgs, list): return []
        return [{"name": o.get("login",""), "url": f"https://github.com/{o.get('login','')}"} for o in orgs]

async def get_language_fingerprint(username: str) -> Dict[str, int]:
    """Primary coding languages — useful for identity correlation."""
    counts: Dict[str, int] = {}
    async with prepare_client(timeout=15, headers=H) as c:
        repos = await _get(c, f"{GH_API}/users/{username}/repos?per_page=20&sort=updated")
        if not repos or not isinstance(repos, list): return {}
        for r in repos:
            lang = r.get("language")
            if lang: counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))

async def search_by_email(email: str) -> List[Dict]:
    """Reverse: email → GitHub username via commit search."""
    results = []
    try:
        async with prepare_client(timeout=15, headers=H) as c:
            data = await _get(c, f"{GH_API}/search/commits?q=author-email:{email}&per_page=5")
            if data and isinstance(data, dict):
                for item in data.get("items", [])[:5]:
                    a = item.get("commit",{}).get("author",{})
                    results.append({"author_name": a.get("name",""),
                                    "author_login": item.get("author",{}).get("login",""),
                                    "repo": item.get("repository",{}).get("full_name",""),
                                    "date": a.get("date","")})
    except Exception: pass
    return results

async def full_github_intel(username: str) -> Dict[str, Any]:
    profile, emails, orgs, langs = await asyncio.gather(
        get_profile(username), extract_emails_from_commits(username),
        get_organizations(username), get_language_fingerprint(username),
        return_exceptions=True)
    return {
        "profile": profile if isinstance(profile, dict) else {},
        "extracted_emails": emails if isinstance(emails, list) else [],
        "organizations": orgs if isinstance(orgs, list) else [],
        "languages": langs if isinstance(langs, dict) else {},
        "found": isinstance(profile, dict) and profile.get("found", False),
    }

def summary(data: Dict[str, Any]) -> Dict[str, Any]:
    p = data.get("profile", {})
    return {
        "found": data.get("found", False), "public_email": p.get("email",""),
        "extracted_emails": [e["email"] for e in data.get("extracted_emails",[])],
        "real_name": p.get("name",""), "location": p.get("location",""),
        "organizations": [o["name"] for o in data.get("organizations",[])],
        "top_languages": list(data.get("languages",{}).keys())[:5],
        "repos": p.get("public_repos",0), "followers": p.get("followers",0),
    }
