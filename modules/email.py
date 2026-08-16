#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zqrya v3.0 - Email Module (with real Breach Detection)"""

import re
import asyncio
import hashlib
import dns.asyncresolver
import dns.exception
from typing import Dict, List, Optional
from datetime import datetime
import aiohttp
from modules.base import BaseModule
from sources.breach_db import BreachDB  # Import breach database


# Disposable email domains
DISPOSABLE = {
    'tempmail.com', 'throwaway.com', 'mailinator.com', 'guerrillamail.com',
    'sharklasers.com', 'yopmail.com', '10minutemail.com', 'temp-mail.org',
    'getnada.com', 'trashmail.com', 'maildrop.cc', 'fakeinbox.com',
    'dispostable.com', 'spamgourmet.com', 'mintemail.com', 'mytrashmail.com',
    'spambox.us', 'tempinbox.com', 'wegwerfmail.de', 'mailnull.com'
}

# Free email providers
FREE_PROVIDERS = {
    'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com',
    'protonmail.com', 'proton.me', 'pm.me', 'mail.com', 'yandex.com',
    'icloud.com', 'me.com', 'live.com', 'msn.com', 'gmx.com', 'gmx.net',
    'zoho.com', 'fastmail.com', 'tutanota.com', 'hey.com'
}


class EmailModule(BaseModule):
    def __init__(self, session):
        super().__init__(session)
        self.name = "email"
        self.email_re = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
        self.breach_db = BreachDB()  # Initialize breach database

    async def scan(self, email: str) -> Dict:
        email = email.lower().strip()
        if not self.email_re.match(email):
            return self.error_result(email, "Invalid email format")

        username, domain = email.split('@', 1)
        from core.dns_helper import make_resolver
        resolver = make_resolver()
        resolver.timeout = 5
        resolver.lifetime = 8

        # Real email-specific breach check + historical domain context
        breach_info = await self._build_breach_info(email, domain, username)

        result = {
            'email': email,
            'username': username,
            'domain': domain,
            'valid_format': True,
            'mx_records': [],
            'spf': None,
            'dmarc': None,
            'dkim_hint': None,
            'has_website': False,
            'website_url': None,
            'gravatar': None,
            'gravatar_profile': None,
            'gravatar_hash': hashlib.md5(email.encode()).hexdigest(),
            'disposable': domain in DISPOSABLE,
            'free_provider': domain in FREE_PROVIDERS,
            'possible_usernames': self._gen_usernames(username),
            'breach_info': breach_info,  # Real email-specific breach info
            'breach_risk': breach_info.get('risk_score', 0),  # Risk score from real findings
            'timestamp': datetime.now().isoformat()
        }

        # MX records
        try:
            ans = await resolver.resolve(domain, 'MX')
            result['mx_records'] = sorted(
                [{'exchange': str(r.exchange).rstrip('.'), 'priority': r.preference} for r in ans],
                key=lambda x: x['priority']
            )
        except Exception:
            pass

        # TXT (SPF)
        try:
            ans = await resolver.resolve(domain, 'TXT')
            for rd in ans:
                for s in rd.strings:
                    txt = s.decode() if isinstance(s, bytes) else str(s)
                    if txt.startswith('v=spf1'):
                        result['spf'] = txt[:200]
        except Exception:
            pass

        # DMARC
        try:
            ans = await resolver.resolve(f'_dmarc.{domain}', 'TXT')
            for rd in ans:
                for s in rd.strings:
                    txt = s.decode() if isinstance(s, bytes) else str(s)
                    if txt.startswith('v=DMARC1'):
                        result['dmarc'] = txt[:200]
        except Exception:
            pass

        # DKIM common selector
        for sel in ['google', 'k1', 'mail', 'default', 'dkim', 'selector1']:
            try:
                await resolver.resolve(f'{sel}._domainkey.{domain}', 'TXT')
                result['dkim_hint'] = f'{sel}._domainkey.{domain} exists'
                break
            except Exception:
                pass

        # Website check
        for proto in ('https', 'http'):
            try:
                async with self.session.get(
                    f'{proto}://{domain}', timeout=aiohttp.ClientTimeout(total=4),
                    allow_redirects=True, ssl=False
                ) as r:
                    if r.status < 400:
                        result['has_website'] = True
                        result['website_url'] = str(r.url)
                        break
            except Exception:
                pass

        # Gravatar
        gh = result['gravatar_hash']
        try:
            async with self.session.get(
                f'https://www.gravatar.com/avatar/{gh}?d=404',
                timeout=aiohttp.ClientTimeout(total=4)
            ) as r:
                if r.status == 200:
                    result['gravatar'] = f'https://www.gravatar.com/avatar/{gh}'
                    result['gravatar_profile'] = f'https://www.gravatar.com/{gh}'
        except Exception:
            pass

        # Attribution: who is behind this email? (public, keyless correlation)
        result['attribution'] = await self._attribution(email, username)

        # Registrant domain (untuk email domain custom) via RDAP — gratis tanpa key
        if not result['free_provider'] and not result['disposable']:
            result['domain_registrant'] = await self._domain_registrant_rdap(domain)

        sources = ['dns']
        if result['gravatar']:   sources.append('gravatar')
        if result['mx_records']: sources.append('mx_lookup')
        if result['spf']:        sources.append('spf')
        att = result['attribution']
        if att.get('display_name') or att.get('gravatar_accounts'):
            sources.append('gravatar_profile')
        if att.get('platforms_registered'):
            sources.append('platform_enumeration')
        bi = result['breach_info']
        if bi.get('has_breaches'):
            sources.extend(bi.get('sources_found', []))
        if bi.get('domain_context', {}).get('has_known_breaches'):
            sources.append('breach_history_domain')

        return self.create_result(email, result, sources)

    def _gen_usernames(self, u: str) -> List[str]:
        names = [u]
        if '.' in u:
            names += [u.replace('.', ''), u.replace('.', '_')]
        if '_' in u:
            names.append(u.replace('_', ''))
        for p in ['real', 'the', 'official', 'mr', 'ms']:
            names += [f'{p}{u}', f'{p}_{u}']
        return list(dict.fromkeys(names))[:12]

    # ─────────────────────── ATTRIBUTION (pemilik) ───────────────────────

    async def _attribution(self, email: str, username: str) -> Dict:
        """Correlate public, keyless sources to attribute the email to a likely owner.

        Sources:
        - Gravatar profile JSON (display name, location, linked accounts, phones)
        - Platform registration enumeration (30+ services, holehe-style)

        NOTE: ini korelasi data publik — BUKAN bukti identitas.
        """
        attrib = {
            'display_name': None,
            'preferred_username': None,
            'location': None,
            'about': None,
            'profile_url': None,
            'gravatar_accounts': [],
            'gravatar_emails': [],
            'gravatar_phones': [],
            'platforms_registered': [],
            'platforms_checked': 0,
            'real_name': None,
            'real_name_source': None,
            'github': {},
            'keybase': {},
            'confidence': 'none',
            'evidence': [],
            'name_source': None,
            'note': '',
        }
        try:
            from stalker.modules.gravatar_lookup import lookup_gravatar
            from stalker.modules.email_scanner import scan_email
            from stalker.modules.github_intel import get_profile, search_by_email
            from stalker.modules.identity_lookup import lookup_keybase, lookup_keybase_by_email
        except ImportError:
            return attrib

        gravatar, platform_results, gh_commits, kb_email = await asyncio.gather(
            lookup_gravatar(email),
            scan_email(email),
            search_by_email(email),
            lookup_keybase_by_email(email),
            return_exceptions=True,
        )

        if isinstance(gravatar, dict):
            attrib['display_name'] = gravatar.get('display_name') or None
            attrib['preferred_username'] = gravatar.get('preferred_username') or None
            attrib['location'] = gravatar.get('location') or None
            attrib['about'] = (gravatar.get('about') or '')[:300] or None
            attrib['profile_url'] = gravatar.get('profile_url') or None
            attrib['gravatar_accounts'] = gravatar.get('accounts') or []
            attrib['gravatar_emails'] = gravatar.get('emails') or []
            attrib['gravatar_phones'] = gravatar.get('phone_numbers') or []

        registered = []
        if isinstance(platform_results, list):
            for r in platform_results:
                if isinstance(r, dict) and r.get('registered'):
                    registered.append(r.get('platform'))
        attrib['platforms_registered'] = sorted(set(registered))
        attrib['platforms_checked'] = len(platform_results) if isinstance(platform_results, list) else 0

        if not isinstance(gh_commits, list):
            gh_commits = []
        if not isinstance(kb_email, dict):
            kb_email = {'found': False}

        # GitHub profile dari local-part email (kandidat username)
        gh_profile = {'found': False}
        kb_user = {'found': False}
        for cand in self._gen_usernames(username)[:3]:
            if not gh_profile.get('found'):
                gh_profile = await get_profile(cand)
            if not kb_user.get('found'):
                kb_user = await lookup_keybase(cand)
        if not isinstance(gh_profile, dict):
            gh_profile = {'found': False}
        if not isinstance(kb_user, dict):
            kb_user = {'found': False}

        kb = kb_user if kb_user.get('found') else kb_email
        attrib['github'] = {
            'profile': gh_profile if gh_profile.get('found') else {},
            'commits': gh_commits[:5],
        }
        attrib['keybase'] = kb if kb.get('found') else {}

        # Nama asli terbaik dari sumber terverifikasi
        real_name = None
        real_name_source = None
        if kb.get('full_name'):
            real_name, real_name_source = kb['full_name'], 'keybase'
        elif gh_commits and gh_commits[0].get('author_name'):
            real_name, real_name_source = gh_commits[0]['author_name'], 'github-commit'
        elif gh_profile.get('name'):
            real_name, real_name_source = gh_profile['name'], 'github-profile'
        attrib['real_name'] = real_name
        attrib['real_name_source'] = real_name_source

        # Confidence dari jumlah sinyal TERVERIFIKASI (bukan probabilitas identitas)
        n_plat = len(attrib['platforms_registered'])
        has_name = bool(attrib['display_name'])
        has_accounts = bool(attrib['gravatar_accounts'])
        has_real_name = bool(real_name)

        evidence = []
        if has_name:
            evidence.append('nama profil Gravatar')
        if has_accounts:
            evidence.append(f"{len(attrib['gravatar_accounts'])} akun terhubung (Gravatar)")
        if n_plat:
            evidence.append(f"terdaftar di {n_plat} platform")
        if has_real_name:
            evidence.append(f"nama asli dari {real_name_source}")
        if kb.get('proofs'):
            evidence.append(f"{len(kb['proofs'])} identity proof (Keybase)")
        if gh_commits:
            evidence.append(f"{len(gh_commits)} commit GitHub oleh email ini")
        attrib['evidence'] = evidence
        attrib['name_source'] = 'gravatar' if has_name else None

        strong = has_real_name and (bool(kb.get('proofs')) or bool(gh_commits) or has_accounts)
        if strong or (has_name and (has_accounts or n_plat >= 5)):
            attrib['confidence'] = 'high'
        elif has_real_name or has_name or n_plat >= 3:
            attrib['confidence'] = 'medium'
        elif n_plat > 0 or has_accounts:
            attrib['confidence'] = 'low'

        attrib['note'] = ('Korelasi data publik — BUKAN bukti identitas. '
                          'Nama dari Gravatar/Keybase/GitHub bisa alias/palsu; '
                          'akun/platform hanya menandakan eksistensi.')
        return attrib

    async def _domain_registrant_rdap(self, domain: str) -> Dict:
        """Registrant/administrative entity via RDAP untuk domain custom (gratis, tanpa key)."""
        try:
            async with self.session.get(
                f'https://rdap.org/domain/{domain}',
                timeout=aiohttp.ClientTimeout(total=8),
                headers={'Accept': 'application/rdap+json'},
            ) as r:
                if r.status != 200:
                    return {'has_registrant': False, 'note': f'HTTP {r.status}'}
                d = await r.json(content_type=None)
                entities = []
                for ent in d.get('entities', []):
                    roles = ent.get('roles', [])
                    if 'registrant' not in roles and 'administrative' not in roles:
                        continue
                    fields = {}
                    for f in ent.get('vcardArray', [None, []])[1] or []:
                        if isinstance(f, list) and len(f) >= 4 and isinstance(f[0], str):
                            fields[f[0]] = f[3]
                    entities.append({
                        'roles': roles,
                        'handle': ent.get('handle'),
                        'name': fields.get('fn'),
                        'org': fields.get('org'),
                        'email': fields.get('email'),
                        'address': fields.get('adr'),
                    })
                return {'has_registrant': bool(entities), 'entities': entities[:3]}
        except Exception:
            return {'has_registrant': False, 'note': 'lookup gagal'}
        return {'has_registrant': False, 'note': 'no data'}

    # ─────────────────────── BREACH DETECTION ───────────────────────

    def _domain_breach_context(self, domain: str) -> Dict:
        """Historical breach context for the DOMAIN — NOT specific to this email.

        Kept separate from the live email-specific results so it is never
        mistaken for "this address was breached".
        """
        domain_breaches = self.breach_db.search_by_domain(domain)

        domain_aliases = {
            'gmail.com': 'Google',
            'google.com': 'Google',
            'yahoo.com': 'Yahoo',
            'ymail.com': 'Yahoo',
            'hotmail.com': 'Microsoft',
            'outlook.com': 'Microsoft',
            'live.com': 'Microsoft',
            'msn.com': 'Microsoft',
            'facebook.com': 'Facebook',
            'twitter.com': 'Twitter',
            'linkedin.com': 'LinkedIn',
            'tumblr.com': 'Tumblr',
            'dropbox.com': 'Dropbox',
            'canva.com': 'Canva',
            'tokopedia.com': 'Tokopedia',
            'jd.id': 'JD.ID',
            'bhinneka.com': 'Bhinneka',
        }

        alias = domain_aliases.get(domain)
        alias_breaches = self.breach_db.search_by_domain(alias) if alias else []

        all_breaches = domain_breaches + alias_breaches
        unique_breaches = {b['name']: b for b in all_breaches}.values()

        breach_list = []
        total_records = 0
        for breach in unique_breaches:
            records = breach.get('records', 0)
            total_records += records
            if records > 100_000_000:
                risk = 'critical'
            elif records > 10_000_000:
                risk = 'high'
            elif records > 1_000_000:
                risk = 'medium'
            else:
                risk = 'low'
            breach_list.append({
                'name': breach.get('name'),
                'year': breach.get('year'),
                'records': records,
                'risk': risk,
                'description': breach.get('description', ''),
                'data_types': breach.get('data_types', []),
                'country': breach.get('country'),
            })

        breach_list.sort(key=lambda x: x['year'], reverse=True)

        return {
            'has_known_breaches': len(breach_list) > 0,
            'breaches': breach_list[:5],
            'total_breaches': len(breach_list),
            'total_records_exposed': total_records,
            'note': 'Riwayat breach DOMAIN — bukan khusus alamat email ini',
        }

    async def _check_email_breaches_live(self, email: str) -> Dict:
        """Real email-specific breach lookups via keyless public sources.

        Sources: GhostProject, LeakCheck (public), BreachDirectory, Hudson Rock.
        """
        result = {
            'sources_checked': 0,
            'sources_found': [],
            'total_records': 0,
            'hudson_rock_infections': 0,
            'hudson_rock': [],
            'details': {},
        }
        try:
            from stalker.modules.dark_web_checker import (
                check_ghostproject, check_leakcheck_free, check_breachdirectory,
                check_intelx_free, check_psbdmp, check_xposedornot,
            )
            from stalker.modules.breach_check import check_hudson_rock
        except ImportError:
            return result

        ghost, leak, breachdir, intelx, psbdmp, xon, hr = await asyncio.gather(
            check_ghostproject(email),
            check_leakcheck_free(email),
            check_breachdirectory(email),
            check_intelx_free(email),
            check_psbdmp(email),
            check_xposedornot(email),
            check_hudson_rock(email=email),
            return_exceptions=True,
        )

        for name, r in (('ghostproject', ghost),
                        ('leakcheck', leak),
                        ('breachdirectory', breachdir),
                        ('intelx', intelx),
                        ('psbdmp', psbdmp),
                        ('xposedornot', xon)):
            if isinstance(r, dict):
                result['sources_checked'] += 1
                result['details'][name] = r
                if r.get('found'):
                    result['sources_found'].append(name)
                    result['total_records'] += r.get('count', 0)

        if isinstance(hr, dict):
            hr_email = hr.get('email', {})
            result['hudson_rock_infections'] = hr_email.get('total_infections', 0)
            result['hudson_rock'] = hr_email.get('infections', [])[:10]

        return result

    async def _build_breach_info(self, email: str, domain: str, username: str) -> Dict:
        """Combine real email-specific results with historical domain context."""
        domain_context = self._domain_breach_context(domain)
        live = await self._check_email_breaches_live(email)

        sources_found = live.get('sources_found', [])
        infections = live.get('hudson_rock_infections', 0)
        has_breaches = bool(sources_found) or infections > 0

        # Evidence = temuan faktual yang bisa diverifikasi (bukan tebakan)
        evidence = []
        for name in sources_found:
            rec = live.get('details', {}).get(name, {}).get('count')
            evidence.append(f"{name}: ditemukan" + (f" ({rec} record)" if rec else ""))
        if infections:
            evidence.append(f"Hudson Rock: {infections} infeksi infostealer")

        # Skor = fungsi deterministik dari temuan terverifikasi (bukan probabilitas nyata)
        risk_score = 0
        if sources_found:
            risk_score += 40 + min(len(sources_found) - 1, 3) * 10
        if infections > 0:
            risk_score += 45
        risk_score = min(risk_score, 100)

        if infections > 0:
            risk_level = 'critical'
        elif len(sources_found) >= 2:
            risk_level = 'high'
        elif len(sources_found) == 1:
            risk_level = 'medium'
        else:
            risk_level = 'none'

        if has_breaches:
            parts = []
            if sources_found:
                parts.append(f"ditemukan di {', '.join(sources_found)}")
            if infections:
                parts.append(f"{infections} infeksi infostealer (Hudson Rock)")
            message = '⚠️ Email ini ditemukan dalam data breach: ' + '; '.join(parts)
        else:
            message = '✓ Tidak ditemukan dalam sumber breach publik yang diperiksa'

        return {
            'has_breaches': has_breaches,
            'sources_checked': live['sources_checked'] + 1,  # +1 Hudson Rock
            'sources_found': sources_found,
            'total_records': live['total_records'],
            'hudson_rock_infections': infections,
            'hudson_rock': live['hudson_rock'],
            'risk_level': risk_level,
            'risk_score': risk_score,
            'message': message,
            'recommendation': self._get_recommendation(risk_level, infections > 0),
            'evidence': evidence,
            'note': (f"Skor dihitung dari {len(evidence)} temuan terverifikasi "
                     f"({len(sources_found)} sumber breach, {infections} infeksi). "
                     f"0 = 'tidak ditemukan di sumber yang dicek', bukan jaminan aman."),
            'domain_context': domain_context,
            # Back-compat: list of (historical domain) breaches for downstream renderers
            'breaches': domain_context['breaches'],
            'total_breaches': domain_context['total_breaches'],
        }

    def _get_recommendation(self, risk_level: str, infected: bool = False) -> str:
        """Security recommendation based on real findings."""
        if infected:
            return ("URGENT: Perangkat/akun yang terkait email ini pernah terekspos infostealer. "
                    "Ganti password SEMUA akun, aktifkan 2FA, dan scan perangkat dari malware.")
        if risk_level == 'critical':
            return "IMMEDIATE ACTION: Ganti password, aktifkan 2FA, dan pantau akun dari aktivitas mencurigakan."
        if risk_level == 'high':
            return "URGENT: Ganti password untuk layanan ini dan akun lain yang memakai password sama. Aktifkan 2FA."
        if risk_level == 'medium':
            return "Email muncul di sumber breach publik. Gunakan password manager dengan password unik dan aktifkan 2FA."
        return "Tidak ditemukan breach spesifik untuk email ini di sumber publik yang diperiksa."
