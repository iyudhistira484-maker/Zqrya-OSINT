#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zqrya v3.0 - Username Module (Enhanced)"""

import asyncio
import hashlib
import random
from typing import Dict, List, Optional
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup
from modules.base import BaseModule
from sources.social_media import SocialMediaDB


class UsernameModule(BaseModule):  # <-- PASTIKAN NAMA CLASS INI
    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        self.name = "username"
        self.social_db = SocialMediaDB()
        
        # Rotating User-Agents
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        ]
        
        self.base_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def _get_headers(self) -> Dict:
        """Get headers with random User-Agent"""
        headers = self.base_headers.copy()
        headers['User-Agent'] = random.choice(self.user_agents)
        return headers

    async def scan(self, username: str) -> Dict:
        username = username.strip().lstrip('@')
        if not username:
            return self.error_result(username, "Empty username")

        platforms = self.social_db.get_all_platforms()
        found = []
        semaphore = asyncio.Semaphore(10)

        async def check_platform(platform: Dict) -> Optional[Dict]:
            async with semaphore:
                url = platform['url'].format(username)
                headers = self._get_headers()
                
                try:
                    async with self.session.get(
                        url, 
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=8),
                        allow_redirects=True,
                        ssl=False
                    ) as resp:
                        
                        if resp.status == 429:
                            await asyncio.sleep(2)
                            return None
                        
                        if resp.status == 200:
                            try:
                                html = await resp.text(encoding='utf-8', errors='ignore', limit=200000)
                                soup = BeautifulSoup(html, 'html.parser')
                                title = (soup.title.string or '').lower() if soup.title else ''
                                
                                # Filter not found
                                not_found = ['404', 'page not found', 'user not found', 
                                            "doesn't exist", 'profile not found']
                                
                                body_text = html.lower()[:5000]
                                if any(b in title for b in not_found) or \
                                   any(b in body_text for b in ['user not found', 'page not found']):
                                    return None
                                
                                # Judul halaman (data asli yang diambil, bukan "nama profil")
                                page_title = (soup.title.string or '').strip()[:200] if soup.title else None
                                og_title = None
                                og = soup.select_one('meta[property="og:title"]')
                                if og and og.get('content'):
                                    og_title = og.get('content').strip()[:200]

                                return {
                                    'platform': platform['name'],
                                    'url': str(resp.url),
                                    'category': platform.get('category', 'social'),
                                    'page_title': page_title,
                                    'og_title': og_title,
                                    'status': 'found'
                                }
                            except Exception:
                                return {
                                    'platform': platform['name'],
                                    'url': str(resp.url),
                                    'category': platform.get('category', 'social'),
                                    'page_title': None,
                                    'og_title': None,
                                    'status': 'found'
                                }
                        
                        elif resp.status in (301, 302, 307, 308):
                            loc = resp.headers.get('Location', '')
                            if username.lower() in loc.lower() or 'profile' in loc.lower():
                                return {
                                    'platform': platform['name'],
                                    'url': loc,
                                    'category': platform.get('category', 'social'),
                                    'page_title': None,
                                    'og_title': None,
                                    'status': 'redirect'
                                }
                            
                except (asyncio.TimeoutError, aiohttp.ClientError):
                    pass
                except Exception:
                    pass
                return None

        # Process in batches
        batch_size = 10
        for i in range(0, len(platforms), batch_size):
            batch = platforms[i:i+batch_size]
            tasks = [check_platform(p) for p in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for r in results:
                if isinstance(r, dict) and r:
                    found.append(r)
            
            if i + batch_size < len(platforms):
                await asyncio.sleep(random.uniform(0.3, 0.8))

        # By category
        by_cat = {}
        for f in found:
            cat = f.get('category', 'other')
            by_cat.setdefault(cat, []).append(f)

        possible_emails = [f"{username}@{d}" for d in
                           ['gmail.com', 'yahoo.com', 'outlook.com', 
                            'hotmail.com', 'protonmail.com', 'mail.com']]
        variations = self._generate_variations(username)[:10]

        # Verifikasi kandidat ke sumber publik (eksistensi, bukan kepemilikan)
        verified_emails = await self._verify_emails(possible_emails)
        verified_variations = await self._verify_variations(variations)

        # Jejak historis (Wayback Machine) — profil lama/hapus
        try:
            from stalker.modules.wayback_checker import full_wayback_intel
            wayback = await full_wayback_intel(username)
        except Exception:
            wayback = {'total_archived': 0, 'platforms_archived': {}}

        data = {
            'username': username,
            'total_checked': len(platforms),
            'total_found': len(found),
            'found': found,
            'by_category': by_cat,
            'profiles': [f['url'] for f in found],
            'possible_emails': possible_emails,
            'verified_emails': verified_emails,
            'variations': variations,
            'verified_variations': verified_variations,
            'wayback': wayback,
            'categories': list(by_cat.keys()),
            'note': 'possible_emails & variations = tebakan; verified_* = eksistensi profil publik, bukan kepemilikan.',
            'timestamp': datetime.now().isoformat()
        }
        return self.create_result(username, data, [f['platform'] for f in found])

    def _generate_variations(self, u: str) -> List[str]:
        v = [u.lower(), u.upper(), u.capitalize()]
        for i in range(5):
            v += [f"{u}{i}", f"{u}_{i}", f"{u}.{i}"]
        for s in ['real', 'official', 'admin', '_id', '_official', 'official_']:
            v += [f"{u}{s}", f"{s}{u}"]
        return list(dict.fromkeys(v))

    async def _verify_emails(self, emails: List[str]) -> List[Dict]:
        """Verify candidate emails exist via Gravatar (public, real signal)."""
        verified = []
        for email in emails[:6]:
            gh = hashlib.md5(email.encode()).hexdigest()
            try:
                async with self.session.get(
                    f'https://www.gravatar.com/avatar/{gh}?d=404',
                    timeout=aiohttp.ClientTimeout(total=4)
                ) as r:
                    if r.status == 200:
                        verified.append({
                            'email': email,
                            'gravatar': f'https://www.gravatar.com/avatar/{gh}',
                            'source': 'gravatar',
                        })
            except Exception:
                pass
        return verified

    async def _verify_variations(self, variations: List[str]) -> List[Dict]:
        """Check which username variations have an existing public profile."""
        verified = []
        tasks = []
        metas = []
        for v in variations:
            for platform, url_tpl in (('telegram', 'https://t.me/{}'),
                                      ('github', 'https://github.com/{}')):
                tasks.append(self.check_profile_exists(v, url_tpl.format(v), platform))
                metas.append((v, platform))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for (v, platform), r in zip(metas, results):
            if r is True:
                verified.append({'username': v, 'platform': platform})
        return verified