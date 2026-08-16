"""ExifTools.com REST API client for metadata extraction."""

from __future__ import annotations
from typing import Dict, Any, Optional
from pathlib import Path
import base64
import httpx
from ..config import Config


EXIFTOOLS_API_BASE = "https://exiftools.com/api/v1"


async def extract_from_url(image_url: str) -> Optional[Dict[str, Any]]:
    """Extract EXIF metadata from an image URL."""
    if not Config.EXIFTOOLS_API_KEY:
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                f"{EXIFTOOLS_API_BASE}/extract",
                headers={"X-API-Key": Config.EXIFTOOLS_API_KEY},
                json={"url": image_url},
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("metadata", {})
            return None
        except Exception:
            return None


async def extract_from_file(filepath: str | Path) -> Optional[Dict[str, Any]]:
    """Extract EXIF metadata from a local image file."""
    if not Config.EXIFTOOLS_API_KEY:
        return None

    filepath = Path(filepath)
    if not filepath.exists():
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            with open(filepath, "rb") as f:
                response = await client.post(
                    f"{EXIFTOOLS_API_BASE}/extract",
                    headers={"X-API-Key": Config.EXIFTOOLS_API_KEY},
                    files={"file": (filepath.name, f, "image/jpeg")},
                )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("metadata", {})
            return None
        except Exception:
            return None


def summarize_metadata(metadata: Dict[str, Any]) -> Dict[str, str]:
    """Extract human-readable summary from raw EXIF metadata."""
    summary = {}

    exif = metadata.get("exif", metadata.get("EXIF", {}))
    if exif:
        if "Make" in exif:
            summary["camera"] = f"{exif.get('Make', '')} {exif.get('Model', '')}".strip()
        if "DateTimeOriginal" in exif:
            summary["date_taken"] = exif["DateTimeOriginal"]
        if "GPSLatitude" in exif and "GPSLongitude" in exif:
            summary["gps"] = f"{exif['GPSLatitude']}, {exif['GPSLongitude']}"
        if "Software" in exif:
            summary["software"] = exif["Software"]

    iptc = metadata.get("iptc", metadata.get("IPTC", {}))
    if iptc:
        if "Creator" in iptc:
            summary["creator"] = iptc["Creator"]
        if "Copyright" in iptc:
            summary["copyright"] = iptc["Copyright"]

    file_info = metadata.get("File", {})
    if file_info:
        summary["file_size"] = str(file_info.get("Size", ""))
        summary["file_type"] = file_info.get("Type", "")

    return summary
