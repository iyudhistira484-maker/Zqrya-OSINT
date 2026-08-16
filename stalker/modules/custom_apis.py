"""Custom API integration via xemoz-official.my.id.

Provides enriched profile data for Instagram, TikTok, Twitter, YouTube, GitHub.
All requests run in parallel. Returns avatar URLs, real names, bios, follower counts, etc.

These APIs bypass Cloudflare blocks that Maigret/socid_extractor can't handle.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio
import httpx

BASE_URL = "https://api-xemoz-official.my.id/api/stalker"

PLATFORM_CONFIG = {
    "instagram": {"endpoint": "stalker-instagram.php", "param": "username"},
    "tiktok":    {"endpoint": "stalker-tiktok.php",    "param": "username"},
    "twitter":   {"endpoint": "stalker-twitter.php",   "param": "user"},
    "youtube":   {"endpoint": "stalker-youtube.php",   "param": "username"},
    "github":    {"endpoint": "stalker-github.php",    "param": "username"},
}


async def search_all_platforms(username: str, timeout: int = 15) -> Dict[str, Any]:
    """Search all 5 platforms in parallel via xemoz API.

    Returns:
        {
            "instagram": {success, avatar_url, real_name, bio, followers, ...} or {error},
            "tiktok": {...},
            "twitter": {...},
            "youtube": {...},
            "github": {...},
        }
    """
    tasks = []
    platform_names = []

    for platform in PLATFORM_CONFIG:
        tasks.append(_search_platform(platform, username, timeout))
        platform_names.append(platform)

    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    results = {}
    for name, res in zip(platform_names, results_raw):
        if isinstance(res, Exception):
            results[name] = {"success": False, "error": str(res)}
        else:
            results[name] = res

    return results


async def _search_platform(platform: str, username: str, timeout: int) -> Dict[str, Any]:
    """Search a single platform via xemoz API."""
    config = PLATFORM_CONFIG.get(platform)
    if not config:
        return {"success": False, "error": f"Unknown platform: {platform}"}

    url = f"{BASE_URL}/{config['endpoint']}"
    params = {config["param"]: username}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}", "platform": platform}

            data = resp.json()
            return _parse_response(platform, data)

    except httpx.TimeoutException:
        return {"success": False, "error": "timeout", "platform": platform}
    except Exception as e:
        return {"success": False, "error": str(e), "platform": platform}


def _parse_response(platform: str, data: Dict) -> Dict[str, Any]:
    """Parse xemoz API response into normalized format."""
    result_data = data.get("result", {})
    if isinstance(result_data, dict):
        inner = result_data.get("result", result_data)
        if isinstance(inner, dict) and result_data.get("status") is False:
            return {"success": False, "error": result_data.get("error", "unknown"), "platform": platform}
    else:
        return {"success": False, "error": "invalid response", "platform": platform}

    parser = _PARSERS.get(platform, _parse_generic)
    parsed = parser(inner)
    parsed["platform"] = platform
    parsed["raw"] = inner
    return parsed


def _parse_instagram(data: Dict) -> Dict[str, Any]:
    return {
        "success": True,
        "username": data.get("username"),
        "real_name": data.get("fullName"),
        "avatar_url": data.get("profilePicHd") or data.get("profilePic"),
        "bio": data.get("bio"),
        "is_verified": data.get("isVerified"),
        "is_private": data.get("isPrivate"),
        "is_business": data.get("isBusiness"),
        "category": data.get("category"),
        "followers": data.get("followers"),
        "following": data.get("following"),
        "posts_count": data.get("postsCount"),
        "external_url": data.get("externalUrl"),
        "user_id": data.get("userId"),
    }


def _parse_tiktok(data: Dict) -> Dict[str, Any]:
    profile = data.get("profile", {})
    avatar = profile.get("avatar", {})
    stats = profile.get("stats", {})

    return {
        "success": True,
        "username": profile.get("username"),
        "real_name": profile.get("nickname"),
        "avatar_url": avatar.get("large") or avatar.get("medium") or avatar.get("thumb"),
        "bio": profile.get("bio"),
        "is_verified": profile.get("verified"),
        "is_private": profile.get("private"),
        "user_id": profile.get("id"),
        "followers": stats.get("followers"),
        "following": stats.get("following"),
        "likes": stats.get("likes"),
        "videos_count": stats.get("videos"),
        "total_videos": data.get("total_videos"),
        "create_time": profile.get("create_time"),
    }


def _parse_twitter(data: Dict) -> Dict[str, Any]:
    return {
        "success": True,
        "username": data.get("username") or data.get("screen_name"),
        "real_name": data.get("name") or data.get("fullname"),
        "avatar_url": data.get("profile_image_url_https") or data.get("image") or data.get("avatar"),
        "bio": data.get("bio") or data.get("description"),
        "is_verified": data.get("verified") or data.get("is_verified"),
        "is_protected": data.get("protected") or data.get("is_protected"),
        "user_id": data.get("id"),
        "followers": data.get("followers_count") or data.get("follower_count"),
        "following": data.get("following_count") or data.get("friends_count"),
        "location": data.get("location"),
        "created_at": data.get("created_at"),
    }


def _parse_youtube(data: Dict) -> Dict[str, Any]:
    channel = data if "channel" not in data else data.get("channel", data)

    return {
        "success": True,
        "username": channel.get("username") or channel.get("customUrl"),
        "real_name": channel.get("title") or channel.get("name"),
        "avatar_url": channel.get("avatar") or channel.get("thumbnails", {}).get("high", {}).get("url") if isinstance(channel.get("thumbnails"), dict) else channel.get("avatar"),
        "bio": channel.get("description"),
        "subscriber_count": channel.get("subscriberCount") or channel.get("subscribers"),
        "video_count": channel.get("videoCount") or channel.get("videos"),
        "view_count": channel.get("viewCount") or channel.get("views"),
        "channel_id": channel.get("id") or channel.get("channelId"),
    }


def _parse_github(data: Dict) -> Dict[str, Any]:
    return {
        "success": True,
        "username": data.get("username"),
        "real_name": data.get("nickname") or data.get("name"),
        "avatar_url": data.get("avatar") or data.get("avatar_url"),
        "bio": data.get("bio"),
        "company": data.get("company"),
        "location": data.get("location"),
        "blog": data.get("blog"),
        "public_repos": data.get("publicRepos") or data.get("public_repos"),
        "followers": data.get("followers"),
        "following": data.get("following"),
        "url": data.get("url") or data.get("html_url"),
    }


def _parse_generic(data: Dict) -> Dict[str, Any]:
    avatar = data.get("avatar") or data.get("avatar_url") or data.get("profilePic") or data.get("image")
    name = data.get("fullName") or data.get("real_name") or data.get("name") or data.get("nickname") or data.get("title")
    return {
        "success": True,
        "username": data.get("username"),
        "real_name": name,
        "avatar_url": avatar,
        "bio": data.get("bio") or data.get("description"),
        "raw_data": data,
    }


_PARSERS = {
    "instagram": _parse_instagram,
    "tiktok": _parse_tiktok,
    "twitter": _parse_twitter,
    "youtube": _parse_youtube,
    "github": _parse_github,
}


def merge_with_maigret(custom_results: Dict[str, Any], maigret_data: Dict[str, Any]) -> Dict[str, Any]:
    """Merge custom API results into Maigret data.

    Adds avatar URLs and real names that Maigret couldn't get.
    Updates found_sites with enriched data from custom APIs.
    """
    found_sites = maigret_data.get("found_sites", [])
    real_names = set(maigret_data.get("real_names", []))
    avatar_urls = list(maigret_data.get("avatar_urls", []))
    custom_profiles = {}

    for platform, data in custom_results.items():
        if not data.get("success"):
            continue

        custom_profiles[platform] = data

        # Extract real name
        name = data.get("real_name")
        if name and len(str(name).strip()) > 1:
            real_names.add(str(name).strip())

        # Extract avatar URL
        avatar = data.get("avatar_url")
        if avatar and str(avatar).startswith("http") and avatar not in avatar_urls:
            avatar_urls.append(avatar)

        # Try to merge into existing found_sites
        merged = False
        for site in found_sites:
            site_name_lower = site.get("site_name", "").lower()
            if platform in site_name_lower or site_name_lower in platform:
                if not site.get("avatar_url") and avatar:
                    site["avatar_url"] = avatar
                if not site.get("real_name") and name:
                    site["real_name"] = name
                if not site.get("bio") and data.get("bio"):
                    site["bio"] = data.get("bio")
                if not site.get("location") and data.get("location"):
                    site["location"] = data.get("location")
                site["custom_api_data"] = data
                merged = True
                break

        # If not found by Maigret, add as new entry
        if not merged and (avatar or name or data.get("followers") is not None):
            found_sites.append({
                "site_name": platform.capitalize(),
                "url_user": f"https://{platform}.com/{data.get('username', '')}" if platform != "youtube" else f"https://youtube.com/@{data.get('username', '')}",
                "url_main": f"https://{platform}.com" if platform != "youtube" else "https://youtube.com",
                "real_name": name,
                "avatar_url": avatar,
                "bio": data.get("bio"),
                "location": data.get("location"),
                "followers": data.get("followers"),
                "following": data.get("following"),
                "is_verified": data.get("is_verified"),
                "is_private": data.get("is_private"),
                "other_usernames": {},
                "other_links": [],
                "ids_data": {},
                "custom_api_data": data,
            })

    maigret_data["found_sites"] = found_sites
    maigret_data["real_names"] = list(real_names)
    maigret_data["avatar_urls"] = avatar_urls
    maigret_data["custom_profiles"] = custom_profiles

    return maigret_data
