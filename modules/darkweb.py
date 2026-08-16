#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zqrya v3.0 - Dark Web & Breach Checker

Bridges Zqrya to the deep pipeline's dark web checker:
- GhostProject (email breach DB)
- Psbdmp (pastebin dumps)
- BreachDirectory
- LeakCheck
- IntelX
- Hudson Rock (infostealer infections)
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
from modules.base import BaseModule


class DarkWebModule(BaseModule):
    """Dark web / paste / breach intelligence (new in v3.0 merge)"""

    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        self.name = "darkweb"

    async def scan(self, target: str, target_type: str = "email") -> Dict:
        """Run dark web checks on email/username/phone"""
        target = target.strip()
        if not target:
            return self.error_result(target, "Empty target")

        try:
            from stalker.modules.dark_web_checker import full_darkweb_check
        except ImportError as e:
            return self.error_result(target, f"Dark web checker unavailable: {e}")

        # Auto-detect type if not given
        qtype = target_type
        if qtype == 'auto':
            if '@' in target and '.' in target.split('@')[-1]:
                qtype = 'email'
            elif target.replace('+', '').replace('-', '').replace(' ', '').isdigit() and len(target) >= 7:
                qtype = 'phone'
            else:
                qtype = 'username'

        try:
            results = await full_darkweb_check(target, qtype)
        except Exception as e:
            return self.error_result(target, str(e))

        # Summarize
        from stalker.modules.dark_web_checker import summary as dw_summary
        s = dw_summary(results)

        # Hudson Rock breach check (email + username)
        hr = {}
        try:
            from stalker.modules.breach_check import check_hudson_rock
            if qtype == 'email':
                hr = await check_hudson_rock(email=target)
            else:
                hr = await check_hudson_rock(username=target)
        except Exception:
            hr = {}

        data = {
            'query': target,
            'query_type': qtype,
            'sources_checked': s['sources_checked'],
            'sources_found': s['sources_found'],
            'total_records': s['total_records'],
            'found_in': s['found_in'],
            'results': self._make_serializable(results),
            'hudson_rock': self._make_serializable(hr),
            'breach_count': hr.get('email', {}).get('total_infections', 0) or
                            hr.get('username', {}).get('total_infections', 0),
            'timestamp': datetime.now().isoformat()
        }
        return self.create_result(target, data, list(results.keys()))

    def _make_serializable(self, obj):
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(i) for i in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        return str(obj)
