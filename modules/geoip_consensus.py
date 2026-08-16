#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inti geolokasi IP yang dipakai bersama (single source of truth).

Dipanggil oleh `modules/ip.py` (engine utama, aiohttp) DAN `stalker/modules/*`
(httpx) supaya logika geolokasi tidak diduplikasi.

Alur: 3 DB GeoIP lokal (offline) + 5 API online -> resolve nama desa/kecamatan
menjadi kabupaten/kota (dataset wilayah Indonesia) -> majority vote gabungan
dengan confidence jujur.

`geolocate(ip, get_json)` menerima callable async `get_json(url) -> dict|None`
sehingga tidak tergantung library HTTP tertentu (aiohttp/httpx).
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Awaitable, Callable, Dict, List, Optional

from modules.geoip_local import LocalGeoIP
from modules.indonesia_regions import IndonesiaRegions

GEO_APIS = [
    ('ip-api', "http://ip-api.com/json/{}?fields=status,message,country,countryCode,region,regionName,city,district,zip,lat,lon,timezone,isp,org,as,asname,mobile,proxy,hosting,query"),
    ('ipapi.co', "https://ipapi.co/{}/json/"),
    ('ipinfo.io', "https://ipinfo.io/{}/json"),
    ('ipwho.is', "https://ipwho.is/{}"),
    ('freeipapi', "https://freeipapi.com/api/json/{}"),
]

_local: Optional[LocalGeoIP] = None
_resolver: Optional[IndonesiaRegions] = None


def _get_local() -> LocalGeoIP:
    global _local
    if _local is None:
        _local = LocalGeoIP()
    return _local


def _get_resolver() -> IndonesiaRegions:
    global _resolver
    if _resolver is None:
        _resolver = IndonesiaRegions()
    return _resolver


def normalize_geo(name: str, d: dict) -> Optional[Dict]:
    """Normalisasi respons berbagai API geo ke skema umum."""
    try:
        if name == 'ip-api':
            if d.get('status') != 'success':
                return None
            return {
                'source': name, 'country': d.get('country'), 'country_code': d.get('countryCode'),
                'region': d.get('regionName'), 'city': d.get('city'), 'zip': d.get('zip'),
                'lat': d.get('lat'), 'lon': d.get('lon'), 'timezone': d.get('timezone'),
                'isp': d.get('isp'), 'org': d.get('org'),
                'asn': d.get('as', '').split()[0] if d.get('as') else None,
                'asn_name': d.get('asname'),
                'is_mobile': d.get('mobile', False), 'is_proxy': d.get('proxy', False),
                'is_hosting': d.get('hosting', False),
            }
        if name == 'ipapi.co':
            if d.get('error'):
                return None
            return {
                'source': name, 'country': d.get('country_name'), 'country_code': d.get('country_code'),
                'region': d.get('region'), 'city': d.get('city'), 'zip': d.get('postal'),
                'lat': d.get('latitude'), 'lon': d.get('longitude'), 'timezone': d.get('timezone'),
                'isp': d.get('org'), 'org': d.get('org'), 'asn': d.get('asn'), 'asn_name': None,
                'is_mobile': d.get('mobile', False), 'is_proxy': d.get('proxy', False),
                'is_hosting': d.get('hosting', False),
            }
        if name == 'ipinfo.io':
            if not d.get('country'):
                return None
            asn = None
            asn_name = None
            org = d.get('org', '')
            if org and org.startswith('AS'):
                parts = org.split(' ', 1)
                asn = parts[0]
                if len(parts) > 1:
                    asn_name = parts[1]
            loc = (d.get('loc') or '0,0').split(',')
            return {
                'source': name, 'country': d.get('country'), 'country_code': d.get('country'),
                'region': d.get('region'), 'city': d.get('city'), 'zip': d.get('postal'),
                'lat': float(loc[0]) if loc and loc[0] else None,
                'lon': float(loc[1]) if len(loc) > 1 and loc[1] else None,
                'timezone': d.get('timezone'), 'isp': d.get('org'), 'org': d.get('org'),
                'asn': asn, 'asn_name': asn_name,
                'is_mobile': False, 'is_proxy': False, 'is_hosting': False,
            }
        if name == 'ipwho.is':
            if not d.get('success'):
                return None
            conn = d.get('connection') or {}
            tz = d.get('timezone') or {}
            return {
                'source': name, 'country': d.get('country'), 'country_code': d.get('country_code'),
                'region': d.get('region'), 'city': d.get('city'), 'zip': d.get('postal'),
                'lat': d.get('latitude'), 'lon': d.get('longitude'),
                'timezone': tz.get('id') if isinstance(tz, dict) else None,
                'isp': conn.get('isp'), 'org': conn.get('org'), 'asn': conn.get('asn'),
                'asn_name': conn.get('org'),
                'is_mobile': conn.get('domain') == 'mobile', 'is_proxy': False, 'is_hosting': False,
            }
        if name == 'freeipapi':
            if not d.get('countryCode'):
                return None
            return {
                'source': name, 'country': d.get('countryName'), 'country_code': d.get('countryCode'),
                'region': d.get('regionName'), 'city': d.get('cityName'), 'zip': d.get('zipCode'),
                'lat': d.get('latitude'), 'lon': d.get('longitude'),
                'timezone': d.get('timeZone'), 'isp': None, 'org': None, 'asn': None, 'asn_name': None,
                'is_mobile': False, 'is_proxy': False, 'is_hosting': False,
            }
    except Exception:
        return None
    return None


def geo_consensus(results: List[Dict]) -> Dict:
    """Konsensus gabungan: majority vote negara & kota + confidence jujur.

    Suara 'specific' (nama desa/kecamatan yang di-resolve ke kabupaten) lebih
    presisi daripada tebakan kota besar, jadi diprioritaskan untuk memilih KOTA
    — tapi hanya bila didukung >=2 sumber yang sepakat ke satu kabupaten,
    supaya satu sumber doang tidak bisa menimpa suara mayoritas.
    """
    specific = [r for r in results if (r.get('_resolved') or {}).get('specific')]
    city_pool = results
    used_specific = False
    if len(specific) >= 2:
        spec_cities = {r.get('city') for r in specific if r.get('city') not in (None, '', 'Unknown')}
        if len(spec_cities) == 1:
            city_pool = specific
            used_specific = True

    def vote(pool, key):
        vals = [r.get(key) for r in pool if r.get(key) not in (None, '', 'Unknown')]
        if not vals:
            return None
        return Counter(vals).most_common(1)[0][0]

    country_code = vote(results, 'country_code')
    country = vote(results, 'country')
    city = vote(city_pool, 'city')
    region = vote(city_pool, 'region')

    codes = [r.get('country_code') for r in results if r.get('country_code')]
    country_agree = codes.count(country_code) if country_code else 0
    country_disagree = len(set(codes)) > 1

    cities = [r.get('city') for r in city_pool if r.get('city') not in (None, '', 'Unknown')]
    city_agree = cities.count(city) if city else 0
    city_disagree = len(set(cities)) > 1

    total = len(results)
    n_specific = len(specific)
    if city:
        if used_specific:
            confidence = 'high' if city_agree >= 2 else 'medium'
        elif city_agree >= 3 and city_agree >= len(cities) * 0.7:
            confidence = 'high'
        elif city_agree >= 2:
            confidence = 'medium'
        else:
            confidence = 'low'
    else:
        confidence = 'high' if country_agree == total else ('medium' if country_agree >= 2 else 'low')

    def pick_agreeing(key):
        for r in city_pool:
            if r.get('city') == city and r.get(key) not in (None, '', 'Unknown'):
                return r.get(key)
        for r in results:
            if r.get('country_code') == country_code and r.get(key) not in (None, '', 'Unknown'):
                return r.get(key)
        for r in results:
            if r.get(key) not in (None, '', 'Unknown'):
                return r.get(key)
        return None

    return {
        'country': country,
        'country_code': country_code,
        'region': region,
        'city': city,
        'zip': pick_agreeing('zip'),
        'lat': pick_agreeing('lat'),
        'lon': pick_agreeing('lon'),
        'timezone': pick_agreeing('timezone'),
        'isp': pick_agreeing('isp'),
        'org': pick_agreeing('org'),
        'asn': pick_agreeing('asn'),
        'asn_name': pick_agreeing('asn_name'),
        'is_mobile': any(r.get('is_mobile') for r in results),
        'is_proxy': any(r.get('is_proxy') for r in results),
        'is_hosting': any(r.get('is_hosting') for r in results),
        'geo_sources': [r.get('source') for r in results if r.get('source')],
        'geo_confidence': confidence,
        'geo_agreement': city_agree if city else country_agree,
        'geo_disagreement': city_disagree or country_disagree,
        'geo_specific': n_specific,
        'geo_used_specific': used_specific,
    }


async def geolocate(ip: str, get_json: Callable[[str], Awaitable[Optional[dict]]]) -> Optional[Dict]:
    """Geolokasi gabungan: DB lokal + API online + resolver + consensus.

    `get_json(url)`: async callable yang mengembalikan dict JSON (atau None
    bila gagal/non-200). Abstraksi ini membuat fungsi dipakai aiohttp & httpx.
    """
    local_votes = _get_local().lookup_all(ip) if _get_local().available else []

    for d in local_votes:
        d['source'] = 'local:' + d.pop('_db', 'db')
        d.setdefault('is_mobile', False)
        d.setdefault('is_proxy', False)
        d.setdefault('is_hosting', False)

    async def fetch_one(name: str, url_tpl: str):
        try:
            d = await get_json(url_tpl.format(ip))
            return normalize_geo(name, d) if d else None
        except Exception:
            return None

    online = await asyncio.gather(
        *[fetch_one(n, u) for n, u in GEO_APIS],
        return_exceptions=True,
    )
    online = [r for r in online if isinstance(r, dict) and r.get('country_code')]

    all_votes = local_votes + online
    if not all_votes:
        return None

    # Koreksi kota: nama desa/kecamatan -> kabupaten/kota (resolver wilayah ID).
    resolver = _get_resolver()
    if resolver.available:
        for v in all_votes:
            c = v.get('city')
            if c and c not in (None, '', 'Unknown'):
                r = resolver.resolve(c, lat=v.get('lat'), lon=v.get('lon'))
                if r:
                    v['_original_city'] = c
                    v['_resolved'] = r
                    v['city'] = r['city']

    unified = geo_consensus(all_votes)

    n_local = len(local_votes)
    n_online = len(online)
    agree = unified.get('geo_agreement', 0)
    total = len(all_votes)
    resolved_specific = [v for v in all_votes if (v.get('_resolved') or {}).get('specific')]
    if unified.get('geo_used_specific'):
        seen = set()
        parts = []
        for v in resolved_specific:
            key = (v.get('_original_city'), v['_resolved']['city'])
            if key not in seen:
                seen.add(key)
                parts.append(f"{v.get('_original_city')}→{v['_resolved']['city']}")
        unified['geo_note'] = f"kota dari nama tempat presisi: {', '.join(parts)}"
    elif unified.get('geo_disagreement'):
        cities = [r.get('city') for r in all_votes if r.get('city') not in (None, '', 'Unknown')]
        distinct = list(dict.fromkeys(cities))
        unified['geo_note'] = (
            f"{agree}/{total} sumber setuju kota \"{unified.get('city')}\" "
            f"— {len(distinct)} kota berbeda: {', '.join(distinct)}"
        )
    else:
        unified['geo_note'] = (
            f"{agree}/{total} sumber sepakat ({n_local} DB lokal + {n_online} API online)"
        )
    unified['geo_local_cities'] = list(dict.fromkeys(
        r.get('city') for r in local_votes if r.get('city') not in (None, '', 'Unknown')
    ))
    return unified
