#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zqrya v3.0 - URL Module (Website Footprint)
Analyzes a full website URL: page metadata, social media links,
contact emails, tech stack, and security headers.
"""

import re
import asyncio
import aiohttp
from datetime import datetime
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from modules.base import BaseModule


class URLModule(BaseModule):
    """Website footprint analysis for a full URL (new in v3.0)"""

    def __init__(self, session):
        super().__init__(session)
        self.name = "url"

        # Social platform detection patterns (domain → platform name)
        self.social_patterns = {
            'facebook.com': 'Facebook',
            'fb.com': 'Facebook',
            'instagram.com': 'Instagram',
            'twitter.com': 'Twitter',
            'x.com': 'Twitter (X)',
            'linkedin.com': 'LinkedIn',
            'youtube.com': 'YouTube',
            'youtu.be': 'YouTube',
            'tiktok.com': 'TikTok',
            'threads.net': 'Threads',
            't.me': 'Telegram',
            'wa.me': 'WhatsApp',
            'whatsapp.com': 'WhatsApp',
            'discord.com': 'Discord',
            'discord.gg': 'Discord',
            'github.com': 'GitHub',
            'gitlab.com': 'GitLab',
            'reddit.com': 'Reddit',
            'pinterest.com': 'Pinterest',
            'snapchat.com': 'Snapchat',
            'tumblr.com': 'Tumblr',
            'medium.com': 'Medium',
            'twitch.tv': 'Twitch',
            'spotify.com': 'Spotify',
            'soundcloud.com': 'SoundCloud',
            'vk.com': 'VK',
            'weibo.com': 'Weibo',
            'tripadvisor.com': 'TripAdvisor',
            'foursquare.com': 'Foursquare',
            'behance.net': 'Behance',
            'dribbble.com': 'Dribbble',
            'patreon.com': 'Patreon',
            'buymeacoffee.com': 'BuyMeACoffee',
            'ko-fi.com': 'Ko-fi',
            'linktr.ee': 'Linktree',
            'paypal.com': 'PayPal',
            'shopee.co.id': 'Shopee',
            'tokopedia.com': 'Tokopedia',
            'bukalapak.com': 'Bukalapak',
            'traveloka.com': 'Traveloka',
            'gojek.com': 'Gojek',
            'grab.com': 'Grab',
        }

        # Technology detection patterns (reused from domain module, lightweight)
        self.tech_patterns = {
            'WordPress': ['wp-content', 'wp-includes', 'wp-json'],
            'Joomla': ['joomla', 'com_content'],
            'Shopify': ['cdn.shopify', 'myshopify.com'],
            'Wix': ['wix.com', 'wix-static'],
            'Squarespace': ['squarespace', 'static.squarespace'],
            'React': ['react', '_reactRoot'],
            'Vue.js': ['__vue', 'vue.js'],
            'Angular': ['ng-version', 'ng-app'],
            'Next.js': ['__next', '_next/static'],
            'Nuxt.js': ['__nuxt', '_nuxt/'],
            'Svelte': ['__svelte', 'svelte-'],
            'jQuery': ['jquery', 'jQuery'],
            'Bootstrap': ['bootstrap', 'bs.'],
            'Tailwind': ['tailwind', 'tw-'],
            'Cloudflare': ['cloudflare', '__cfduid', 'cf-ray'],
            'nginx': ['nginx', 'nginx/'],
            'Apache': ['apache', 'apache/'],
            'IIS': ['iis', 'microsoft-iis'],
            'LiteSpeed': ['litespeed', 'lscache'],
            'Google Analytics': ['google-analytics', 'gtag'],
            'Facebook Pixel': ['fbq(', 'facebook-pixel'],
            'Stripe': ['stripe', 'js.stripe'],
            'PayPal': ['paypal', 'paypalobjects'],
            'Midtrans': ['midtrans', 'veritrans'],
            'Xendit': ['xendit'],
        }

    async def scan(self, url: str) -> Dict:
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        parsed = urlparse(url)
        domain = parsed.netloc.split(':')[0]
        if domain.startswith('www.'):
            domain = domain[4:]

        result = {
            'url': url,
            'domain': domain,
            'final_url': None,
            'status': None,
            'title': None,
            'description': None,
            'og_title': None,
            'og_image': None,
            'favicon': None,
            'language': None,
            'author': None,
            'keywords': [],
            'technologies': [],
            'social_links': [],
            'emails': [],
            'phone_numbers': [],
            'links_count': 0,
            'external_links_count': 0,
            'server_header': None,
            'x_powered_by': None,
            'security_headers': {},
            'response_time_ms': None,
            'timestamp': datetime.now().isoformat()
        }

        start = datetime.now()
        # Jangan minta brotli (br) di request sendiri: kalau library brotli tidak
        # terinstall, aiohttp gagal decode → hasil kosong total. Request-level
        # headers menimpa session headers, jadi ini aman apa pun session-nya.
        try:
            import brotli  # noqa: F401
            _accept_enc = 'gzip, deflate, br'
        except ImportError:
            _accept_enc = 'gzip, deflate'
        try:
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=12),
                allow_redirects=True,
                ssl=False,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                                       'Chrome/124.0.0.0 Safari/537.36',
                         'Accept-Encoding': _accept_enc}
            ) as resp:
                result['status'] = resp.status
                result['final_url'] = str(resp.url)
                result['server_header'] = resp.headers.get('Server')
                result['x_powered_by'] = resp.headers.get('X-Powered-By')

                # Security headers
                h = dict(resp.headers)
                result['security_headers'] = {
                    'hsts': 'Strict-Transport-Security' in h,
                    'csp': 'Content-Security-Policy' in h,
                    'xframe': 'X-Frame-Options' in h,
                    'xcto': 'X-Content-Type-Options' in h,
                }

                if resp.status == 200:
                    raw = await resp.read()
                    html = raw[:800000].decode('utf-8', errors='ignore')
                    self._parse_html(html, result, dict(resp.headers), domain)
        except asyncio.TimeoutError:
            result['error'] = 'Connection timeout'
        except aiohttp.ClientError as e:
            result['error'] = str(e)
        except Exception as e:
            result['error'] = str(e)

        result['response_time_ms'] = int((datetime.now() - start).total_seconds() * 1000)

        sources = ['http']
        if result['social_links']:
            sources.append('social_link_extraction')
        if result['emails']:
            sources.append('email_extraction')
        if result['technologies']:
            sources.append('tech_detection')

        return self.create_result(url, result, sources)

    def _parse_html(self, html: str, result: Dict, headers: dict, domain: str):
        """Parse HTML page and extract footprint data"""
        soup = BeautifulSoup(html, 'html.parser')

        # Title
        if soup.title and soup.title.string:
            result['title'] = soup.title.string.strip()[:200]

        # Meta tags
        for meta in soup.find_all('meta'):
            name = (meta.get('name') or '').lower()
            prop = (meta.get('property') or '').lower()
            content = meta.get('content', '').strip()

            if name == 'description' and not result['description']:
                result['description'] = content[:300]
            elif name == 'keywords' and content:
                result['keywords'] = [k.strip() for k in content.split(',')][:20]
            elif name == 'author' and not result['author']:
                result['author'] = content[:100]
            elif name == 'language' and not result['language']:
                result['language'] = content[:20]
            elif prop == 'og:title' and not result['og_title']:
                result['og_title'] = content[:200]
            elif prop == 'og:image' and not result['og_image']:
                result['og_image'] = content[:300]
            elif 'og:locale' in prop and not result['language']:
                result['language'] = content[:20]

        # Favicon
        icon = soup.find('link', rel=lambda r: r and 'icon' in r.lower())
        if icon and icon.get('href'):
            result['favicon'] = urljoin(result['final_url'] or result['url'], icon['href'])

        # Language from <html lang>
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang') and not result['language']:
            result['language'] = html_tag['lang'][:20]

        # Collect all links
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            links.append(urljoin(result['final_url'] or result['url'], href))

        result['links_count'] = len(links)
        result['external_links_count'] = len(
            [l for l in links if urlparse(l).netloc and urlparse(l).netloc.split(':')[0] != domain]
        )

        # Social links (only links to external social platforms,
        # i.e. hosts different from the scanned site itself)
        seen = set()
        for link in links:
            try:
                host = urlparse(link).netloc.split(':')[0].lower()
                if host.startswith('www.'):
                    host = host[4:]
                # Skip links pointing back to the scanned site itself
                if host == domain or host.endswith('.' + domain):
                    continue
                platform = self.social_patterns.get(host)
                if platform and link not in seen:
                    seen.add(link)
                    result['social_links'].append({
                        'platform': platform,
                        'url': link
                    })
            except Exception:
                continue

        # Emails (mailto + regex)
        emails = set()
        for mailto in soup.find_all('a', href=True):
            href = mailto['href']
            if href.startswith('mailto:'):
                addr = href[7:].split('?')[0].strip()
                if addr and '@' in addr:
                    emails.add(addr)
        text = soup.get_text(' ', strip=True)[:200000]
        for m in re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text):
            if not any(x in m for x in ['.png', '.jpg', '.jpeg', '.gif', '.webp', 'example.com', 'sentry', 'wixpress']):
                emails.add(m.lower())
        result['emails'] = sorted(emails)[:20]

        # Phone numbers
        phones = set()
        for tel in soup.find_all('a', href=True):
            href = tel['href']
            if href.startswith('tel:'):
                num = href[4:].split('?')[0].strip()
                if num:
                    phones.add(num)
        for m in re.findall(r'(\+?[\d][\d\s\-\(\)]{7,15})', text):
            digits = re.sub(r'\D', '', m)
            if 8 <= len(digits) <= 14 and digits not in [d for d in phones]:
                phones.add(m.strip())
        result['phone_numbers'] = sorted(phones)[:10]

        # Tech detection
        combined = (html[:200000] + str(headers)).lower()
        for tech, patterns in self.tech_patterns.items():
            for pattern in patterns:
                if pattern.lower() in combined:
                    if tech not in result['technologies']:
                        result['technologies'].append(tech)
                    break

        result['technologies'] = result['technologies'][:20]
