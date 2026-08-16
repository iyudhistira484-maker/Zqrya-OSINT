#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zqrya v3.0 - IP Module (upgraded)"""

import socket
import ipaddress
import asyncio
from typing import Dict, Optional
from datetime import datetime
import aiohttp
from modules.base import BaseModule
from modules.geoip_consensus import geolocate


class IPModule(BaseModule):
    def __init__(self, session):
        super().__init__(session)
        self.name = "ip"

        # RDAP servers for all RIRs
        self.rdap_servers = [
            'https://rdap.arin.net/registry/ip/{}',      # North America
            'https://rdap.db.ripe.net/ip/{}',            # Europe, Middle East, Central Asia
            'https://rdap.apnic.net/ip/{}',              # Asia Pacific
            'https://rdap.lacnic.net/rdap/ip/{}',        # Latin America
            'https://rdap.afrinic.net/rdap/ip/{}',       # Africa
        ]

        # Simple cache untuk mengurangi request duplikat
        self._cache = {}
        self._cache_ttl = 3600  # 1 hour cache

    async def scan(self, target: str) -> Dict:
        ip = target.strip()

        # Check cache
        cache_key = f"ip_{ip}"
        if cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self._cache_ttl:
                return cached_result

        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            try:
                ip = socket.gethostbyname(target.strip())
                ip_obj = ipaddress.ip_address(ip)
            except Exception:
                return self.error_result(target, "Invalid IP or hostname")

        result = {
            'ip': ip,
            'input': target,
            'version': ip_obj.version,
            'is_private': ip_obj.is_private,
            'is_loopback': ip_obj.is_loopback,
            'is_multicast': ip_obj.is_multicast,
            'is_global': ip_obj.is_global,
            'is_reserved': ip_obj.is_reserved,
            'reverse_dns': None,
            'country': None, 'country_code': None,
            'region': None, 'city': None, 'zip': None,
            'lat': None, 'lon': None,
            'timezone': None,
            'isp': None, 'org': None,
            'asn': None, 'asn_name': None,
            'is_mobile': False,
            'is_proxy': False,
            'is_hosting': False,
            'is_crawler': False,
            'is_tor': False,
            'rdap': {},
            'abuse_contact': None,
            'shodan': {},
            'risk_score': None,  # skor deterministik dari sinyal terverifikasi
            'risk_factors': [],
            'risk_note': '',
            'timestamp': datetime.now().isoformat()
        }

        # Reverse DNS
        try:
            result['reverse_dns'] = socket.gethostbyaddr(ip)[0]
        except Exception:
            pass

        if not ip_obj.is_private and not ip_obj.is_loopback and not ip_obj.is_reserved:
            geo, rdap, shodan = await asyncio.gather(
                self._geolocate(ip),
                self._rdap(ip),
                self._shodan(ip)
            )
            if geo:
                result.update(geo)
            if rdap:
                result['rdap'] = rdap
                if rdap.get('abuse_email'):
                    result['abuse_contact'] = rdap['abuse_email']
            if shodan:
                result['shodan'] = shodan

            # Lokasi TERDAFTAR ISP/ASN dari RDAP autnum (verifiable, bukan GeoIP).
            # Berguna untuk ISP regional kecil yang alokasinya tak tercatat sampai
            # kota di GeoIP (mis. ISP Gresik sering ditebak "Surabaya").
            asn = result.get('asn') or (result.get('rdap') or {}).get('asn')
            if asn:
                isp_loc = await self._rdap_asn(asn)
                if isp_loc:
                    result['isp_registered'] = isp_loc

            # Hitung skor dari sinyal nyata (Shodan terverifikasi + flag perkiraan)
            result['risk_score'], result['risk_factors'], result['risk_note'] = self._calculate_risk_score(result)
        else:
            result['note'] = 'Private/loopback/reserved IP — limited data available'

        sources = ['reverse_dns']
        if result.get('country'):
            sources.append('ip-api.com')
        if result.get('rdap'):
            sources.append('rdap')
        if result.get('shodan'):
            sources.append('shodan-internetdb')

        final_result = self.create_result(ip, result, sources)

        # Cache result
        self._cache[cache_key] = (datetime.now(), final_result)

        return final_result

    async def _geolocate(self, ip: str) -> Optional[Dict]:
        """Geolokasi gabungan (shared core) — lihat modules/geoip_consensus.py."""
        return await geolocate(ip, self._fetch_json)

    async def _fetch_json(self, url: str):
        """Ambil JSON dari URL (aiohttp) — dipakai shared geolocate()."""
        try:
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=6),
            ) as r:
                if r.status != 200:
                    return None
                return await r.json(content_type=None)
        except Exception:
            return None

    async def _rdap(self, ip: str) -> Dict:
        """RDAP lookup with multiple RIR servers"""
        for url_tpl in self.rdap_servers:
            try:
                async with self.session.get(
                    url_tpl.format(ip),
                    timeout=aiohttp.ClientTimeout(total=5),
                    headers={'Accept': 'application/rdap+json'}
                ) as r:
                    if r.status == 200:
                        d = await r.json(content_type=None)
                        info = {}
                        info['rir'] = url_tpl.split('/')[2].split('.')[0].upper()
                        info['handle'] = d.get('handle')
                        info['network'] = d.get('name')
                        info['type'] = d.get('type')
                        info['start_address'] = d.get('startAddress')
                        info['end_address'] = d.get('endAddress')
                        info['ip_version'] = d.get('ipVersion')

                        # Extract organization and abuse contact from entities
                        for ent in d.get('entities', []):
                            roles = ent.get('roles', [])
                            vcard = ent.get('vcardArray', [None, []])[1]
                            for field in vcard:
                                if not isinstance(field, list):
                                    continue
                                if field[0] == 'fn' and 'organization' not in info:
                                    if any(r in roles for r in ['registrant', 'administrative', 'technical']):
                                        info['organization'] = field[3]
                                if field[0] == 'email':
                                    if 'abuse' in roles:
                                        info['abuse_email'] = field[3]
                                    elif 'administrative' in roles and 'abuse_email' not in info:
                                        info['admin_email'] = field[3]
                                if field[0] == 'tel' and 'abuse' in roles:
                                    info['abuse_phone'] = field[3]

                        # Events
                        for ev in d.get('events', []):
                            action = ev.get('eventAction')
                            date = ev.get('eventDate', '')[:10]
                            if action == 'registration':
                                info['registered'] = date
                            elif action == 'last changed':
                                info['last_changed'] = date
                            elif action == 'expiration':
                                info['expires'] = date

                        # Remarks/notices
                        if d.get('remarks'):
                            info['remarks'] = d.get('remarks')[0].get('description', [''])[0][:200]

                        return info
            except Exception:
                continue
        return {}

    async def _rdap_asn(self, asn: str) -> Dict:
        """Lokasi TERDAFTAR ISP/ASN dari RDAP autnum — verifiable, bukan GeoIP.

        Ini lokasi kantor/registrasi ISP, BUKAN lokasi fisik si IP. Berguna untuk
        ISP kecil/regional yang alokasinya tidak tercatat sampai kota di GeoIP.
        """
        asn_num = str(asn or '').replace('AS', '').replace('as', '').strip()
        if not asn_num.isdigit():
            return {}
        for url_tpl in ('https://rdap.apnic.net/autnum/{}', 'https://rdap.db.ripe.net/autnum/{}'):
            try:
                async with self.session.get(
                    url_tpl.format(asn_num),
                    timeout=aiohttp.ClientTimeout(total=5),
                    headers={'Accept': 'application/rdap+json'},
                ) as r:
                    if r.status != 200:
                        continue
                    d = await r.json(content_type=None)
                    name = d.get('name') or ''
                    blob = name
                    for rem in d.get('remarks', []):
                        blob += '\n' + '\n'.join(rem.get('description', []))
                    for e in d.get('entities', []):
                        vc = e.get('vcardArray', [None, []])[1]
                        for f in vc:
                            if isinstance(f, list) and f[0] == 'adr':
                                addr = [x for x in f[1:] if isinstance(x, str) and x.strip()]
                                if addr:
                                    blob += '\n' + ', '.join(addr)
                    city, region = self._parse_id_address(blob)
                    info = {'asn': f'AS{asn_num}', 'name': name}
                    if city:
                        info['city'] = city
                    if region:
                        info['region'] = region
                    return info
            except Exception:
                continue
        return {}

    @staticmethod
    def _parse_id_address(text: str):
        """Ekstrak (kota/kabupaten, provinsi) dari alamat berformat Indonesia."""
        import re
        text = text or ''
        city = None
        region = None
        m = re.search(r'(?:Kab\.?|Kabupaten|Kota)\s+([A-Za-z][A-Za-z\.\']+)', text)
        if m:
            city = m.group(1).strip(' .')
        for prov in ['Jawa Timur', 'Jawa Barat', 'Jawa Tengah', 'DKI Jakarta', 'Jakarta',
                     'Banten', 'DI Yogyakarta', 'Yogyakarta', 'Bali', 'Sumatera Utara',
                     'Sumatera Selatan', 'Sumatera Barat', 'Riau', 'Kepulauan Riau',
                     'Kalimantan Timur', 'Kalimantan Barat', 'Kalimantan Selatan', 'Kalimantan Tengah',
                     'Kalimantan Utara', 'Sulawesi Selatan', 'Sulawesi Utara', 'Sulawesi Tengah',
                     'Sulawesi Tenggara', 'Sulawesi Barat', 'Gorontalo', 'Maluku', 'Maluku Utara',
                     'Papua', 'Nusa Tenggara Timur', 'Nusa Tenggara Barat', 'Lampung', 'Bengkulu',
                     'Jambi', 'Aceh', 'Bangka Belitung']:
            if prov in text:
                region = prov
                break
        return city, region

    async def _shodan(self, ip: str) -> Dict:
        """Shodan InternetDB (free, no key): open ports, CVEs, tags, hostnames."""
        try:
            async with self.session.get(
                f'https://internetdb.shodan.io/{ip}',
                timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                if r.status == 200:
                    d = await r.json(content_type=None)
                    return {
                        'open_ports': d.get('ports', []),
                        'hostnames': d.get('hostnames', []),
                        'tags': d.get('tags', []),
                        'vulns': d.get('vulns', []),
                        'cpes': d.get('cpes', []),
                    }
                return {'note': f'HTTP {r.status}'}
        except Exception:
            return {}
        return {}

    def _calculate_risk_score(self, data: Dict):
        """Score from verifiable signals, with honest labeling.

        - verified: Shodan InternetDB scan data (tags, CVEs) — hasil scan nyata.
        - heuristic: flag ip-api (proxy/hosting) — perkiraan, bisa false positive.

        Returns (score, factors, note).
        """
        verified = []
        heuristic = []

        shodan = data.get('shodan') or {}
        tags = {str(t).lower() for t in shodan.get('tags', [])}
        risk_tags = {
            'vpn', 'tor', 'proxy', 'compromised', 'botnet', 'malware',
            'spam', 'honeypot', 'scanner', 'mining', 'c2', 'self-signed',
        }
        for tag in sorted(risk_tags & tags):
            verified.append(f'Shodan tag "{tag}" (hasil scan)')

        vulns = shodan.get('vulns', [])
        if vulns:
            verified.append(f'{len(vulns)} CVE terdeteksi (Shodan)')

        if data.get('is_proxy'):
            heuristic.append('flag proxy/VPN (ip-api — perkiraan)')
        if data.get('is_hosting'):
            heuristic.append('flag datacenter/hosting (ip-api — perkiraan)')

        score = min(100, len(verified) * 25 + len(heuristic) * 10)
        factors = verified + heuristic
        if not factors:
            factors.append('tidak ada sinyal risiko yang terdeteksi')

        note = (f"Skor dihitung dari {len(verified)} sinyal terverifikasi "
                f"+ {len(heuristic)} indikator perkiraan. Bukan probabilitas serangan.")
        return score, factors, note

    async def bulk_lookup(self, ips: list) -> Dict[str, Dict]:
        """Bulk IP lookup (for multiple IPs)"""
        results = {}
        tasks = [self.scan(ip) for ip in ips]
        scan_results = await asyncio.gather(*tasks, return_exceptions=True)

        for ip, result in zip(ips, scan_results):
            if isinstance(result, dict) and not result.get('error'):
                results[ip] = result
            else:
                results[ip] = {'error': str(result) if result else 'Lookup failed'}

        return results

    def clear_cache(self):
        """Clear the IP lookup cache"""
        self._cache.clear()
