"""Face search — multi-engine reverse image lookup.

Engines:
  - Yandex (via yandex.com/images)
  - Google Lens (via lens.google.com)
  - Bing Images (via bing.com/images)
  - TinEye (via tineye.com)
  - Search4Faces (search4faces.com API)

All engines are HTTP-based (httpx) — no browser automation, no extra deps.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio
import re
import urllib.parse
import httpx

from ..config import Config
from .proxy_manager import prepare_client


# ============================================================
#  YANDEX (uses reverse_image module)
# ============================================================

async def _search_yandex(image_url: str, max_results: int = 15) -> Dict[str, Any]:
    """Search Yandex Images via shared reverse_image module."""
    from . import reverse_image
    result = await reverse_image.reverse_search_url(image_url, max_results)
    return {
        "engine": "yandex",
        "success": result.get("success", False),
        "pages_found": result.get("pages_found", []),
        "similar_images": result.get("similar_images", []),
        "error": result.get("error", ""),
    }


# ============================================================
#  GOOGLE LENS
# ============================================================

async def _search_google_lens(image_url: str, max_results: int = 10) -> Dict[str, Any]:
    """Search Google Lens / Google Images with a URL."""
    params = {"image_url": image_url, "sbisrc": "1"}
    google_url = "https://www.google.com/searchbyimage?" + urllib.parse.urlencode(params)
    try:
        async with prepare_client(
            timeout=20, follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            resp = await client.get(google_url)
            if resp.status_code != 200:
                return {"engine": "google_lens", "success": False, "error": f"HTTP {resp.status_code}"}
            html = resp.text
            pages = _extract_google_pages(html, max_results)
            return {"engine": "google_lens", "success": True, "pages_found": pages, "similar_images": []}
    except Exception as e:
        return {"engine": "google_lens", "success": False, "error": str(e)}


def _extract_google_pages(html: str, max_results: int) -> List[Dict[str, str]]:
    pages = []
    # Google search result links pattern
    for match in re.finditer(
        r'<a[^>]*href="(/url\?q=([^"&]+)[^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    ):
        url = match.group(2)
        title = _clean(match.group(3))
        if url.startswith("http") and "google.com" not in url:
            if url not in [p["url"] for p in pages]:
                pages.append({"url": url, "title": title, "snippet": ""})
    return pages[:max_results]


# ============================================================
#  BING IMAGES
# ============================================================

async def _search_bing(image_url: str, max_results: int = 10) -> Dict[str, Any]:
    """Search Bing Images with a URL (reverse image lookup)."""
    bing_url = "https://www.bing.com/images/searchbyimage"
    params = {"q": "imgurl:" + image_url, "form": "QBIR"}
    try:
        async with prepare_client(
            timeout=20, follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            resp = await client.get(bing_url, params=params)
            if resp.status_code != 200:
                return {"engine": "bing", "success": False, "error": f"HTTP {resp.status_code}"}
            html = resp.text
            pages = _extract_bing_pages(html, max_results)
            similar = _extract_bing_similar(html, max_results)
            return {"engine": "bing", "success": True, "pages_found": pages, "similar_images": similar}
    except Exception as e:
        return {"engine": "bing", "success": False, "error": str(e)}


def _extract_bing_pages(html: str, max_results: int) -> List[Dict[str, str]]:
    pages = []
    for match in re.finditer(
        r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    ):
        url = match.group(1)
        title = _clean(match.group(2))
        if url.startswith("http") and "bing.com" not in url and "microsoft.com" not in url:
            if url not in [p["url"] for p in pages]:
                pages.append({"url": url, "title": title, "snippet": ""})
    return pages[:max_results]


def _extract_bing_similar(html: str, max_results: int) -> List[Dict[str, str]]:
    similar = []
    for match in re.finditer(r'"thumbnailUrl"\s*:\s*"(https?://[^"]+)"', html):
        url = match.group(1)
        if url not in [s["url"] for s in similar]:
            similar.append({"url": url, "title": ""})
    return similar[:max_results]


# ============================================================
#  TINEYE
# ============================================================

async def _search_tineye(image_url: str, max_results: int = 10) -> Dict[str, Any]:
    """Search TinEye with an image URL."""
    tineye_url = "https://tineye.com/search"
    params = {"url": image_url}
    try:
        async with prepare_client(
            timeout=25, follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as client:
            resp = await client.get(tineye_url, params=params)
            if resp.status_code != 200:
                return {"engine": "tineye", "success": False, "error": f"HTTP {resp.status_code}"}
            html = resp.text
            pages = _extract_tineye_pages(html, max_results)
            return {"engine": "tineye", "success": True, "pages_found": pages, "similar_images": []}
    except Exception as e:
        return {"engine": "tineye", "success": False, "error": str(e)}


def _extract_tineye_pages(html: str, max_results: int) -> List[Dict[str, str]]:
    pages = []
    for match in re.finditer(
        r'class="match"[^>]*>.*?href="([^"]+)"[^>]*>(.*?)</a>.*?<p[^>]*>(.*?)</p>',
        html, re.DOTALL,
    ):
        url = match.group(1)
        title = _clean(match.group(2))
        snippet = _clean(match.group(3))
        if url.startswith("http") and url not in [p["url"] for p in pages]:
            pages.append({"url": url, "title": title, "snippet": snippet[:200]})
    return pages[:max_results]


# ============================================================
#  SEARCH4FACES
# ============================================================

async def _search_4faces(image_url: str, max_results: int = 15) -> Dict[str, Any]:
    """Search search4faces.com with an image URL."""
    try:
        async with prepare_client(
            timeout=25, follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/html",
                "Origin": "https://search4faces.com",
                "Referer": "https://search4faces.com/",
            },
        ) as client:
            # Try the API JSON endpoint
            resp = await client.post(
                "https://search4faces.com/api/search",
                json={"url": image_url, "limit": max_results},
            )
            if resp.status_code == 200:
                data = resp.json()
                pages = []
                for r in data.get("results", [])[:max_results]:
                    pages.append({
                        "url": r.get("url", "") or r.get("link", ""),
                        "title": r.get("title", "") or r.get("name", ""),
                        "snippet": r.get("snippet", "") or r.get("profile", ""),
                    })
                return {"engine": "search4faces", "success": True, "pages_found": pages, "similar_images": []}

            # Fallback: HTML page
            html_url = f"https://search4faces.com/search.html?url={urllib.parse.quote(image_url)}"
            resp2 = await client.get(html_url)
            if resp2.status_code == 200:
                pages = _extract_4faces_html(resp2.text, max_results)
                return {"engine": "search4faces", "success": True, "pages_found": pages, "similar_images": []}

            return {"engine": "search4faces", "success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"engine": "search4faces", "success": False, "error": str(e)}


def _extract_4faces_html(html: str, max_results: int) -> List[Dict[str, str]]:
    pages = []
    for match in re.finditer(
        r'<a[^>]*href="(https?://[^"]+)"[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    ):
        url = match.group(1)
        title = _clean(match.group(2))
        if url not in [p["url"] for p in pages]:
            pages.append({"url": url, "title": title, "snippet": ""})
    return pages[:max_results]


def _safe(result, engine_name: str) -> Dict[str, Any]:
    if isinstance(result, Exception):
        return {"engine": engine_name, "success": False, "error": str(result)}
    return result


# ============================================================
#  MULTI-ENGINE
# ============================================================

async def search_all_engines(avatar_urls: List[str]) -> Dict[str, Any]:
    """Run all 3 engines on up to Config.FACE_SEARCH_MAX_AVATARS avatars.

    Returns: {avatar_url: {yandex: {...}, google_lens: {...}, search4faces: {...}}}
    """
    urls = avatar_urls[:Config.FACE_SEARCH_MAX_AVATARS]
    if not urls:
        return {}

    results: Dict[str, Dict] = {url: {} for url in urls}

    async def _run_engines_for_url(url: str):
        yandex, google, bing, tineye, s4f = await asyncio.gather(
            _search_yandex(url),
            _search_google_lens(url),
            _search_bing(url),
            _search_tineye(url),
            _search_4faces(url),
            return_exceptions=True,
        )
        return url, {
            "yandex": _safe(yandex, "yandex"),
            "google_lens": _safe(google, "google_lens"),
            "bing": _safe(bing, "bing"),
            "tineye": _safe(tineye, "tineye"),
            "search4faces": _safe(s4f, "search4faces"),
        }

    tasks = [_run_engines_for_url(url) for url in urls]
    gathered = await asyncio.gather(*tasks, return_exceptions=True)
    for item in gathered:
        if isinstance(item, tuple):
            url, data = item
            results[url] = data

    return results


def summary(results: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate face search results across all engines and avatars."""
    total_pages = 0
    total_similar = 0
    engines_ok: Dict[str, int] = {}
    avatars_searched = 0

    for avatar_url, engines in results.items():
        avatars_searched += 1
        for eng_name, eng_data in engines.items():
            if isinstance(eng_data, dict) and eng_data.get("success"):
                engines_ok[eng_name] = engines_ok.get(eng_name, 0) + 1
                total_pages += len(eng_data.get("pages_found", []))
                total_similar += len(eng_data.get("similar_images", []))

    return {
        "avatars_searched": avatars_searched,
        "total_pages_found": total_pages,
        "total_similar_images": total_similar,
        "engines_used": engines_ok,
    }


def _clean(text: str) -> str:
    import html as html_mod
    text = html_mod.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]
