"""Stalker - OSINT All-in-One Investigation Tool.

Combines Maigret (username search), ExifTools (metadata extraction),
Cloudflare bypass (FlareSolverr), and Google Dork (people search)
into a single CLI tool.
"""

import sys
import os
import asyncio
import warnings
import logging

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

warnings.filterwarnings("ignore")
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

__version__ = "1.0.0"
__author__ = "Stalker Project"
