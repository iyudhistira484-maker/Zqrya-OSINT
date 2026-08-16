#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zqrya v3.0 - Interactive Shell
`Zqrya > ` command prompt with a complete menu-driven OSINT workflow.
"""
import asyncio
import os
import sys
from datetime import datetime

from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.text import Text
from rich.columns import Columns
from rich.prompt import Prompt, Confirm

from core.banner import console, show_banner, clear_screen
from core.engine import ZqryaEngine
from core.detector import detector
from core.utils import VERSION, print_version

PROMPT = "[bold violet]Zqrya[/bold violet] [bold white]>[/bold white] "


class InteractiveShell:
    """Interactive `Zqrya > ` command shell."""

    def __init__(self, timeout: int = 12, threads: int = 25):
        self.timeout = timeout
        self.threads = threads
        self.engine = None
        self.history = []            # list of dicts: {ts, type, target, found}
        self.deep_mode = False       # default quick scan
        self.auto_report = False     # auto-save report after scan
        self.report_format = "json"
        self.output_dir = "output"

    # ─────────────────────────── helpers ───────────────────────────
    def _fmt_ts(self):
        return datetime.now().strftime("%H:%M:%S")

    def _push_history(self, target, ttype, found=0):
        self.history.append({
            "ts": self._fmt_ts(),
            "type": ttype,
            "target": target,
            "found": found,
        })

    def _print_menu(self):
        items = [
            # ── CORE SCAN ──
            ("1",  "👤  Username OSINT"),
            ("2",  "📧  Email OSINT"),
            ("3",  "📱  Phone OSINT"),
            ("4",  "🌐  Domain Recon"),
            ("5",  "🌍  IP Address"),
            ("6",  "🕸️  Website Footprint (URL)"),
            ("7",  "🧠  Maigret Deep Search (600+ platforms)"),
            ("8",  "🌑  Dark Web / Breach Check"),
            # ── PIPELINE ──
            ("9",  "🧬  Username Variants"),
            ("10", "🚀  Combined OSINT (Full Pipeline)"),
            ("11", "📦  Batch Scan"),
            # ── OSINT TOOLS ──
            ("12", "🪪  NIK/KTP lookup"),
            ("13", "📇  NKK / Kartu Keluarga"),
            ("14", "🔳  QR/barcode decoder"),
            ("15", "👛  E-wallet OSINT"),
            ("16", "🟢  Status online checker"),
            ("17", "📶  Phone HLR lookup"),
            ("18", "↩️  Reverse email"),
            ("19", "🎮  Gaming OSINT"),
            ("20", "📸  IG/TikTok deep"),
            ("21", "🖧  Exposed device search"),
            ("22", "📍  Visual geolocation"),
            # ── SYSTEM ──
            ("23", "🎯  IP Logger (tracking link)"),
            ("24", "🖥️  Launch Web Dashboard"),
            ("25", "🕘  History"),
            ("26", "⚙️  Settings"),
            ("27", "ℹ️  About / Help"),
            ("0",  "🚪  Exit"),
        ]

        console.print("[bold violet]📋 MAIN MENU[/bold violet]")
        console.print()

        half = len(items) // 2
        left = [f"[bold cyan]{o:>2}.[/bold cyan]  {i}" for o, i in items[:half]]
        right = [f"[bold cyan]{o:>2}.[/bold cyan]  {i}" for o, i in items[half:]]
        console.print(Columns(
            ["\n".join(left), "\n".join(right)],
            equal=True, expand=False, padding=(0, 4),
        ))

        console.print()

        # Settings bar
        deep_s = "[green]ON[/green]" if self.deep_mode else "[red]OFF[/red]"
        rep_s = "[green]ON[/green]" if self.auto_report else "[red]OFF[/red]"
        console.print(
            f"  [dim]Deep:[/dim] {deep_s}    "
            f"[dim]Auto-report:[/dim] {rep_s}    "
            f"[dim]Format:[/dim] [cyan]{self.report_format}[/cyan]    "
            f"[dim]History:[/dim] [cyan]{len(self.history)}[/cyan]"
        )
        console.print()

    def _print_help(self):
        console.print("[bold violet]ZQRYA INTERACTIVE SHELL — HELP[/bold violet]")
        console.print("[dim]──────────────────────────────────────────────────[/dim]")
        console.print()
        console.print("[bold yellow]📌 SCAN COMMANDS:[/bold yellow]")
        cmds = [
            ("u <username>",    "Username OSINT (130+ platforms)"),
            ("e <email>",       "Email + DNS + breach analysis"),
            ("p <phone>",       "Phone OSINT (8 countries)"),
            ("d <domain>",      "Domain recon (DNS/WHOIS/tech)"),
            ("i <ip>",          "IP geolocation + RDAP + ASN"),
            ("url <url>",       "Website footprint (URL module)"),
            ("m <username>",    "Maigret deep search (600+ platforms)"),
            ("dw <target>",     "Dark web / paste / breach check"),
            ("var <username>",  "Generate 150+ username variants"),
            ("iplogger",        "IP Logger — tangkap IP target via link"),
            ("full <target>", "Combined OSINT (Full Pipeline)"),
            ("batch <file>",    "Batch scan targets from file"),
        ]
        for c, d in cmds:
            console.print(f"  [green]{c:<18}[/green] [dim]{d}[/dim]")

        console.print()
        console.print("[bold yellow]⚙️  SYSTEM COMMANDS:[/bold yellow]")
        sys_cmds = [
            ("menu",          "Show the main menu"),
            ("deep",          "Toggle deep investigation mode"),
            ("report",        "Toggle auto-save report after scan"),
            ("set-format",    "Change report format (json/html/txt/md/all)"),
            ("history",       "Show scan history"),
            ("again <n>",     "Re-run scan #n from history"),
            ("web",           "Launch web dashboard"),
            ("clear",         "Clear screen"),
            ("version",       "Show version info"),
            ("help",          "Show this help"),
            ("exit / quit",   "Exit the shell"),
        ]
        for c, d in sys_cmds:
            console.print(f"  [cyan]{c:<18}[/cyan] [dim]{d}[/dim]")

        console.print()
        console.print("[bold yellow]⚠️  LEGAL DISCLAIMER[/bold yellow]")
        console.print("[dim]──────────────────────────────────────────────────[/dim]")
        console.print("[dim]Zqrya is for educational purposes and authorized security testing only.[/dim]")
        console.print("[dim]Only investigate targets you own or have permission to test.[/dim]")
        console.print("[dim]All data comes from public sources.[/dim]")

    # ─────────────────────────── runner ───────────────────────────
    async def _run_scan(self, ttype: str, target: str):
        """Run a single-module scan and display the result."""
        async with ZqryaEngine(timeout=self.timeout, max_concurrent=self.threads) as engine:
            if self.deep_mode:
                console.print(f"\n[bold violet]🔍 Deep investigation: [yellow]{target}[/yellow] "
                              f"([bold]{ttype.upper()}[/bold])[/bold violet]")
                results = await engine.investigate_all(target, ttype)
                if results:
                    # Gabung dengan deep pipeline untuk target yang didukung
                    if ttype in ("username", "email", "phone"):
                        full_result = await self._run_full(target, zqrya_results=results)
                        if full_result:
                            results["full"] = full_result
                    # Summary gabungan (termasuk baris full pipeline)
                    await engine.display_summary(results)
                    # expose primary module result for history counting
                    primary = results.get(ttype, {})
                    found = self._count_found(ttype, primary)
                else:
                    found = 0
                return results, found
            else:
                result = await engine.investigate(target, ttype)
                if result and not result.get("error"):
                    await engine.display_result(result)
                    found = self._count_found(ttype, result)
                else:
                    found = 0
                return result, found

    @staticmethod
    def _count_found(ttype: str, result: dict) -> int:
        if not result:
            return 0
        d = result.get("data", {})
        if ttype == "username":
            return len(d.get("found", []))
        if ttype == "email":
            return len(d.get("mx_records", []))
        if ttype == "phone":
            return 1 if d.get("provider") else 0
        if ttype == "domain":
            return len(d.get("ip_addresses", []))
        if ttype == "ip":
            return 1 if d.get("country") else 0
        if ttype == "url":
            return len(d.get("social_links", []))
        if ttype == "maigret":
            return len(d.get("found", []))
        if ttype == "darkweb":
            return d.get("sources_found", 0)
        return 1 if d else 0

    async def _maybe_save_report(self, results: dict, target: str, ttype: str):
        if not self.auto_report or not results:
            return
        from reports.generator import ReportGenerator
        rg = ReportGenerator(output_dir=self.output_dir)
        try:
            if self.report_format == "all":
                base = f"zqrya_{ttype}_{target.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                files = await rg.save_all_formats(results, base)
                console.print(f"[green]✅ Reports saved: {len(files)} files[/green]")
            else:
                fname = f"zqrya_{ttype}_{target.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{self.report_format}"
                if self.report_format == "json":
                    f = await rg.save_json(results, fname)
                elif self.report_format == "html":
                    f = await rg.save_html(results, fname)
                elif self.report_format == "txt":
                    f = await rg.save_txt(results, fname)
                elif self.report_format == "md":
                    f = await rg.save_markdown(results, fname)
                else:
                    f = await rg.save_json(results, fname)
                console.print(f"[green]✅ Report saved: {f}[/green]")
        except Exception as e:
            console.print(f"[red]❌ Report error: {e}[/red]")

    async def _ask_and_scan(self, ttype: str, label: str, hint: str = "", target: str = None):
        console.print(f"\n[bold violet]🔍 {label}[/bold violet]")
        if target is None:
            target = Prompt.ask(f"[cyan]Target[/cyan] ({hint})" if hint else "[cyan]Target[/cyan]")
        if not target.strip():
            console.print("[yellow]⚠  Cancelled[/yellow]")
            return
        target = target.strip()
        found = 0
        results = None
        try:
            if ttype == "full":
                results = await self._run_full(target)
                found = results.get("summary", {}).get("profiles_found", 0) if results else 0
            elif ttype == "variants":
                self._run_variants(target)
                return
            elif ttype == "batch":
                self._run_batch(target)
                return
            else:
                results, found = await self._run_scan(ttype, target)
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠  Scan cancelled[/yellow]")
            return
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            if "--debug" in sys.argv:
                import traceback
                traceback.print_exc()
            return

        self._push_history(target, ttype, found)
        console.print(f"[dim]✓ {label} done — {found} finding(s) at {self._fmt_ts()}[/dim]")
        if results:
            await self._maybe_save_report(results, target, ttype)

    # ─────────────────────────── full investigation ───────────────────────────
    async def _run_full(self, target: str, zqrya_results=None):
        """Run the combined Zqrya + Full Pipeline investigation.

        Pass zqrya_results to reuse an already-completed Zqrya deep scan.
        """
        from stalker.pipeline import run_investigation, _run_maigret
        from stalker.modules import breach_check, username_variants
        from core.detector import detector as det

        console.print(f"\n[bold violet]🚀 Combined OSINT (Full Pipeline): [yellow]{target}[/yellow][/bold violet]")
        entity = det.detect(target)
        ttype = entity.type

        # ── Phase A: Zqrya engine (deep multi-module scan) ──
        if zqrya_results is None:
            console.print("\n[bold cyan]▸ ZQRYA ENGINE[/bold cyan]")
            async with ZqryaEngine(timeout=self.timeout, max_concurrent=self.threads) as engine:
                zqrya_results = await engine.investigate_all(target, ttype)
                if zqrya_results:
                    await engine.display_summary(zqrya_results)
        console.print("\n[bold cyan]▸ DEEP PIPELINE[/bold cyan]")

        if ttype == "email":
            from stalker.modules import email_scanner, dark_web_checker
            console.print("[cyan]📧 Email scanner (30+ platforms)...[/cyan]")
            results = await email_scanner.scan_email(entity.normalized)
            s = email_scanner.summary(results)
            console.print(f"  [green]Registered on {s['registered_count']}/{s['platforms_checked']} platforms[/green]")
            console.print("[cyan]🌑 Dark web check...[/cyan]")
            hr = await breach_check.check_hudson_rock(email=entity.normalized)
            dw = await dark_web_checker.full_darkweb_check(entity.normalized, "email")
            result = {
                "username": entity.normalized,
                "email_scan": results,
                "breach": hr,
                "dark_web": dw,
                "summary": {
                    "profiles_found": s["registered_count"],
                    "platforms": s["registered_platforms"],
                    "breach_hudson_rock": hr.get("email", {}).get("total_infections", 0),
                },
            }
        elif ttype == "phone":
            from stalker.modules import phone_scanner
            console.print("[cyan]📱 Phone scanner (6 platforms + Truecaller)...[/cyan]")
            full = await phone_scanner.full_scan(entity.normalized)
            a = full.get("analysis", {})
            result = {
                "username": entity.normalized,
                "phone_scan": full,
                "summary": {
                    "phone_carrier": a.get("carrier", "?"),
                    "phone_country": a.get("country", "?"),
                    "profiles_found": phone_scanner.summary(full.get("platforms", []))["registered_count"],
                },
            }
            if full.get("truecaller", {}).get("name"):
                console.print(f"  [yellow]Truecaller: {full['truecaller']['name']}[/yellow]")
        else:
            result = await run_investigation(
                entity.normalized, enable_exif=False, enable_dork=True,
                max_sites=300, skip_social=True,
            )

        # ── Merge Zqrya results into the combined report ──
        if result:
            result["zqrya"] = zqrya_results or {}

        console.print(f"\n[bold green]📊 Pipeline Summary:[/bold green]")
        s = result.get("summary", {}) if result else {}
        for k, v in s.items():
            if isinstance(v, (list, dict)):
                console.print(f"  [cyan]{k}:[/cyan] {str(v)[:80]}")
            else:
                console.print(f"  [cyan]{k}:[/cyan] {v}")
        return result

    def _run_variants(self, username: str):
        from stalker.modules.username_variants import generate_variants
        variants = generate_variants(username, max_variants=150)
        console.print(f"\n[bold violet]🧬 Username Variants: [yellow]{username}[/yellow][/bold violet]")
        console.print(f"[dim]Generated {len(variants)} variants[/dim]\n")
        cols = Columns([f"[cyan]{i}.[/cyan] [white]{v}[/white]" for i, v in enumerate(variants, 1)],
                       equal=False, expand=False)
        console.print(cols)
        console.print()

    async def _run_batch(self, path: str):
        if not os.path.isfile(path):
            console.print(f"[red]❌ Batch file not found: {path}[/red]")
            return
        with open(path, "r", encoding="utf-8") as f:
            targets = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        if not targets:
            console.print("[red]❌ No targets in file[/red]")
            return
        console.print(f"\n[bold cyan]📦 Batch scanning {len(targets)} targets[/bold cyan]\n")
        ok = 0
        async with ZqryaEngine(timeout=self.timeout, max_concurrent=self.threads) as engine:
            for idx, t in enumerate(targets, 1):
                console.print(f"[{idx}/{len(targets)}] 🔍 [yellow]{t}[/yellow]")
                try:
                    entity = detector.detect(t)
                    if self.deep_mode:
                        r = await engine.investigate_all(entity.normalized, entity.type)
                    else:
                        r = await engine.investigate(entity.normalized, entity.type)
                    if r and r.get("data"):
                        ok += 1
                        console.print("  [green]✅ OK[/green]")
                    else:
                        console.print("  [yellow]⚠ No results[/yellow]")
                except Exception as e:
                    console.print(f"  [red]✗ {e}[/red]")
                await asyncio.sleep(0.3)
        console.print(f"\n[bold green]📊 Batch done: {ok}/{len(targets)} successful[/bold green]")

    # ─────────────────────────── history ───────────────────────────
    def _show_history(self):
        if not self.history:
            console.print("[yellow]📭 No history yet[/yellow]")
            return
        console.print("[bold violet]🕘 SCAN HISTORY[/bold violet]")
        console.print()
        t = Table(show_header=True, header_style="bold violet", box=box.SIMPLE_HEAD,
                  pad_edge=False)
        t.add_column("#", justify="center", style="cyan", width=5)
        t.add_column("Time", style="dim")
        t.add_column("Type", style="yellow", width=12)
        t.add_column("Target", style="white")
        t.add_column("Found", justify="right", style="green", width=6)
        for i, h in enumerate(self.history, 1):
            t.add_row(str(i), h["ts"], h["type"], h["target"], str(h["found"]))
        console.print(t)
        console.print("[dim]Re-run a scan with: [cyan]again <n>[/cyan][/dim]")

    async def _rescan(self, n: int):
        if not (1 <= n <= len(self.history)):
            console.print("[red]❌ Invalid history index[/red]")
            return
        h = self.history[n - 1]
        console.print(f"\n[cyan]↻ Re-running: {h['type']} → {h['target']}[/cyan]")
        if h["type"] == "full":
            await self._ask_and_scan("full", "Combined OSINT (Full Pipeline)")
        else:
            results, found = await self._run_scan(h["type"], h["target"])
            self._push_history(h["target"], h["type"], found)
            if results:
                await self._maybe_save_report(results, h["target"], h["type"])

    # ─────────────────────────── settings ───────────────────────────
    def _show_settings(self):
        console.print("[bold violet]⚙️  SETTINGS[/bold violet]")
        console.print("[dim]──────────────────────────────────────────────────[/dim]")
        console.print()
        rows = [
            ("Deep mode",     "ON" if self.deep_mode else "OFF"),
            ("Auto-report",   "ON" if self.auto_report else "OFF"),
            ("Report format", self.report_format),
            ("Output dir",    self.output_dir),
            ("Timeout",       f"{self.timeout}s"),
            ("Threads",       str(self.threads)),
        ]
        for i, (label, val) in enumerate(rows, 1):
            console.print(f"  [cyan]{i}.[/cyan] {label:<14}: [bold]{val}[/bold]")
        console.print()
        console.print("[dim]Tip: use commands [cyan]deep[/cyan], [cyan]report[/cyan], [cyan]set-format[/cyan][/dim]")

    # ─────────────────────────── web ───────────────────────────
    def _launch_web(self):
        from web.server import start_web_server
        console.print("\n[bold cyan]🖥️  Starting web dashboard on http://localhost:7331[/bold cyan]")
        console.print("[dim]Press Ctrl+C to stop the server and return to shell[/dim]\n")
        try:
            start_web_server(port=7331, open_browser=False)
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠  Web server stopped[/yellow]")
        except Exception as e:
            console.print(f"[red]❌ Web error: {e}[/red]")

    # ─────────────────────────── IP logger ───────────────────────────
    async def _run_iplogger(self):
        from stalker.modules.ip_logger import run_ip_logger
        from stalker.reporters import terminal as term

        console.print("\n[bold violet]🎯 IP LOGGER — tangkap IP target saat mereka klik link[/bold violet]")
        console.print("[dim]  [1] Redirect + LIVE — redirect ke URL, tetap ping tiap 15s sambil terbuka[/dim]")
        console.print("[dim]  [2] Halaman HTML custom[/dim]")
        console.print("[dim]  [3] Pixel 1x1 (email tracking)[/dim]")
        console.print()
        choice = Prompt.ask("[cyan]Pilih decoy[/cyan]", choices=["1", "2", "3"], default="1")

        redirect_url = None
        page_html = None
        pixel = False
        live = False
        if choice == "1":
            live = True
            redirect_url = Prompt.ask("[cyan]URL redirect[/cyan]").strip() or \
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        elif choice == "2":
            page_html = Prompt.ask("[cyan]HTML (kosong = default 'Loading…')[/cyan]").strip() or (
                "<!doctype html><html><body style='background:#000;color:#fff;"
                "font-family:sans-serif;display:flex;align-items:center;"
                "justify-content:center;height:100vh;margin:0'>"
                "<h1>Loading…</h1></body></html>")
        else:
            pixel = True

        port_raw = Prompt.ask("[cyan]Port[/cyan]", default="8080").strip()
        try:
            port = int(port_raw)
        except ValueError:
            port = 8080

        term.print_header("IP LOGGER — TRACKING LINK")
        console.print()
        try:
            await run_ip_logger(port=port, redirect_url=redirect_url,
                                page_html=page_html, pixel=pixel, live=live,
                                shorten=True, public_tunnel=True)
        except OSError as e:
            console.print(f"[red]❌ Port {port} tidak bisa dipakai: {e}[/red]")
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠  Logger dihentikan[/yellow]")

    # ─────────────────────────── new OSINT tools ───────────────────────────
    def _run_osint_tool(self, key: str, target: str = None):
        import subprocess
        tools = {
            "nik": ("NIK/KTP lookup", "NIK 16 digit", "nik"),
            "nkk": ("NKK / Kartu Keluarga", "NKK 16 digit", "nkk"),
            "qr": ("QR/barcode decoder", "path file / URL gambar", "qr"),
            "ewallet": ("E-wallet OSINT", "nomor HP (08xx)", "ewallet"),
            "online": ("Status online checker", "username Telegram / nomor HP", "online"),
            "hlr": ("Phone HLR lookup", "nomor HP", "hlr"),
            "revemail": ("Reverse email", "alamat email", "revemail"),
            "gaming": ("Gaming OSINT", "username", "gaming"),
            "social": ("IG/TikTok deep", "username", "social"),
            "device": ("Exposed device search", "alamat IP", "device"),
            "geolocate": ("Visual geolocation", "path file / URL gambar", "geolocate"),
        }
        label, hint, cmd = tools[key]
        if not target:
            target = Prompt.ask(f"[cyan]{label} — target ({hint})[/cyan]").strip()
        if not target:
            console.print("[yellow]⚠  Cancelled[/yellow]")
            return
        console.print()
        subprocess.run([sys.executable, "-m", "stalker.cli", cmd, target])

    # ─────────────────────────── main loop ───────────────────────────
    async def run(self):
        # Gate: database GeoIP wajib diunduh dulu sebelum akses
        try:
            from modules.geoip_local import require_geoip
            if not require_geoip(console):
                return
        except ImportError:
            pass

        clear_screen()
        show_banner()
        console.print(
            "[bold violet]INTERACTIVE SHELL[/bold violet]  [dim]•[/dim]  "
            "[white]Type a number, a command, or [bold]help[/bold][/white]"
        )
        console.print()
        self._print_menu()

        while True:
            try:
                raw = console.input(PROMPT)
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]👋 Goodbye![/yellow]")
                break

            cmd = raw.strip()
            if not cmd:
                continue

            low = cmd.lower()
            parts = cmd.split(None, 1)
            head = parts[0].lower()
            rest = parts[1].strip() if len(parts) > 1 else ""

            # ── exit ──
            if low in ("exit", "quit", "q", "0", "bye"):
                console.print("[yellow]👋 Goodbye![/yellow]")
                break

            # ── help / menu / clear / version ──
            if low in ("help", "?", "27"):
                self._print_help()
            elif low in ("menu", "home"):
                console.print()
                self._print_menu()
            elif low in ("clear", "cls"):
                clear_screen()
                show_banner()
            elif low in ("version", "ver"):
                print_version()
            elif low in ("about",):
                print_version()

            # ── scans ──
            elif head in ("u", "username", "1"):
                await self._ask_and_scan("username", "Username OSINT", "e.g. PiuPiuu", rest or None)
            elif head in ("e", "email", "2"):
                await self._ask_and_scan("email", "Email OSINT", "e.g. user@mail.com", rest or None)
            elif head in ("p", "phone", "3"):
                await self._ask_and_scan("phone", "Phone OSINT", "e.g. 08123456789 / +62...", rest or None)
            elif head in ("d", "domain", "4"):
                await self._ask_and_scan("domain", "Domain Recon", "e.g. example.com", rest or None)
            elif head in ("i", "ip", "5"):
                await self._ask_and_scan("ip", "IP Address", "e.g. 8.8.8.8", rest or None)
            elif head in ("url", "6"):
                await self._ask_and_scan("url", "Website Footprint", "e.g. https://example.com", rest or None)
            elif head in ("m", "maigret", "7"):
                await self._ask_and_scan("maigret", "Maigret Deep Search", "username, 600+ platforms", rest or None)
            elif head in ("dw", "darkweb", "8"):
                await self._ask_and_scan("darkweb", "Dark Web / Breach Check", "email, username, or phone", rest or None)
            elif head in ("var", "variants", "9"):
                if rest:
                    self._run_variants(rest)
                else:
                    await self._ask_and_scan("variants", "Username Variants")
            elif head in ("full", "10"):
                if rest:
                    r = await self._run_full(rest)
                    self._push_history(rest, "full",
                                       r.get("summary", {}).get("profiles_found", 0) if r else 0)
                    if r:
                        await self._maybe_save_report(r, rest, "full")
                else:
                    await self._ask_and_scan("full", "Combined OSINT (Full Pipeline)")
            elif head in ("batch", "11"):
                if rest:
                    await self._run_batch(rest)
                else:
                    path = Prompt.ask("[cyan]Batch file path[/cyan]")
                    await self._run_batch(path.strip())

            # ── IP logger ──
            elif low in ("iplogger", "grab", "23"):
                await self._run_iplogger()

            # ── web dashboard ──
            elif low in ("web", "24"):
                self._launch_web()

            # ── new OSINT tools ──
            elif head in ("12", "nik", "ktp"):
                self._run_osint_tool("nik", rest or None)
            elif head in ("13", "nkk", "kk"):
                self._run_osint_tool("nkk", rest or None)
            elif head in ("14", "qr", "barcode"):
                self._run_osint_tool("qr", rest or None)
            elif head in ("15", "ewallet", "gopay", "ovo", "dana"):
                self._run_osint_tool("ewallet", rest or None)
            elif head in ("16", "online", "lastseen"):
                self._run_osint_tool("online", rest or None)
            elif head in ("17", "hlr"):
                self._run_osint_tool("hlr", rest or None)
            elif head in ("18", "revemail", "remail"):
                self._run_osint_tool("revemail", rest or None)
            elif head in ("19", "gaming", "game"):
                self._run_osint_tool("gaming", rest or None)
            elif head in ("20", "social", "sosmed"):
                self._run_osint_tool("social", rest or None)
            elif head in ("21", "device", "exposed"):
                self._run_osint_tool("device", rest or None)
            elif head in ("22", "geolocate", "locate"):
                self._run_osint_tool("geolocate", rest or None)

            # ── history ──
            elif low in ("history", "25"):
                self._show_history()
            elif head == "again":
                try:
                    await self._rescan(int(rest))
                except ValueError:
                    console.print("[red]❌ Usage: again <history-number>[/red]")

            # ── settings ──
            elif low in ("settings", "26"):
                self._show_settings()
            elif low == "deep":
                self.deep_mode = not self.deep_mode
                console.print(f"[green]✅ Deep mode: {'ON' if self.deep_mode else 'OFF'}[/green]")
            elif low == "report":
                self.auto_report = not self.auto_report
                console.print(f"[green]✅ Auto-report: {'ON' if self.auto_report else 'OFF'}[/green]")
            elif head == "set-format":
                fmt = rest.lower() if rest else Prompt.ask(
                    "[cyan]Format[/cyan]", choices=["json", "html", "txt", "md", "all"])
                if fmt in ("json", "html", "txt", "md", "all"):
                    self.report_format = fmt
                    console.print(f"[green]✅ Report format: {fmt}[/green]")
                else:
                    console.print("[red]❌ Valid: json, html, txt, md, all[/red]")

            # ── unknown ──
            else:
                console.print(f"[red]❌ Unknown command: {cmd}[/red]")
                console.print("[dim]Type [cyan]help[/cyan] for available commands or [cyan]menu[/cyan] for the menu[/dim]")

            console.print()


def run_interactive(timeout: int = 12, threads: int = 25):
    """Entry point for the interactive shell."""
    shell = InteractiveShell(timeout=timeout, threads=threads)
    try:
        asyncio.run(shell.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Goodbye![/yellow]")


if __name__ == "__main__":
    run_interactive()
