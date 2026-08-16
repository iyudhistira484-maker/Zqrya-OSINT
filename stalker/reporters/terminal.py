"""Terminal output helpers using Rich."""

from __future__ import annotations
from datetime import datetime

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

if HAS_RICH:
    console = Console()
else:
    console = None


def print_header(text: str):
    if HAS_RICH:
        console.print(f"\n[bold cyan]{text}[/bold cyan]")
        console.print("[cyan]──────────────────────────────────────────────────[/cyan]")
    else:
        print(f"\n{'='*50}")
        print(f"  {text}")
        print(f"{'='*50}")

def print_phase(num: int, name: str, description: str = ""):
    if HAS_RICH:
        console.print(f"\n[bold yellow][{num}/{4}][/bold yellow] [bold white]{name}[/bold white]")
        if description:
            console.print(f"  [dim]{description}[/dim]")
    else:
        print(f"\n[{num}/4] {name}")
        if description:
            print(f"  {description}")

def print_success(text: str):
    if HAS_RICH:
        console.print(f"  [green bold]OK[/green bold] {text}")
    else:
        print(f"  [OK] {text}")

def print_error(text: str):
    if HAS_RICH:
        console.print(f"  [red bold]ERR[/red bold] {text}")
    else:
        print(f"  [ERR] {text}")

def print_warning(text: str):
    if HAS_RICH:
        console.print(f"    [dim]{text}[/dim]")
    else:
        print(f"    {text}")

def print_info(text: str):
    if HAS_RICH:
        console.print(f"  [blue]{text}[/blue]")
    else:
        print(f"  {text}")

def print_divider():
    if HAS_RICH:
        console.rule()
    else:
        print("-" * 50)

def print_banner():
    banner = r"""
  _____ _______       _      _  ________ _____
 / ____|__   __|/\   | |    | |/ /  ____|  __ \
| (___    | |  /  \  | |    | ' /| |__  | |__) |
 \___ \   | | / /\ \ | |    |  < |  __| |  _  /
 ____) |  | |/ ____ \| |____| . \| |____| | \ \
|_____/   |_/_/    \_\______|_|\_\______|_|  \_\
"""
    if HAS_RICH:
        from rich.text import Text
        console.print(Text(banner.strip(chr(10)), style="bold cyan"))
    else:
        print(banner)
