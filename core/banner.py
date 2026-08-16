#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zqrya v3.0 - Banner"""

import os
import sys
import time
from rich.console import Console
from rich.text import Text
from rich.theme import Theme
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

custom_theme = Theme({
    "info":      "dim cyan",
    "warning":   "yellow",
    "danger":    "bold red",
    "success":   "bold green",
    "zqrya":     "bold violet",
    "highlight": "bold blue",
    "dim":       "dim white",
    "accent":    "bold cyan",
})

console = Console(theme=custom_theme)

# ASCII Art Banner - ZQRYA (ANSI Shadow, handcrafted)
BANNER = r"""
       ▄██████▓  ▒█████     ▒█████     ██   ██      ▄██▄
      ██  ▒██▒   ▒██▒  ██▒  ▒██▒  ██▒  ▓██  ██▒    ██  ██▒
      ░ ▓██▄ ▒   ▒██░  ██░  ▒██▀▀██░   ▒██  ██░    ██  ██░
       ▒██▒  ▒   ▒██   ██░  ░▓█ ░██    ░▓████░     ██▀▀██░
      ▒██████▒▒  ░ ████▓▒░  ░▓█▒░██▓    ░ ▒██▒░    ██  ██░
      ▒ ▒▓▒ ▒ ░  ░ ▒░▒░▒░   ▒ ░░▒ ▒     ░ ▒██▒     ██  ██░
      ░ ░▒  ░      ░ ▒ ▒░   ▒ ░░▒ ▒     ░ ▒██▒     ░░  ░░
      ░  ░  ░    ░ ░ ░ ▒ ▒  ░  ░░ ░     ░  ░░      ░    ░
            ░        ░ ░ ░  ░  ░  ░     ░  ░
"""

# Small banner for compact display
SMALL_BANNER = """
ZQRYA v3.0 - OSINT Intelligence Suite
No API Keys • Public Sources Only
"""

# One-line banner for logging
LINE_BANNER = "◤ ZQRYA v3.0 - Advanced OSINT Framework"


def show_banner():
    """Display the Zqrya banner with premium styling"""
    clear_screen()

    # ASCII art (no surrounding box)
    art_lines = [line for line in BANNER.split('\n') if line.strip()]
    for line in art_lines:
        console.print(f"[bold violet]{line}[/bold violet]")

    console.print()

    # Title / tagline (aligned with the art, no box)
    console.print(
        "      [bold violet]Z Q R Y A[/bold violet]  [dim]•[/dim]  "
        "[bold white]v3.0 OSINT Intelligence Suite[/bold white]"
    )
    console.print("      [dim]No API Keys  •  Public Sources Only  •  Ethical Use[/dim]")
    console.print("      [yellow]⚠  For education & authorized security research only[/yellow]")

    console.print()

    # Command hints (aligned, two tidy lines)
    console.print("  " + "  ".join([
        "[bold cyan]⚡ Quick:[/bold cyan]",
        "[green]-u USER[/green]", "[green]-e EMAIL[/green]", "[green]-p PHONE[/green]",
        "[green]-d DOMAIN[/green]", "[green]-i IP[/green]", "[green]-url URL[/green]",
    ]))
    console.print("  " + "  ".join([
        "[cyan]🛠  Advanced:[/cyan]",
        "[green]--deep[/green]", "[green]--batch FILE[/green]", "[green]-m USER[/green]",
        "[green]--full TARGET[/green]", "[yellow]-web[/yellow]",
    ]))
    console.print()
    console.print("  [dim]💡 Run with no arguments to open the interactive shell[/dim]")
    console.print("  [dim]Zqrya • OSINT for everyone • © 2026[/dim]")
    console.print()


def show_small_banner():
    """Display a smaller banner (for web UI or compact mode)"""
    console.print(SMALL_BANNER, style="bold violet")


def show_loading_banner():
    """Display banner with loading animation"""
    console.clear()
    console.print("[bold violet]ZQRYA v3.0[/bold violet] - [dim]Initializing...[/dim]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console
    ) as progress:
        progress.add_task(description="[cyan]Loading modules...[/cyan]", total=None)
        time.sleep(0.5)

    console.clear()
    show_banner()


def get_banner_text() -> str:
    """Return banner as plain text (for logs, reports, etc.)"""
    return """Zqrya v3.0 - OSINT Intelligence Suite
    No API Keys Required • Public Sources Only • Ethical Use Only
    """


def get_banner_rich() -> Text:
    """Return banner as rich Text object"""
    text = Text()
    text.append("ZQRYA", style="bold violet")
    text.append(" v3.0 ", style="bold white")
    text.append("• ", style="dim")
    text.append("OSINT Framework", style="cyan")
    return text


def print_header(title: str, subtitle: str = "", icon: str = "🔍"):
    """Print a formatted header with title and subtitle"""
    console.print()
    console.print(f"[bold violet]{icon} {title}[/bold violet]")
    if subtitle:
        console.print(f"[dim]  {subtitle}[/dim]")
    print_divider()
    console.print()


def print_divider(char: str = "─", length: int = 50):
    """Print a divider line"""
    console.print(f"[dim]{char * length}[/dim]")


def print_entity_summary(entity_type: str, count: int, icon: str = "📦"):
    """Print entity summary line"""
    if count > 0:
        console.print(f"  {icon} [cyan]{entity_type.title()}:[/cyan] [green]{count}[/green]")
    else:
        console.print(f"  {icon} [cyan]{entity_type.title()}:[/cyan] [dim]0[/dim]")


def animate_loading(message: str = "Loading", duration: float = 1.0):
    """Simple loading animation"""
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    start = time.time()
    i = 0

    while time.time() - start < duration:
        console.print(f"\r[cyan]{chars[i % len(chars)]}[/cyan] {message}...", end="")
        time.sleep(0.1)
        i += 1

    console.print("\r" + " " * 50, end="")
    console.print("\r", end="")


# ==================== CONVENIENCE FUNCTIONS ====================

def print_success(msg: str):
    """Print success message"""
    console.print(f"[success]✅ {msg}[/success]")


def print_error(msg: str):
    """Print error message"""
    console.print(f"[danger]❌ {msg}[/danger]")


def print_warning(msg: str):
    """Print warning message"""
    console.print(f"[warning]⚠  {msg}[/warning]")


def print_info(msg: str):
    """Print info message"""
    console.print(f"[info]ℹ  {msg}[/info]")


def print_debug(msg: str):
    """Print debug message (only shown with --debug flag)"""
    if "--debug" in sys.argv:
        console.print(f"[dim]🐛 DEBUG: {msg}[/dim]")


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


# ==================== PROGRESS BARS ====================

def create_progress():
    """Create a rich progress bar"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        transient=False
    )


def create_spinner():
    """Create a simple spinner"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    )


# Export commonly used functions
__all__ = [
    'console',
    'show_banner',
    'show_small_banner',
    'show_loading_banner',
    'get_banner_text',
    'get_banner_rich',
    'print_header',
    'print_divider',
    'print_entity_summary',
    'animate_loading',
    'print_success',
    'print_error',
    'print_warning',
    'print_info',
    'print_debug',
    'clear_screen',
    'create_progress',
    'create_spinner'
]
