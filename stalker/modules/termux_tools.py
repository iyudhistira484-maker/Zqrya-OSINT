"""Termux Native Tools Integration.

Uses Termux:API to provide native Android features:
- termux-notification  — push notification with investigation summary
- termux-vibrate       — haptic feedback when complete
- termux-clipboard-set — copy result to clipboard
- termux-share         — share report file
- termux-open          — open HTML report in browser
- termux-tts-speak     — text-to-speech result summary
- termux-location      — get device GPS location
- termux-battery-status — check battery before long scans
- termux-toast         — quick toast notification

Requires: pkg install termux-api && pip install termux-api
Termux:API companion app must be installed.
"""

from __future__ import annotations
from pathlib import Path
import asyncio
import os
import subprocess
import shutil
import json


IS_TERMUX = Path("/data/data/com.termux").is_dir()
HAS_TERMUX_API = shutil.which("termux-notification") is not None


def _run(cmd: list, timeout: int = 10) -> tuple[str, int]:
    """Run a shell command, return (stdout, returncode)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "", -1


async def notify(title: str, content: str, priority: str = "high") -> bool:
    """Send Android push notification via termux-notification."""
    if not IS_TERMUX or not HAS_TERMUX_API:
        return False
    cmd = [
        "termux-notification",
        "--title", title[:50],
        "--content", content[:200],
        "--priority", priority,
        "--id", "zqrya",
        "--sound",
    ]
    _, code = await asyncio.to_thread(_run, cmd)
    return code == 0


async def vibrate(duration_ms: int = 500, force: bool = True) -> bool:
    """Vibrate the device."""
    if not IS_TERMUX or not HAS_TERMUX_API:
        return False
    cmd = ["termux-vibrate", "-d", str(duration_ms)]
    if force:
        cmd.append("-f")
    _, code = await asyncio.to_thread(_run, cmd)
    return code == 0


async def copy_to_clipboard(text: str) -> bool:
    """Copy text to Android clipboard."""
    if not IS_TERMUX or not HAS_TERMUX_API:
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            "termux-clipboard-set",
            stdin=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=text.encode())
        return (proc.returncode or 0) == 0
    except Exception:
        return False


async def open_file(path: str) -> bool:
    """Open a file with the default Android app (e.g., HTML in browser)."""
    if not IS_TERMUX:
        return False
    _, code = await asyncio.to_thread(_run, ["termux-open", str(path)])
    return code == 0


async def share_file(path: str, title: str = "Stalker Report") -> bool:
    """Share a file via Android share sheet."""
    if not IS_TERMUX or not HAS_TERMUX_API:
        return False
    _, code = await asyncio.to_thread(_run, ["termux-share", "-a", "send", str(path)])
    return code == 0


async def speak(text: str, language: str = "en-US") -> bool:
    """Text-to-speech summary (useful when screen is off)."""
    if not IS_TERMUX or not HAS_TERMUX_API:
        return False
    cmd = ["termux-tts-speak", "-l", language, text[:300]]
    _, code = await asyncio.to_thread(_run, cmd)
    return code == 0


async def toast(message: str, short: bool = True) -> bool:
    """Show a brief Android toast notification."""
    if not IS_TERMUX or not HAS_TERMUX_API:
        return False
    cmd = ["termux-toast"]
    if short:
        cmd.append("-s")
    cmd.append(message[:100])
    _, code = await asyncio.to_thread(_run, cmd)
    return code == 0


async def get_battery() -> dict:
    """Check battery status before a long scan."""
    if not IS_TERMUX or not HAS_TERMUX_API:
        return {}
    out, code = await asyncio.to_thread(_run, ["termux-battery-status"])
    if code == 0 and out:
        try:
            return json.loads(out)
        except Exception:
            pass
    return {}


async def get_location(provider: str = "gps") -> dict:
    """Get device GPS/network location."""
    if not IS_TERMUX or not HAS_TERMUX_API:
        return {}
    out, code = await asyncio.to_thread(_run, ["termux-location", "-p", provider, "-r", "once"], timeout=30)
    if code == 0 and out:
        try:
            return json.loads(out)
        except Exception:
            pass
    return {}


async def post_investigation_notify(username: str, summary: dict, report_files: list) -> None:
    """Send complete investigation notification when done — Termux main hook."""
    if not IS_TERMUX:
        return

    profiles = summary.get("profiles_found", 0)
    sites = summary.get("sites_checked", 0)
    duration = summary.get("duration", "?")
    breach = summary.get("breach_hudson_rock", 0)

    title = f"Stalker: @{username} done"
    lines = [f"{profiles}/{sites} profiles found"]
    if breach:
        lines.append(f"⚠ {breach} breach(es)")
    if summary.get("telegram_found"):
        lines.append("✓ Telegram found")
    lines.append(f"Duration: {duration}")
    content = " | ".join(lines)

    await asyncio.gather(
        notify(title, content),
        vibrate(800),
        toast(f"Investigation complete: {profiles} profiles", short=True),
        return_exceptions=True,
    )

    # Open HTML report automatically
    html_files = [f for f in report_files if str(f).endswith(".html")]
    if html_files:
        await asyncio.sleep(1)
        await open_file(str(html_files[0]))


def is_available() -> bool:
    return IS_TERMUX and HAS_TERMUX_API


def setup_instructions() -> str:
    return """
  Termux:API Setup (for native notifications):
  
  1. Install Termux:API from F-Droid:
     https://f-droid.org/packages/com.termux.api/
  
  2. Install the API package in Termux:
     pkg install termux-api
  
  3. Grant permissions in Android Settings:
     Termux:API → Permissions → Allow All
  
  Features unlocked:
  - Push notifications when scan completes
  - Haptic vibration feedback  
  - Auto-open HTML report in browser
  - Share report via Android share sheet
  - Copy results to clipboard
  - Text-to-speech summary
"""
