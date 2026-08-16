"""Configuration loader — with Termux auto-detection for mobile optimization."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

IS_TERMUX = Path("/data/data/com.termux").is_dir()

class Config:
    EXIFTOOLS_API_KEY      = os.getenv("EXIFTOOLS_API_KEY", "")
    NUMVERIFY_API_KEY      = os.getenv("NUMVERIFY_API_KEY", "")
    VERIPHONE_API_KEY      = os.getenv("VERIPHONE_API_KEY", "")
    TELEGRAM_BOT_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID       = os.getenv("TELEGRAM_CHAT_ID", "")
    DORK_MAX_RESULTS       = int(os.getenv("DORK_MAX_RESULTS", "10" if IS_TERMUX else "20"))
    # Comma-separated HTTP/SOCKS proxies for search engines (rotate on rate-limit).
    # e.g. DORK_PROXY_LIST="http://user:pass@host:8080,http://host2:3128"
    DORK_PROXY_LIST        = [p.strip() for p in os.getenv("DORK_PROXY_LIST", "").split(",") if p.strip()]
    # Extra delay between Google queries (seconds) — helps avoid rate-limit.
    DORK_SLEEP             = float(os.getenv("DORK_SLEEP", "0"))
    MAIGRET_TIMEOUT        = int(os.getenv("MAIGRET_TIMEOUT", "30" if IS_TERMUX else "60"))
    # KEY FIX: Termux/mobile → max 100 sites (prevents DNS flood on carrier network)
    # Desktop/VPN → up to 500 sites
    MAIGRET_MAX_SITES      = int(os.getenv("MAIGRET_MAX_SITES", "100" if IS_TERMUX else "500"))
    OUTPUT_DIR             = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "output")))
    IMAGE_DIR              = Path(os.getenv("IMAGE_DIR", str(BASE_DIR / "output" / "images")))
    STEALTH_MODE           = os.getenv("STEALTH_MODE", "false").lower() in ("true","1","yes")
    STEALTH_RANDOM_UA      = os.getenv("STEALTH_RANDOM_UA", "true").lower()  in ("true","1","yes")
    REQUEST_DELAY          = float(os.getenv("REQUEST_DELAY", "1.0" if IS_TERMUX else "0.5"))
    FACE_SEARCH_MAX_AVATARS= int(os.getenv("FACE_SEARCH_MAX_AVATARS", "3"))
    # DB lokal (SIAK/NPWP) — default DI DALAM project (databaselocal/),
    # bukan di luar folder. Env LOCALDB_DIR tetap menang kalau di-set.
    LOCALDB_DIR            = os.getenv("LOCALDB_DIR", str(BASE_DIR / "databaselocal"))
    IS_TERMUX              = IS_TERMUX

    @classmethod
    def ensure_dirs(cls):
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.IMAGE_DIR.mkdir(parents=True, exist_ok=True)
