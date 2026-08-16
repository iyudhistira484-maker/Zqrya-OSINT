#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Real-time target monitor — entry point: `python -m stalker.monitor`.

Pantau aktivitas baru sebuah target (GitHub, Reddit, Pastebin) dan kirim
notifikasi via Telegram/Termux ketika ada perubahan.

Usage:
    python -m stalker.monitor <target> [--type auto|username|email|phone]
                                       [--interval 30] [--once]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from stalker.modules.realtime_monitor import monitor_once, monitor_loop


def _detect_type(target: str) -> str:
    if "@" in target and "." in target.split("@")[-1]:
        return "email"
    if target.replace(" ", "").replace("-", "").replace("+", "").isdigit():
        return "phone"
    return "username"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Monitor a target for new activity (GitHub/Reddit/Pastebin)."
    )
    ap.add_argument("target", help="Username, email, or phone to monitor")
    ap.add_argument("--type", dest="target_type", default="auto",
                    choices=["auto", "username", "email", "phone"],
                    help="Target type (auto-detected by default)")
    ap.add_argument("--interval", type=int, default=30,
                    help="Minutes between checks in loop mode (default: 30)")
    ap.add_argument("--once", action="store_true",
                    help="Run a single check instead of continuous monitoring")
    args = ap.parse_args()

    ttype = args.target_type
    if ttype == "auto":
        ttype = _detect_type(args.target)

    if args.once:
        asyncio.run(monitor_once(args.target, ttype))
    else:
        asyncio.run(monitor_loop(args.target, ttype, args.interval))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n  Monitor stopped.")
        sys.exit(0)
