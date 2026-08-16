#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zqrya v3.0 - Maigret Module (600+ platforms)

Bridges Zqrya to the vendored Maigret engine.
Finds profiles, real names, avatars, bios across 600+ social networks.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
from modules.base import BaseModule

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _ensure_maigret_paths():
    """Ensure maigret is importable.
    IMPORTANT: only the repo root `maigret/` goes on sys.path, because the
    package lives at `maigret/maigret/`. Inserting `maigret/maigret` directly
    makes `import maigret` resolve to the inner `maigret.py` module instead
    of the package.
    """
    for p in [str(PROJECT_ROOT), str(PROJECT_ROOT / 'maigret')]:
        if p not in sys.path:
            sys.path.insert(0, p)


class MaigretModule(BaseModule):
    """Deep username search using the Maigret engine (600+ platforms)"""

    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        self.name = "maigret"
        self._db = None

    async def _load_db(self):
        if self._db is not None:
            return self._db
        from maigret.sites import MaigretDatabase
        db_path = PROJECT_ROOT / 'maigret' / 'maigret' / 'resources' / 'data.json'
        db = MaigretDatabase()
        if db_path.exists():
            db = db.load_from_path(str(db_path))
        self._db = db
        return db

    async def scan(self, username: str, max_sites: int = 300) -> Dict:
        _ensure_maigret_paths()
        username = username.strip().lstrip('@')
        if not username:
            return self.error_result(username, "Empty username")

        try:
            from maigret.sites import MaigretDatabase  # noqa: F401
            import maigret
            from maigret.notify import QueryNotifyPrint
            from stalker.config import Config
        except ImportError as e:
            return self.error_result(username, f"Maigret engine not available: {e}")

        # Use the pipeline's maigret runner (handles DNS patch, logging, cloudflare)
        from stalker.pipeline import _run_maigret

        try:
            data = await _run_maigret(username, max_sites=max_sites)
        except Exception as e:
            return self.error_result(username, str(e))

        found = data.get('found_sites', [])
        total_checked = data.get('total_checked', 0)
        real_names = data.get('real_names', [])
        avatar_urls = data.get('avatar_urls', [])

        # Normalize to Zqrya module format
        platforms = []
        for site in found:
            platforms.append({
                'platform': site.get('site_name', ''),
                'url': site.get('url_user') or site.get('url_main', ''),
                'real_name': site.get('real_name'),
                'avatar_url': site.get('avatar_url'),
                'bio': (site.get('bio') or '')[:200],
                'location': site.get('location'),
                'category': 'maigret',
                'status': 'found'
            })

        result_data = {
            'username': username,
            'total_checked': total_checked,
            'total_found': len(platforms),
            'found': platforms,
            'real_names': real_names[:10],
            'avatar_urls': avatar_urls[:10],
            'engine': 'maigret',
            'sites_checked': total_checked,
            'timestamp': datetime.now().isoformat()
        }

        return self.create_result(username, result_data, ['maigret'])

    async def scan_variants(self, username: str, max_variants: int = 50) -> List[str]:
        """Generate username variants (150+ permutations)"""
        from stalker.modules.username_variants import generate_variants
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, generate_variants, username, max_variants)
