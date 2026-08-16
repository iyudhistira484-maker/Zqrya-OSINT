"""Reddit User Analyzer — public post/comment history OSINT.

Features (no API key needed):
- Account age, karma, verified status
- Top subreddits (reveals interests/location/profession)
- Post & comment history analysis
- Timezone estimation from posting patterns
- Keyword extraction from content
- Cross-platform correlation clues
"""
from __future__ import annotations
from typing import Dict, Any, List
import asyncio, re
from collections import Counter
from .proxy_manager import prepare_client

REDDIT_API = "https://www.reddit.com"
H = {"User-Agent": "Zqrya/3.0 OSINT-Tool"}

async def get_user_info(username: str) -> Dict[str, Any]:
    async with prepare_client(timeout=15, headers=H) as c:
        try:
            r = await c.get(f"{REDDIT_API}/user/{username}/about.json")
            if r.status_code == 200:
                d = r.json().get("data", {})
                if not d: return {"found": False}
                import datetime
                created = datetime.datetime.utcfromtimestamp(d.get("created_utc", 0))
                return {
                    "found": True, "username": d.get("name",""),
                    "karma_post": d.get("link_karma", 0),
                    "karma_comment": d.get("comment_karma", 0),
                    "total_karma": d.get("total_karma", 0),
                    "created_at": created.strftime("%Y-%m-%d"),
                    "account_age_days": (datetime.datetime.utcnow() - created).days,
                    "is_gold": d.get("is_gold", False),
                    "is_mod": d.get("is_mod", False),
                    "verified": d.get("verified", False),
                    "has_verified_email": d.get("has_verified_email", False),
                    "icon_img": d.get("icon_img",""),
                    "profile_url": f"https://reddit.com/u/{username}",
                }
            elif r.status_code == 404:
                return {"found": False, "error": "user not found"}
        except Exception as e:
            return {"found": False, "error": str(e)}
    return {"found": False}

async def get_post_history(username: str, limit: int = 25) -> List[Dict]:
    async with prepare_client(timeout=15, headers=H) as c:
        try:
            r = await c.get(f"{REDDIT_API}/user/{username}/submitted.json?limit={limit}&sort=new")
            if r.status_code == 200:
                posts = r.json().get("data", {}).get("children", [])
                return [{"title": p["data"].get("title","")[:100], "subreddit": p["data"].get("subreddit",""),
                         "score": p["data"].get("score",0), "url": p["data"].get("url",""),
                         "created_utc": p["data"].get("created_utc",0)} for p in posts]
        except Exception: pass
    return []

async def get_comment_history(username: str, limit: int = 25) -> List[Dict]:
    async with prepare_client(timeout=15, headers=H) as c:
        try:
            r = await c.get(f"{REDDIT_API}/user/{username}/comments.json?limit={limit}&sort=new")
            if r.status_code == 200:
                comments = r.json().get("data", {}).get("children", [])
                return [{"body": c_["data"].get("body","")[:200], "subreddit": c_["data"].get("subreddit",""),
                         "score": c_["data"].get("score",0), "created_utc": c_["data"].get("created_utc",0)}
                        for c_ in comments]
        except Exception: pass
    return []

def analyze_activity(posts: List[Dict], comments: List[Dict]) -> Dict[str, Any]:
    """Extract intelligence from activity patterns."""
    all_subs = [p["subreddit"] for p in posts] + [c["subreddit"] for c in comments]
    top_subs = Counter(all_subs).most_common(10)
    all_text = " ".join([p.get("title","") for p in posts] + [c.get("body","") for c in comments])
    # Timezone estimation from UTC hours
    import datetime
    hours = []
    for item in posts + comments:
        ts = item.get("created_utc", 0)
        if ts:
            hours.append(datetime.datetime.utcfromtimestamp(ts).hour)
    peak_hour = Counter(hours).most_common(1)[0][0] if hours else None
    # Extract emails, phones from content
    emails_found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', all_text)
    phones_found = re.findall(r'\+?[0-9]{10,13}', all_text)
    # Location clues from subreddits
    location_subs = [s for s in all_subs if any(k in s.lower() for k in
        ["indonesia","jakarta","bandung","surabaya","malaysia","singapore","india","uk","australia","canada","germany"])]
    return {
        "top_subreddits": top_subs,
        "total_posts": len(posts),
        "total_comments": len(comments),
        "peak_activity_hour_utc": peak_hour,
        "estimated_timezone": _estimate_tz(peak_hour),
        "location_clues": list(set(location_subs))[:5],
        "emails_in_content": list(set(emails_found))[:5],
        "phones_in_content": list(set(phones_found))[:3],
    }

def _estimate_tz(peak_hour):
    if peak_hour is None: return "unknown"
    # If peak activity is 14-22 UTC → likely SEA/Asia (WIB = UTC+7)
    if 7 <= peak_hour <= 15: return "Asia/Pacific (UTC+7 to +12)"
    if 16 <= peak_hour <= 22: return "Europe/Africa (UTC+0 to +3)"
    if 0 <= peak_hour <= 7: return "Americas (UTC-5 to -8)"
    return "unknown"

async def full_reddit_intel(username: str) -> Dict[str, Any]:
    info, posts, comments = await asyncio.gather(
        get_user_info(username), get_post_history(username), get_comment_history(username),
        return_exceptions=True)
    if not isinstance(info, dict) or not info.get("found"):
        return {"found": False}
    activity = analyze_activity(
        posts if isinstance(posts, list) else [],
        comments if isinstance(comments, list) else [])
    return {"found": True, "profile": info, "activity": activity,
            "recent_posts": (posts or [])[:5], "recent_comments": (comments or [])[:5]}

def summary(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get("found"): return {"found": False}
    p = data.get("profile", {})
    a = data.get("activity", {})
    return {
        "found": True, "karma": p.get("total_karma",0), "account_age_days": p.get("account_age_days",0),
        "top_subreddits": [s[0] for s in a.get("top_subreddits",[])[:5]],
        "estimated_timezone": a.get("estimated_timezone",""),
        "location_clues": a.get("location_clues",[]),
        "emails_found": a.get("emails_in_content",[]),
    }
