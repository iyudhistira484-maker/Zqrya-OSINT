"""Reverse image search via Yandex Images.

Takes an avatar/profile photo URL and searches Yandex Images to find:
- Other websites where the same photo appears
- Visually similar images
- Pages containing the image

This is far more useful than EXIF for social media avatars since
platforms strip EXIF data. Reverse image search can find the same
person across different platforms even with different usernames.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio
import re
import urllib.parse
import httpx
from .proxy_manager import prepare_client



async def reverse_search_url(image_url: str, max_results: int = 20) -> Dict[str, Any]:
    """Search Yandex Images with an image URL.

    Uses Yandex's CBIR (Content-Based Image Retrieval) endpoint.

    Returns:
        {
            "success": bool,
            "image_url": str,
            "pages_found": [{url, title, snippet}],
            "similar_images": [{url, title}],
            "total_results": int,
        }
    """
    try:
        # Yandex reverse image search via URL
        # Method: POST image URL to Yandex CBIR endpoint, parse HTML results
        cbir_url = f"https://yandex.com/images/search?rpt=imageview&url={urllib.parse.quote(image_url, safe='')}"

        async with prepare_client(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            resp = await client.get(cbir_url)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}", "image_url": image_url}

            html = resp.text
            pages = _extract_pages(html, max_results)
            similar = _extract_similar_images(html, max_results)

            return {
                "success": True,
                "image_url": image_url,
                "pages_found": pages,
                "similar_images": similar,
                "total_results": len(pages) + len(similar),
            }

    except httpx.TimeoutException:
        return {"success": False, "error": "timeout", "image_url": image_url}
    except Exception as e:
        return {"success": False, "error": str(e), "image_url": image_url}


async def search_all_avatars(avatar_urls: List[str], max_results: int = 15) -> Dict[str, Any]:
    """Run reverse image search on all avatar URLs in parallel.

    Returns:
        {avatar_url: {success, pages_found, similar_images, ...}}
    """
    if not avatar_urls:
        return {}

    # Limit to 5 avatars to avoid rate limiting
    urls_to_search = avatar_urls[:5]

    tasks = [reverse_search_url(url, max_results) for url in urls_to_search]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = {}
    for url, res in zip(urls_to_search, results):
        if isinstance(res, Exception):
            output[url] = {"success": False, "error": str(res), "image_url": url}
        else:
            output[url] = res

    return output


def _extract_pages(html: str, max_results: int) -> List[Dict[str, str]]:
    """Extract page results from Yandex Images HTML response."""
    pages = []

    # Yandex uses data attributes in HTML for image search results
    # Look for links to pages containing the image
    # Pattern: data-ref links or CbirSites-Item
    patterns = [
        # CbirSites items
        r'class="CbirSites-Item"[^>]*>.*?href="([^"]+)"[^>]*>([^<]*)</a>',
        # Generic link patterns in image search
        r'data-ref="([^"]+)"[^>]*title="([^"]*)"',
        # Other sites containing this image
        r'"sites":\s*\[.*?"url":\s*"([^"]+)".*?"title":\s*"([^"]*)"',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        for url, title in matches[:max_results]:
            if url.startswith("http") and url not in [p["url"] for p in pages]:
                pages.append({
                    "url": url,
                    "title": _clean_text(title),
                    "snippet": "",
                })

    # Also try JSON embedded in script tags
    json_pattern = r'"url"\s*:\s*"(https?://[^"]+)"[^}]*"title"\s*:\s*"([^"]*)"'
    json_matches = re.findall(json_pattern, html)
    for url, title in json_matches[:max_results]:
        if url.startswith("http") and "yandex" not in url.lower():
            if url not in [p["url"] for p in pages]:
                pages.append({
                    "url": url,
                    "title": _clean_text(title),
                    "snippet": "",
                })

    return pages[:max_results]


def _extract_similar_images(html: str, max_results: int) -> List[Dict[str, str]]:
    """Extract similar image results from Yandex Images HTML."""
    similar = []

    # Look for similar image thumbnails
    patterns = [
        r'class="SimpleImage[^"]*"[^>]*>.*?src="([^"]+)".*?alt="([^"]*)"',
        r'data-src="(https?://[^"]+)"[^>]*alt="([^"]*)"',
        r'"imgUrl"\s*:\s*"(https?://[^"]+)"[^}]*"title"\s*:\s*"([^"]*)"',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        for url, title in matches[:max_results]:
            if url.startswith("http") and url not in [s["url"] for s in similar]:
                similar.append({
                    "url": url,
                    "title": _clean_text(title),
                })

    return similar[:max_results]


def _clean_text(text: str) -> str:
    """Clean HTML entities and whitespace from text."""
    import html as html_mod
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:200]  # Truncate long titles
