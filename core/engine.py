#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zqrya v3.0 - Main Engine"""

import asyncio
import aiohttp
import socket
from datetime import datetime
from typing import Dict, List, Optional, Any
from rich.table import Table
from rich.tree import Tree
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from core.banner import console
from core.detector import detector, Entity
from core.correlation import CorrelationEngine
from modules.username import UsernameModule
from modules.email import EmailModule
from modules.phone import PhoneModule
from modules.domain import DomainModule
from modules.ip import IPModule
from modules.url import URLModule
from modules.maigret import MaigretModule
from modules.darkweb import DarkWebModule


class ZqryaEngine:
    """Main OSINT investigation engine"""

    def __init__(self, timeout: int = 12, max_concurrent: int = 25):
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.session = None
        self.results = {}
        self.correlation = CorrelationEngine()
        self.modules = {}

    async def __aenter__(self):
        # Gunakan DNS resolver manual dengan nameserver Google
        resolver = aiohttp.resolver.AsyncResolver(
            nameservers=['8.8.8.8', '1.1.1.1', '8.8.4.4']
        )

        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            ssl=False,
            force_close=True,
            enable_cleanup_closed=True,
            resolver=resolver,
            ttl_dns_cache=300
        )

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )

        self.modules = {
            'username': UsernameModule(self.session),
            'email': EmailModule(self.session),
            'phone': PhoneModule(self.session),
            'domain': DomainModule(self.session),
            'ip': IPModule(self.session),
            'url': URLModule(self.session),
            'maigret': MaigretModule(self.session),
            'darkweb': DarkWebModule(self.session),
        }
        return self

    async def __aexit__(self, *args):
        if self.session and not self.session.closed:
            await self.session.close()

    async def investigate(self, target: str, target_type: str = None) -> Dict:
        """Single-module investigation"""
        if not target_type or target_type == 'auto':
            entity = detector.detect(target)
            target_type = entity.type
            target = entity.normalized

        console.print(f"[cyan]🔍 Investigating: [bold]{target}[/bold] "
                      f"([yellow]{target_type.upper()}[/yellow])[/cyan]")

        module = self.modules.get(target_type)
        if not module:
            console.print(f"[red]❌ No module for type: {target_type}[/red]")
            return {}

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True, console=console
            ) as progress:
                progress.add_task(description=f"Running {target_type} scan…", total=None)
                result = await module.scan(target)
            if result and not result.get('error'):
                self.results[target_type] = result
                return result
            elif result and result.get('error'):
                console.print(f"[red]❌ {result['error']}[/red]")
                return result
            else:
                console.print("[red]❌ No results[/red]")
                return {}
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            return {}

    async def investigate_all(self, target: str, target_type: str = None) -> Dict[str, Any]:
        """Multi-module deep investigation"""
        if not target_type or target_type == 'auto':
            entity = detector.detect(target)
            target_type = entity.type
            target = entity.normalized

        console.print()
        console.print("[bold violet]🔍 DEEP INVESTIGATION[/bold violet]")
        console.print(f"[white]Target[/white] : [bold yellow]{target}[/bold yellow]")
        console.print(f"[white]Type[/white]   : [bold green]{target_type.upper()}[/bold green]")
        console.print(f"[white]Time[/white]   : [dim]{datetime.now().strftime('%H:%M:%S')}[/dim]")
        console.print("[dim]──────────────────────────────────────────────────[/dim]")
        console.print()

        module_map = {
            'username': ['username', 'maigret', 'email', 'darkweb'],
            'email':    ['email', 'darkweb', 'domain'],
            'phone':    ['phone', 'darkweb'],
            'domain':   ['domain', 'ip'],
            'ip':       ['ip', 'domain'],
            'url':      ['url', 'domain', 'ip'],
        }
        modules_to_run = module_map.get(target_type, list(self.modules.keys()))

        results = {}
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(), console=console
        ) as progress:
            task = progress.add_task("[violet]Running modules…[/violet]", total=len(modules_to_run))

            for mod_name in modules_to_run:
                mod = self.modules.get(mod_name)
                if mod:
                    progress.update(task, description=f"[cyan]{mod_name}…[/cyan]")
                    try:
                        r = await mod.scan(target)
                        if r and r.get('data'):
                            results[mod_name] = r
                    except Exception as e:
                        console.print(f"  [red]✗ {mod_name}: {str(e)[:60]}[/red]")
                    progress.advance(task)
                    await asyncio.sleep(0.05)

        self.results = results
        if results:
            console.print("\n[cyan]🔄 Correlating intelligence…[/cyan]")
            self.results['_correlation'] = self.correlation.correlate(results)

        return self.results

    async def display_result(self, result: Dict):
        if not result or result.get('error'):
            return
        mod = result.get('module', '')
        data = result.get('data', {})
        fn = {
            'username': self._show_username,
            'email':    self._show_email,
            'phone':    self._show_phone,
            'domain':   self._show_domain,
            'ip':       self._show_ip,
            'url':      self._show_url,
            'maigret':  self._show_maigret,
            'darkweb':  self._show_darkweb,
        }.get(mod)
        if fn:
            fn(data)

    async def display_summary(self, results: Dict):
        console.print("\n[bold violet]📊 INVESTIGATION SUMMARY[/bold violet]\n")
        t = Table(show_header=True, header_style="bold violet", box=box.SIMPLE_HEAD,
                  pad_edge=False)
        t.add_column("Module", style="bold white", width=12)
        t.add_column("Status", justify="center", width=12)
        t.add_column("Key Findings")

        for name, result in results.items():
            if name.startswith('_'):
                continue
            if name == 'full' and result and result.get('summary'):
                s = result['summary']
                plats = ', '.join(s.get('platforms', [])[:4]) or '—'
                t.add_row('FULL', '[green]✅ OK[/green]',
                          f"{s.get('profiles_found',0)} profiles | {s.get('sites_checked',0)} sites | {plats}")
                continue
            if result and result.get('error'):
                t.add_row(name.upper(), "[red]✗ Error[/red]", str(result['error'])[:60])
            elif result and result.get('data'):
                d = result['data']
                if name == 'username':   findings = f"{d.get('total_found',0)} platforms found"
                elif name == 'email':    findings = f"{len(d.get('mx_records',[]))} MX | SPF {'✓' if d.get('spf') else '✗'} | DMARC {'✓' if d.get('dmarc') else '✗'}"
                elif name == 'phone':    findings = f"{d.get('provider','?')} | {d.get('country','?')} | {d.get('line_type','?')}"
                elif name == 'domain':   findings = f"IP: {', '.join(d.get('ip_addresses',[])[:2]) or '—'} | HTTP {d.get('https_status') or d.get('http_status','?')}"
                elif name == 'ip':       findings = f"{d.get('city','?')}, {d.get('country','?')} | {d.get('isp','?')}"
                elif name == 'url':      findings = f"{d.get('title','?')[:40]} | {len(d.get('social_links',[]))} social links"
                elif name == 'maigret':  findings = f"{d.get('total_found',0)} profiles / {d.get('total_checked',0)} sites"
                elif name == 'darkweb':
                    b = d.get('breach_count', 0)
                    findings = (f"{d.get('sources_found',0)} sources | {d.get('total_records',0)} records "
                                f"| {b} breach{'es' if b != 1 else ''}")
                else:                    findings = "Data found"
                t.add_row(name.upper(), "[green]✅ OK[/green]", findings)
            else:
                t.add_row(name.upper(), "[yellow]⚠ None[/yellow]", "—")

        console.print(t)

        if '_correlation' in results:
            corr = results['_correlation']
            entities = corr.get('entities', {})
            if entities:
                console.print("\n[bold yellow]🔗 Correlated Intel:[/bold yellow]")
                tree = Tree(f"[bold violet]{corr.get('primary','Target')}[/bold violet]")
                for etype, elist in entities.items():
                    if elist:
                        branch = tree.add(f"[yellow]{etype}[/yellow]")
                        for e in list(elist)[:5]:
                            branch.add(f"[dim]{e}[/dim]")
                console.print(tree)

    # ── Display helpers ──
    @staticmethod
    def _kv(label: str, value) -> str:
        """Aligned key/value line for result panels."""
        return f"[white]{label:<13}[/white]: {value}"

    @staticmethod
    def _bullet(platform: str, url: str, extra: str = "") -> str:
        """Aligned bullet line for platform lists."""
        return f"  [cyan]•[/cyan] [white]{platform:<20}[/white]{extra}[dim]{url}[/dim]"

    @staticmethod
    def _show_result_card(title: str, lines: List[str], color: str = "violet"):
        """Print a result card (no box) with a title and divider."""
        console.print()
        console.print(f"[bold {color}]{title}[/bold {color}]")
        console.print(f"[dim]{'─' * 50}[/dim]")
        for line in lines:
            console.print(line)
        console.print()

    def _show_username(self, d):
        found = d.get('found', [])
        lines = [f"[bold violet]👤 Username:[/bold violet] [yellow]{d.get('username')}[/yellow]",
                 f"[green]✓ Found on {len(found)} / {d.get('total_checked',0)} platforms[/green]"]
        for p in found[:15]:
            lines.append(self._bullet(p['platform'], p['url']))
        if len(found) > 15:
            lines.append(f"  [dim]… and {len(found)-15} more[/dim]")
        self._show_result_card("👤 USERNAME OSINT", lines, "violet")

    def _show_email(self, d):
        lines = [
            f"[bold violet]📧 Email:[/bold violet] [yellow]{d.get('email')}[/yellow]",
            self._kv("Domain", d.get('domain')),
            self._kv("MX Records", f"{len(d.get('mx_records',[]))} found"),
            self._kv("SPF", '[green]✓ Present[/green]' if d.get('spf') else '[red]✗ Missing[/red]'),
            self._kv("DMARC", '[green]✓ Present[/green]' if d.get('dmarc') else '[yellow]✗ Missing[/yellow]'),
            self._kv("Disposable", '[red]Yes ⚠[/red]' if d.get('disposable') else '[green]No[/green]'),
            self._kv("Gravatar", '[green]✓ Has profile[/green]' if d.get('gravatar') else 'Not found'),
            self._kv("Website", '[green]✓ ' + str(d.get('website_url','')) + '[/green]' if d.get('has_website') else '[red]No website[/red]'),
        ]
        if d.get('breach_hint'):
            lines.append(self._kv("Breach hint", f"[yellow]{d['breach_hint']}[/yellow]"))
        self._show_result_card("📧 EMAIL OSINT", lines, "magenta")

    def _show_phone(self, d):
        lines = [
            f"[bold violet]📱 Phone:[/bold violet] [yellow]{d.get('input')}[/yellow]",
            self._kv("International", f"[green]{d.get('international')}[/green]"),
            self._kv("Country", f"{d.get('country')} ({d.get('country_iso')})"),
            self._kv("Provider", f"[cyan]{d.get('provider','Unknown')}[/cyan]"),
            self._kv("Type", d.get('line_type')),
            self._kv("Location", d.get('location') or '—'),
            self._kv("Timezone", ', '.join(d.get('timezones',[])[:2]) or '—'),
            self._kv("Mobile", '[green]Yes[/green]' if d.get('is_mobile') else 'No'),
        ]
        if d.get('whatsapp_link'):
            lines.append(self._kv("WhatsApp", f"[green]{d['whatsapp_link']}[/green]"))
        if d.get('telegram_link'):
            lines.append(self._kv("Telegram", f"[green]{d['telegram_link']}[/green]"))
        self._show_result_card("📱 PHONE OSINT", lines, "green")

    def _show_domain(self, d):
        lines = [
            f"[bold violet]🌐 Domain:[/bold violet] [yellow]{d.get('domain')}[/yellow]",
            self._kv("IPv4", ', '.join(d.get('ip_addresses',[])[:3]) or '[red]None[/red]'),
            self._kv("IPv6", ', '.join(d.get('ipv6_addresses',[])[:2]) or '—'),
            self._kv("Nameservers", ', '.join(d.get('nameservers',[])[:3]) or '—'),
            self._kv("MX Records", len(d.get('mx_records',[]))),
            self._kv("HTTPS status", d.get('https_status') or '—'),
            self._kv("HTTP status", d.get('http_status') or '—'),
            self._kv("Server", d.get('server_header') or '—'),
            self._kv("Title", (d.get('title') or '—')[:60]),
        ]
        if d.get('whois'):
            w = d['whois']
            if w.get('registrar'):
                lines.append(self._kv("Registrar", w['registrar']))
            if w.get('creation_date'):
                lines.append(self._kv("Created", str(w['creation_date'])[:10]))
            if w.get('expiration_date'):
                lines.append(self._kv("Expires", str(w['expiration_date'])[:10]))
        if d.get('technologies'):
            lines.append(self._kv("Tech stack", f"[cyan]{', '.join(d['technologies'])}[/cyan]"))
        if d.get('security_headers'):
            sh = d['security_headers']
            sec = []
            if sh.get('hsts'):   sec.append('[green]HSTS[/green]')
            if sh.get('csp'):    sec.append('[green]CSP[/green]')
            if sh.get('xframe'): sec.append('[green]X-Frame[/green]')
            if sec: lines.append(self._kv("Security", ' '.join(sec)))
        self._show_result_card("🌐 DOMAIN OSINT", lines, "yellow")

    def _show_ip(self, d):
        lines = [
            f"[bold violet]🌍 IP:[/bold violet] [yellow]{d.get('ip')}[/yellow]",
            self._kv("Country", f"{d.get('country','?')} ({d.get('country_code','?')})"),
            self._kv("Region", d.get('region','—')),
            self._kv("City", d.get('city','—')),
            self._kv("Coords", f"{d.get('lat','?')}, {d.get('lon','?')}"),
            self._kv("ISP", d.get('isp','—')),
            self._kv("Org", d.get('org','—')),
            self._kv("ASN", f"{d.get('asn','—')} {d.get('asn_name','')}"),
            self._kv("Reverse", d.get('reverse_dns') or '—'),
            self._kv("Proxy/VPN", '[red]⚠ Detected[/red]' if d.get('is_proxy') else '[green]No[/green]'),
            self._kv("Hosting", '[yellow]Yes (datacenter)[/yellow]' if d.get('is_hosting') else 'No'),
            self._kv("Mobile ISP", '[cyan]Yes[/cyan]' if d.get('is_mobile') else 'No'),
        ]
        if d.get('rdap',{}).get('organization'):
            lines.append(self._kv("RIR Org", d['rdap']['organization']))
        if d.get('abuse_contact'):
            lines.append(self._kv("Abuse", f"[yellow]{d['abuse_contact']}[/yellow]"))
        self._show_result_card("🌍 IP OSINT", lines, "yellow")

    def _show_maigret(self, d):
        found = d.get('found', [])
        lines = [
            f"[bold violet]🧠 Maigret:[/bold violet] [yellow]{d.get('username')}[/yellow]",
            f"[green]✓ Found {len(found)} / {d.get('total_checked',0)} platforms (600+ engine)[/green]",
        ]
        names = d.get('real_names', [])
        if names:
            lines.append(self._kv("Real names", f"[cyan]{', '.join(names[:5])}[/cyan]"))
        for p in found[:12]:
            name = f" ({p.get('real_name')})" if p.get('real_name') else ''
            lines.append(self._bullet(p.get('platform',''), p.get('url',''), name))
        if len(found) > 12:
            lines.append(f"  [dim]… and {len(found)-12} more[/dim]")
        self._show_result_card("🧠 MAIGRET OSINT (600+ PLATFORMS)", lines, "violet")

    def _show_darkweb(self, d):
        lines = [
            f"[bold violet]🌑 Dark Web:[/bold violet] [yellow]{d.get('query')}[/yellow] ([dim]{d.get('query_type')}[/dim])",
            self._kv("Sources", f"{d.get('sources_found')} / {d.get('sources_checked')} found"),
            self._kv("Records", d.get('total_records',0)),
        ]
        if d.get('found_in'):
            lines.append(self._kv("Found in", f"[red]{', '.join(d['found_in'])}[/red]"))
        hr = d.get('hudson_rock', {})
        for key in ('email', 'username'):
            h = hr.get(key, {})
            if h.get('total_infections'):
                lines.append(self._kv(f"HR {key}", f"[red]{h['total_infections']} infection(s)[/red]"))
        if not d.get('found_in') and not d.get('breach_count'):
            lines.append("[green]✓ Clean — not found in checked sources[/green]")
        self._show_result_card("🌑 DARK WEB CHECK", lines, "red")

    def _show_url(self, d):
        lines = [
            f"[bold violet]🕸️ URL:[/bold violet] [yellow]{d.get('url')}[/yellow]",
            self._kv("Final URL", d.get('final_url') or '—'),
            self._kv("Title", (d.get('title') or '—')[:60]),
            self._kv("Status", d.get('status') or '—'),
            self._kv("Server", d.get('server_header') or '—'),
            self._kv("Tech", f"[cyan]{', '.join(d.get('technologies',[])[:8]) or '—'}[/cyan]"),
        ]
        if d.get('description'):
            lines.append(self._kv("Desc", d['description'][:80]))
        if d.get('emails'):
            lines.append(self._kv("Emails", f"[green]{', '.join(d['emails'][:5])}[/green]"))
        if d.get('social_links'):
            lines.append(self._kv("Social", f"{len(d['social_links'])} profile link(s) found"))
            for sl in d['social_links'][:8]:
                lines.append(self._bullet(sl['platform'], sl['url']))
        self._show_result_card("🕸️ URL FOOTPRINT", lines, "cyan")


