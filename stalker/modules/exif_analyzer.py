"""EXIF metadata extraction.

Layered strategy (gratis, tanpa API key):
1. ExifTools.com REST API — kalau EXIFTOOLS_API_KEY tersedia (metadata terlengkap)
2. Pillow lokal (PIL) — default; ekstrak Make/Model/DateTime/Software/GPS dari file
3. URL → unduh dulu ke temp, lalu proses dengan Pillow
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from pathlib import Path
import base64
import tempfile
import httpx
from ..config import Config


try:
    from PIL import Image, ExifTags
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


EXIFTOOLS_API_BASE = "https://exiftools.com/api/v1"


def _pillow_metadata(filepath: Path) -> Optional[Dict[str, Any]]:
    """Extract EXIF/GPS/IPTC via Pillow (lokal, gratis). Returns {} kalau tidak ada EXIF."""
    if not HAS_PILLOW:
        return None
    try:
        with Image.open(filepath) as img:
            exif_raw = img.getexif()
            if not exif_raw:
                return {}
            meta: Dict[str, Any] = {"exif": {}}
            for tag_id, value in exif_raw.items():
                tag = ExifTags.TAGS.get(tag_id, str(tag_id))
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="replace")
                    except Exception:
                        value = str(value)
                meta["exif"][tag] = str(value)
            # GPS dari IFD khusus
            gps_ifd = exif_raw.get_ifd(ExifTags.IFD.GPSInfo)
            if gps_ifd:
                def _num(v):
                    """IFDRational/Fraction → float."""
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return v

                gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
                meta["gps"] = {str(k): _num(v) for k, v in gps.items()}
                # koordinat desimal kalau ada
                try:
                    lat_d = [_num(x) for x in (gps.get("GPSLatitude") or ())]
                    lat_r = gps.get("GPSLatitudeRef") or "N"
                    lon_d = [_num(x) for x in (gps.get("GPSLongitude") or ())]
                    lon_r = gps.get("GPSLongitudeRef") or "E"
                    if lat_d and lon_d and len(lat_d) == 3:
                        lat = lat_d[0] + lat_d[1] / 60 + lat_d[2] / 3600
                        lon = lon_d[0] + lon_d[1] / 60 + lon_d[2] / 3600
                        if str(lat_r).upper().startswith("S"):
                            lat = -lat
                        if str(lon_r).upper().startswith("W"):
                            lon = -lon
                        meta["gps_decimal"] = f"{round(lat, 6)}, {round(lon, 6)}"
                        meta["gps_coords"] = [round(lat, 6), round(lon, 6)]
                except Exception:
                    pass
            if not meta["exif"] and not meta.get("gps"):
                return {}
            return meta
    except Exception:
        return None


async def extract_from_url(image_url: str) -> Optional[Dict[str, Any]]:
    """Extract EXIF metadata from an image URL (ExifTools API atau Pillow lokal)."""
    if Config.EXIFTOOLS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{EXIFTOOLS_API_BASE}/extract",
                    headers={"X-API-Key": Config.EXIFTOOLS_API_KEY},
                    json={"url": image_url},
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return data.get("metadata", {})
        except Exception:
            pass
    # Fallback: unduh ke temp lalu proses lokal
    if not HAS_PILLOW:
        return None
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(image_url)
            if resp.status_code != 200:
                return None
            suffix = Path(image_url.split("?")[0]).suffix.lower() or ".jpg"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = Path(tmp.name)
            try:
                return _pillow_metadata(tmp_path) or None
            finally:
                tmp_path.unlink(missing_ok=True)
    except Exception:
        return None


async def extract_from_file(filepath: str | Path) -> Optional[Dict[str, Any]]:
    """Extract EXIF metadata from a local image file (ExifTools API atau Pillow lokal)."""
    filepath = Path(filepath)
    if not filepath.exists():
        return None

    if Config.EXIFTOOLS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
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
        except Exception:
            pass
    return _pillow_metadata(filepath)


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
