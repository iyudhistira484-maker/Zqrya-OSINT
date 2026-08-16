#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zqrya v3.0 - Utils
Rebranded & enhanced with new features, batch processing help, and better formatting
"""

from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.columns import Columns
from rich.text import Text
from core.banner import console, show_banner

VERSION = "3.0.0"
AUTHOR = "Zqrya Team"
GITHUB = "https://github.com/webdev11-code/Zqrya-OSINT"
TOOL_NAME = "Zqrya"


def _cmd_section(title: str, rows: list, cmd_style: str = "green"):
    """Print a two-column command reference section that wraps cleanly."""
    console.print(f"\n[bold yellow]{title}[/bold yellow]")
    t = Table(show_header=False, box=None, pad_edge=False, padding=(0, 1))
    t.add_column(no_wrap=True)
    t.add_column()
    for cmd, desc in rows:
        t.add_row(f"[{cmd_style}]{cmd}[/{cmd_style}]", f"[dim]{desc}[/dim]")
    console.print(t)


def print_help():
    """Print comprehensive help menu"""
    show_banner()

    # ==================== BASIC USAGE ====================
    _cmd_section("📌 BASIC USAGE", [
        ("python zqrya.py",                   "Launch interactive shell (Zqrya >)"),
        ("python zqrya.py -sh",               "Launch interactive shell (same as above)"),
        ("python zqrya.py -u USERNAME",      "Username OSINT (130+ platforms)"),
        ("python zqrya.py -e EMAIL",         "Email + DNS + breach analysis"),
        ("python zqrya.py -p PHONE",         "Phone OSINT (8 countries)"),
        ("python zqrya.py -d DOMAIN",        "Domain recon (DNS/HTTP/TLS/WHOIS)"),
        ("python zqrya.py -i IP",            "IP geolocation + RDAP + ASN + risk"),
        ("python zqrya.py -url URL",         "Website footprint analysis"),
        ("python zqrya.py -m USERNAME",      "Maigret deep search (600+ platforms)"),
        ("python zqrya.py --darkweb EMAIL",  "Dark web / paste / breach check"),
        ("python zqrya.py --variants USER",  "Generate 150+ username variants"),
        ("python zqrya.py --iplogger",       "IP Logger — tangkap IP target via link"),
        ("python zqrya.py --full TARGET", "Combined OSINT (Full Pipeline)"),
        ("python zqrya.py -web",             "Launch web UI on localhost:7331"),
        ("python zqrya.py -web --port 8080", "Custom web UI port"),
    ])

    # ==================== ADVANCED OPTIONS ====================
    _cmd_section("⚡ ADVANCED OPTIONS", [
        ("--deep",               "Deep investigation (run all relevant modules)"),
        ("--batch targets.txt",  "Batch scan multiple targets from file"),
        ("--batch-delay 2",      "Delay between batch scans (seconds)"),
        ("--output-dir ./reports", "Custom output directory"),
        ("--quiet",              "Suppress output (only save report)"),
        ("--debug",              "Enable debug output"),
        ("--timeout 30",         "Custom request timeout"),
        ("--threads 50",         "Concurrent threads"),
    ], cmd_style="cyan")

    # ==================== REPORT FORMATS ====================
    _cmd_section("📊 REPORT FORMATS", [
        ("... --report",       "Generate report (JSON default)"),
        ("... --format json",  "JSON format (machine readable)"),
        ("... --format html",  "HTML report (interactive)"),
        ("... --format txt",   "Plain text report"),
        ("... --format md",    "Markdown report"),
        ("... --format all",   "Generate all formats at once"),
        ("... --compress",     "Compress JSON output (gzip)"),
        ("... -o report.html", "Specify output filename"),
    ])

    # ==================== BATCH PROCESSING ====================
    console.print("\n[bold yellow]📦 BATCH PROCESSING:[/bold yellow]")
    console.print("  [cyan]Create a file with one target per line:[/cyan]")
    console.print("  [dim]  targets.txt:[/dim]")
    console.print("  [dim]    user1[/dim]")
    console.print("  [dim]    user2@gmail.com[/dim]")
    console.print("  [dim]    08123456789[/dim]")
    console.print("  [dim]    example.com[/dim]")
    console.print("")
    console.print("  [green]python zqrya.py --batch targets.txt --format all --output-dir ./reports[/green]")

    # ==================== PHONE EXAMPLES (8 COUNTRIES) ====================
    console.print("\n[bold yellow]📱 PHONE OSINT — 8 COUNTRIES:[/bold yellow]")

    phone_table = Table(show_header=True, header_style="bold violet", box=box.ROUNDED)
    phone_table.add_column("Country", style="green")
    phone_table.add_column("Code", style="yellow", justify="center")
    phone_table.add_column("Example", style="white")
    phone_table.add_column("Providers", style="dim")

    phone_data = [
        ("🇮🇩 Indonesia", "+62", "08123456789", "Telkomsel, Indosat, XL, Smartfren"),
        ("🇺🇸 USA", "+1", "+12125551234", "AT&T, Verizon, T-Mobile"),
        ("🇬🇧 UK", "+44", "+447700123456", "EE, O2, Vodafone, Three"),
        ("🇲🇾 Malaysia", "+60", "+60123456789", "Maxis, Celcom, DiGi, U Mobile"),
        ("🇮🇳 India", "+91", "+919876543210", "Airtel, Vi, Jio, BSNL"),
        ("🇦🇺 Australia", "+61", "+61412345678", "Telstra, Optus, Vodafone"),
        ("🇸🇬 Singapore", "+65", "+6581234567", "Singtel, StarHub, M1, SIMBA"),
        ("🇵🇭 Philippines", "+63", "+639171234567", "Globe, Smart, DITO"),
    ]

    for row in phone_data:
        phone_table.add_row(*row)

    console.print(phone_table)
    console.print("[dim]  Usage: python zqrya.py -p <number>  (e.g. python zqrya.py -p 08123456789)[/dim]")

    # ==================== EXAMPLES ====================
    console.print("\n[bold green]🚀 REAL-WORLD EXAMPLES:[/bold green]")

    examples = [
        ("[dim]# Username investigation[/dim]", "python zqrya.py -u PiuPiuu"),
        ("[dim]# Email with breach detection[/dim]", "python zqrya.py -e user@gmail.com --report --format html"),
        ("[dim]# Phone number (Indonesia)[/dim]", "python zqrya.py -p 08123456789 --deep"),
        ("[dim]# Domain recon with WHOIS[/dim]", "python zqrya.py -d example.com --format all"),
        ("[dim]# Website footprint[/dim]", "python zqrya.py -url https://example.com"),
        ("[dim]# IP with risk score[/dim]", "python zqrya.py -i 8.8.8.8 --report"),
        ("[dim]# IP Logger (tracking link)[/dim]", "python zqrya.py --iplogger --redirect https://news.example.com/x"),
        ("[dim]# Batch scan 100 targets[/dim]", "python zqrya.py --batch targets.txt --deep --format json"),
        ("[dim]# Generate all report formats[/dim]", "python zqrya.py -u asep --format all -o asep_report"),
        ("[dim]# Quiet mode (no terminal output)[/dim]", "python zqrya.py -d example.com --report --quiet"),
    ]

    for desc, cmd in examples:
        console.print(desc)
        console.print(f"  [cyan]{cmd}[/cyan]")

    # ==================== FEATURE HIGHLIGHTS ====================
    console.print("\n[bold magenta]✨ NEW IN v3.0:[/bold magenta]")
    features = Columns([
        "⌨️ Interactive Shell - Zqrya > menu CLI",
        "🌐 Web UI - Professional dashboard",
        "🧠 Maigret Engine - 600+ platforms",
        "🌑 Dark Web Check - Paste/breach DBs",
        "🦠 Hudson Rock - Infostealer intel",
        "🛰️ Shodan InternetDB - Ports & CVEs",
        "🧬 Username Variants - 150+ perms",
        "🎯 IP Logger - Tracking link",
        "🕸️ URL Module - Website footprint",
        "🆔 WHOIS Lookup - Domain registration",
        "🌗 Theme Toggle - Dark/Light web UI",
    ], equal=False, expand=False)
    console.print(features)

    # ==================== LEGAL DISCLAIMER ====================
    console.print(Panel(
        "[yellow]⚠️  LEGAL DISCLAIMER[/yellow]\n\n"
        "For education & authorized security testing only.\n"
        "• Only investigate targets you own or have explicit permission to test\n"
        "• All data comes from public sources (DNS, RDAP, public websites)\n"
        "• Not for doxing, stalking, or any illegal activities\n\n"
        "[dim]You are solely responsible for complying with all applicable laws.[/dim]",
        border_style="red",
        box=box.HEAVY,
        padding=(1, 2)
    ))

    # ==================== FOOTER ====================
    console.print(f"\n[dim]💡 Need help? Visit [cyan]{GITHUB}[/cyan] • Report issues at GitHub Issues[/dim]")
    console.print(f"[dim]📧 Contact: [cyan]support@zqrya.dev[/cyan] • ⭐ Star the repo if you find it useful![/dim]")


def print_version():
    """Print version information"""
    console.print(f"\n[bold violet]◤ Zqrya v{VERSION}[/bold violet]")
    console.print(f"[dim]   Author: {AUTHOR}[/dim]")
    console.print(f"[dim]   GitHub: {GITHUB}[/dim]")
    console.print(f"[dim]   License: MIT[/dim]")
    console.print(f"[dim]   Python: {__import__('sys').version.split()[0]}[/dim]")
    console.print()
    console.print("[green]✨ Features:[/green]")
    console.print("  • 169+ Username Platforms + Maigret 600+")
    console.print("  • 8 Country Phone OSINT")
    console.print("  • Email Breach Detection + Hudson Rock")
    console.print("  • Dark Web Checker (paste/breach DBs)")
    console.print("  • Domain Tech Stack Detection + WHOIS")
    console.print("  • Website Footprint (URL Module)")
    console.print("  • IP Risk Scoring + Shodan InternetDB")
    console.print("  • Username Variants Generator")
    console.print("  • Web UI Dashboard")
    console.print("  • Batch Processing")
    console.print("  • Multi-format Reports (JSON/HTML/TXT/MD)")


def sanitize_filename(text: str) -> str:
    """Sanitize string for use as filename"""
    import re
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', text)
    sanitized = sanitized.replace(' ', '_')
    sanitized = re.sub(r'_+', '_', sanitized)
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized.strip('_')


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def parse_timeout(timeout_str: str) -> int:
    """Parse timeout string to seconds"""
    try:
        return int(timeout_str)
    except ValueError:
        return 12


def print_banner_small():
    """Print a small banner (for web UI or quick display)"""
    console.print("[bold violet]ZQRYA[/bold violet] [dim]v3.0[/dim]")


def get_version_info() -> dict:
    """Get version information as dict"""
    return {
        'version': VERSION,
        'author': AUTHOR,
        'github': GITHUB,
        'python': __import__('sys').version.split()[0],
        'features': [
            'Username OSINT (130+ platforms)',
            'Email OSINT with breach detection',
            'Phone OSINT (8 countries)',
            'Domain OSINT with tech detection + WHOIS',
            'Website footprint (URL module)',
            'IP OSINT with risk scoring',
            'Web UI',
            'Batch processing',
            'Multi-format reports'
        ]
    }
