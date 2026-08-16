"""Profile image downloader for EXIF analysis."""

from __future__ import annotations
from typing import Optional
from pathlib import Path
import httpx
import hashlib
from ..config import Config


async def download_profile_image(url: str, username: str) -> Optional[Path]:
    """Download a profile image from a URL to the local image directory."""
    Config.ensure_dirs()

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return None

            content_type = response.headers.get("content-type", "")
            ext = _guess_extension(content_type)
            if not ext:
                return None

            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"{username}_{url_hash}.{ext}"
            filepath = Config.IMAGE_DIR / filename

            with open(filepath, "wb") as f:
                f.write(response.content)

            return filepath
    except Exception:
        return None


async def download_images_from_urls(urls: list[str], username: str) -> list[dict]:
    """Download multiple profile images and return results."""
    results = []
    for url in urls[:10]:  # Limit to 10 images per user
        if not url:
            continue
        filepath = await download_profile_image(url, username)
        results.append({
            "url": url,
            "local_path": str(filepath) if filepath else None,
            "success": filepath is not None,
        })
    return results


def _guess_extension(content_type: str) -> Optional[str]:
    """Guess file extension from content-type header."""
    mapping = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/bmp": "bmp",
        "image/tiff": "tiff",
    }
    return mapping.get(content_type.split(";")[0].strip().lower())
