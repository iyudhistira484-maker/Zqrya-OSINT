"""Stalker — Interactive entry point with auto-detection (phone/email/username).

Modes adapt based on input type:
  - Phone  (+62...): Phone Scanner, Breach, Telegram
  - Email  (@): Email Scanner 30+ platforms, Breach, Dork
  - Username: Full OSINT pipeline

Termux: output via Telegram Bot with full investigation summary.
"""

from __future__ import annotations
import asyncio
import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from stalker.config import Config
from stalker.reporters import terminal as term

IS_TERMUX = Path("/data/data/com.termux").is_dir()

PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


# ============================================================
#  PIPELINE DIAGRAMS
# ============================================================
PIPELINE_FULL = r"""
   [1] Full Investigation
   +-- Phase 1: Maigret Username Search (600+ sites)
   |       +-- Custom APIs (Instagram, TikTok, Twitter, YouTube, GitHub)
   |       +-- Telegram Profiler
   +-- Phase 2: Intel Extraction
   |       |-- Breach Check (Hudson Rock)
   |       |-- Text Profiler (emails, phones, crypto, social handles)
   |       +-- Email Scanner (30+ platforms)
   +-- Phase 3: Phone + Leak
   |       |-- Phone Scanner (Instagram, Snapchat, Amazon, WA, Telegram, Signal)
   |       +-- Password Leak (Pwned Passwords)
   +-- Phase 4: Visual Analysis
   |       |-- Face Search (Yandex + Google + Bing + TinEye + S4F)
   |       |-- Reverse Image (Yandex)
   |       +-- EXIF Metadata
   +-- Phase 5: Deep Search
   |       |-- Smart Dork (Google + DuckDuckGo)
   |       +-- Recursive Search
   +-- Phase 6: Report
           |-- Social Graph
           |-- Avatar Download
           +-- HTML + JSON Report
"""

PIPELINE_QUICK = r"""
   [2] Quick Profile
   +-- Maigret Quick Search (100 sites)
   +-- Custom APIs + Telegram + Breach + Text Profiler
   +-- HTML + JSON Report
"""

PIPELINE_TELEGRAM = r"""
   [3] Deep Telegram
   +-- Profile Lookup (display name, bio, avatar, numeric ID)
"""

PIPELINE_DORK = r"""
   [4] Smart Dork Only
   +-- Quick Search + Custom APIs -> Smart Dork -> Report
"""

PIPELINE_EMAIL = r"""
   [5] Email Investigation
   +-- Email Scanner (30+ platforms)
   +-- Breach Check (Hudson Rock)
   +-- Smart Dork on local-part
   +-- HTML + JSON Report
"""

PIPELINE_FACE = r"""
   [5] Face Search
   +-- 5 engines on avatar (Yandex, Google, Bing, TinEye, S4F)
   +-- HTML + JSON Report
"""

PIPELINE_PHONE = r"""
   [2] Phone Investigation
   +-- Phone Scanner (IG, Snapchat, Amazon, WA, Telegram, Signal)
   +-- Breach Check (Hudson Rock)
   +-- Telegram Profiler (if username found)
   +-- HTML + JSON Report
"""

PIPELINE_GUIDED = r"""
   [6] Guided Mode — pick specific modules
"""


# ============================================================
#  TELEGRAM SENDER (Termux)
# ============================================================

def _get_telegram_creds():
    if Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHAT_ID:
        return Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID

    print()
    term.print_divider()
    print("  Telegram Bot Setup (Required for Termux output)")
    print()
    bot_token = input("  Bot Token: ").strip()
    chat_id = input("  Chat ID  : ").strip()

    if bot_token and chat_id:
        env_path = BASE_DIR / ".env"
        lines = []
        if env_path.exists():
            lines = env_path.read_text().splitlines()
        updated = []
        found_token, found_chat = False, False
        for line in lines:
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                updated.append(f"TELEGRAM_BOT_TOKEN={bot_token}")
                found_token = True
            elif line.startswith("TELEGRAM_CHAT_ID="):
                updated.append(f"TELEGRAM_CHAT_ID={chat_id}")
                found_chat = True
            else:
                updated.append(line)
        if not found_token:
            updated.append(f"TELEGRAM_BOT_TOKEN={bot_token}")
        if not found_chat:
            updated.append(f"TELEGRAM_CHAT_ID={chat_id}")
        env_path.write_text("\n".join(updated) + "\n")
        Config.TELEGRAM_BOT_TOKEN = bot_token
        Config.TELEGRAM_CHAT_ID = chat_id
        return bot_token, chat_id
    return "", ""


async def _telegram_send(username: str, result: dict, report_files: list):
    from stalker.modules.telegram_sender import send_message, send_report_files

    bot_token = Config.TELEGRAM_BOT_TOKEN
    chat_id = Config.TELEGRAM_CHAT_ID

    if not bot_token or not chat_id:
        bot_token, chat_id = _get_telegram_creds()
    if not bot_token or not chat_id:
        term.print_error("Telegram not configured — reports saved locally only.")
        return

    print()
    print("  Sending report to Telegram...")

    s = result.get("summary", {})
    lines = [f"<b>Stalker Intelligence Report</b>", f"Target: @{username}"]
    lines.append("")

    pf = s.get("profiles_found", 0)
    sc = s.get("sites_checked", 0)
    lines.append(f"Profiles: {pf}/{sc} sites")
    if s.get("platforms"):
        lines.append(f"Platforms: {', '.join(s['platforms'][:10])}")
    if s.get("custom_api_platforms"):
        lines.append(f"Custom APIs: {', '.join(s['custom_api_platforms'])}")
    if s.get("real_names_found"):
        lines.append(f"Names: {', '.join(s['real_names_found'][:5])}")

    if s.get("email_registered"):
        lines.append(f"Email: {s['email_registered']} platform(s)")
    if s.get("telegram_found"):
        lines.append(f"Telegram: {s.get('telegram_display', '@'+username)}")

    if s.get("breach_hudson_rock"):
        lines.append(f"<b>Hudson Rock:</b> {s['breach_hudson_rock']} infection(s)")
    if s.get("password_leaks"):
        lines.append(f"<b>Password Leaks:</b> {s['password_leaks']} found")

    if s.get("phone_registered"):
        lines.append(f"Phone: {s['phone_registered']} platform(s)")
    if s.get("text_entities"):
        lines.append(f"Extracted: {', '.join(s['text_entities'][:5])}")

    if s.get("face_search_engines"):
        lines.append(f"Face Search: {len(s['face_search_engines'])} engines, {s.get('face_search_pages', 0)} pages")
    if s.get("reverse_image_pages") or s.get("reverse_image_similar"):
        lines.append(f"Reverse Image: {s.get('reverse_image_pages',0)} pages, {s.get('reverse_image_similar',0)} similar")
    if s.get("recursive_usernames"):
        lines.append(f"Recursive: {len(s['recursive_usernames'])} usernames")
    if s.get("dork_names_searched"):
        lines.append(f"Smart Dork: {len(s['dork_names_searched'])} queries")
    if s.get("link_aggregators_found"):
        lines.append(f"Link Aggregators: {', '.join(s['link_aggregators_found'])}")
    if s.get("pastebin_urls"):
        lines.append(f"Pastebin URLs: {len(s['pastebin_urls'])} found")

    lines.append(f"Duration: {s.get('duration', '0s')}")
    lines.append("")
    
    # FIX: Safe casting to Path to prevent AttributeError if elements are strings
    html_files = [Path(f) for f in report_files if Path(f).suffix == ".html"]
    if html_files:
        try:
            size = html_files[0].stat().st_size
            lines.append(f"Report: {html_files[0].name} ({size:,} bytes)")
        except OSError:
            lines.append(f"Report: {html_files[0].name}")

    summary = "\n".join(lines)
    await send_message(bot_token, chat_id, summary)
    sent = await send_report_files([Path(f) for f in report_files], bot_token, chat_id)
    for name in sent:
        term.print_success(f"Sent via Telegram: {name}")
    if not sent:
        term.print_error("Failed to send — reports saved locally only.")


# ============================================================
#  MAIN MENU (with loop)
# ============================================================
def show_menu():
    # Gate: database GeoIP wajib diunduh dulu sebelum akses
    try:
        from modules.geoip_local import require_geoip
        if not require_geoip():
            sys.exit(1)
    except ImportError:
        pass

    while True:
        _clear_screen()
        term.print_banner()
        term.print_divider()
        print()
        print("  [u] Update Maigret database (refresh site list)")
        print("  [n] Search by real name")
        print("  [m] Monitor a target (real-time alerts)")
        print("  [l] Check password leak (Pwned)")
        print("  [g] IP Logger (tracking link)")
        print()
        value = input("  Enter username, email, or phone (or 'exit' to quit): ").strip()
        if value.lower() in ("exit", "quit", "0"):
            print("\n  Goodbye!")
            break
        if value.lower() == "u":
            term.print_phase(0, "Updating", "Refreshing Maigret site list...")
            os.system("python -m maigret --update-db")
            input("  Update complete. Press Enter to continue...")
            continue
        if value.lower() == "n":
            show_name_menu()
            input("  Press Enter to continue...")
            continue
        if value.lower() == "m":
            show_monitor_menu()
            input("  Press Enter to continue...")
            continue
        if value.lower() == "l":
            show_leak_menu()
            input("  Press Enter to continue...")
            continue
        if value.lower() == "g":
            show_iplogger_menu()
            input("  Press Enter to continue...")
            continue
        if not value:
            term.print_error("Input required!")
            input("  Press Enter to continue...")
            continue

        is_email = "@" in value and "." in value.split("@")[-1]
        is_phone = bool(PHONE_RE.match(value.replace(" ", "").replace("-", "")))

        input_type = "PHONE" if is_phone else "EMAIL" if is_email else "USERNAME"
        print(f"\n  Detected: {input_type}")
        print()

        if is_phone:
            _phone_menu(value)
        elif is_email:
            _email_menu(value)
        else:
            _username_menu(value)

        print()
        input("  Press Enter to return to main menu...")


def _username_menu(username: str):
    print("  [1] Full Investigation       — All modules (comprehensive)")
    print("  [2] Quick Profile            — Username + APIs + Breach + Telegram")
    print("  [3] Deep Telegram            — Telegram profiler only")
    print("  [4] Smart Dork Only          — Quick search -> Dork -> Report")
    print("  [5] Face Search              — 5 engines on avatar")
    print("  [6] Guided Mode              — Pick specific modules")
    print("  [7] Linktree/Bio.site/Carrd  — Check link aggregators")
    print("  [8] Pastebin Leak Check      — Search pastebin/justpaste")
    print("  [p] Show pipeline diagrams")
    print()

    choice = _get_choice("1-8")
    if choice == "p":
        print(PIPELINE_FULL)
        print(PIPELINE_QUICK)
        print(PIPELINE_TELEGRAM)
        print(PIPELINE_DORK)
        print(PIPELINE_FACE)
        print(PIPELINE_EMAIL)
        print(PIPELINE_PHONE)
        print(PIPELINE_GUIDED)
        print()
        choice = _get_choice("1-8")

    mode_map = {
        "1": lambda: _run_full(username),
        "2": lambda: _run_quick(username),
        "3": lambda: _run_telegram(username),
        "4": lambda: _run_dork_only(username),
        "5": lambda: _run_face_search(username),
        "7": lambda: asyncio.run(_run_linktree(username)),
        "8": lambda: asyncio.run(_run_pastebin(username)),
    }
    if choice in mode_map:
        asyncio.run(mode_map[choice]())
    elif choice == "6":
        asyncio.run(_run_guided(username))
    else:
        term.print_error("Invalid choice.")


def _email_menu(email: str):
    print("  [1] Full Investigation       — Email Scanner + Breach + Dork")
    print("  [2] Email Scanner Only       — 30+ platforms")
    print("  [3] Breach Check + Dork      — Hudson Rock + Smart Dork")
    print("  [4] Guided Mode              — Pick specific modules")
    print("  [5] Domain WHOIS Check       — WHOIS lookup")
    print()

    choice = _get_choice("1-5")
    if choice == "1":
        asyncio.run(_run_email_full(email))
    elif choice == "2":
        asyncio.run(_run_email(email))
    elif choice == "3":
        asyncio.run(_run_email_breach_dork(email))
    elif choice == "4":
        asyncio.run(_run_guided(email))
    elif choice == "5":
        asyncio.run(_run_whois(email))
    else:
        term.print_error("Invalid choice.")


def _phone_menu(phone: str):
    print("  [1] Phone Investigation      — Phone Scanner (6 platforms) + Full Intel")
    print("  [2] Phone Scanner Only       — Check 6 social platforms")
    print("  [3] Anti-Scam Toolkit        — Report to platforms + Expose scammer")
    print("  [4] Guided Mode              — Pick specific modules")
    print()

    choice = _get_choice("1-4")
    if choice == "1":
        asyncio.run(_run_phone_full(phone))
    elif choice == "2":
        asyncio.run(_run_phone_only(phone))
    elif choice == "3":
        asyncio.run(_run_anti_scam(phone))
    elif choice == "4":
        asyncio.run(_run_guided(phone))
    else:
        term.print_error("Invalid choice.")


def _get_choice(prompt_range: str) -> str:
    choice = input(f"  Choose ({prompt_range}): ").strip().lower()
    return choice


# ============================================================
#  MODE ROUTINES
# ============================================================

async def _run_full(username: str):
    from stalker.pipeline import run_investigation, save_report
    from stalker.modules import auto_chaining
    result = await run_investigation(username, enable_exif=True, enable_dork=True)
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(username, result, saved)
    await auto_chaining.ask_follow_up(result, username)


async def _run_quick(username: str):
    from stalker.pipeline import run_investigation, save_report
    from stalker.modules import auto_chaining
    result = await run_investigation(username,
        enable_exif=False, enable_dork=False, max_sites=100,
        skip_face_search=True, skip_reverse=True, skip_recursive=True, skip_social=True,
    )
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(username, result, saved)
    await auto_chaining.ask_follow_up(result, username)


async def _run_telegram(username: str):
    from stalker.modules import telegram_profiler
    from stalker.pipeline import save_report

    term.print_phase(1, "Telegram Profiler", f"Looking up @{username} on Telegram...")
    tg = await telegram_profiler.profile(username)

    result = _empty_result(username)
    result["telegram"] = tg
    result["summary"].update(
        telegram_found=1 if tg.get("success") else 0,
        telegram_display=tg.get("display_name", ""),
    )
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(username, result, saved)


async def _run_dork_only(username: str):
    from stalker.pipeline import run_dork_pipeline, save_report
    result = await run_dork_pipeline(username)
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(username, result, saved)


async def _run_email(email: str):
    from stalker.modules import email_scanner, breach_check
    from stalker.pipeline import save_report

    term.print_phase(1, "Email Scanner", f"Checking {email} across 30+ platforms...")
    results = await email_scanner.scan_email(email)
    s = email_scanner.summary(results)

    term.print_phase(2, "Breach Check", "Querying Hudson Rock...")
    hr = await breach_check.check_hudson_rock(email=email)

    result = _empty_result(email)
    result["email_scan"] = results
    result["breach"] = hr
    result["summary"].update(
        profiles_found=s["registered_count"],
        sites_checked=s["platforms_checked"],
        platforms=s["registered_platforms"],
        email_registered=s["registered_count"],
        breach_hudson_rock=hr.get("email", {}).get("total_infections", 0),
    )
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(email, result, saved)


async def _run_email_full(email: str):
    from stalker.modules import email_scanner, breach_check, google_dork
    from stalker.modules import auto_chaining
    from stalker.pipeline import save_report

    term.print_phase(1, "Email Scanner", f"Checking {email} across 30+ platforms...")
    results = await email_scanner.scan_email(email)
    s = email_scanner.summary(results)

    term.print_phase(2, "Breach Check", "Querying Hudson Rock...")
    hr = await breach_check.check_hudson_rock(email=email)

    username_part = email.split("@")[0]
    dork_results = {}
    try:
        term.print_phase(3, "Smart Dork", f"Dorking with {username_part}...")
        dork_results = await google_dork.smart_dork({
            "username": username_part, "real_names": [username_part],
            "found_sites": [], "custom_profiles": {},
        })
    except Exception:
        pass

    result = _empty_result(email)
    result["email_scan"] = results
    result["breach"] = hr
    result["google_dork"] = dork_results
    result["summary"].update(
        profiles_found=s["registered_count"],
        sites_checked=s["platforms_checked"],
        platforms=s["registered_platforms"],
        email_registered=s["registered_count"],
        breach_hudson_rock=hr.get("email", {}).get("total_infections", 0),
        dork_names_searched=list(dork_results.keys()),
    )
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(email, result, saved)
    await auto_chaining.ask_follow_up(result, email)


async def _run_email_breach_dork(email: str):
    from stalker.modules import breach_check, google_dork
    from stalker.pipeline import save_report

    term.print_phase(1, "Breach Check", "Querying Hudson Rock...")
    hr = await breach_check.check_hudson_rock(email=email)

    username_part = email.split("@")[0]
    term.print_phase(2, "Smart Dork", f"Dorking with {username_part}...")
    dork_results = await google_dork.smart_dork({
        "username": username_part, "real_names": [username_part],
        "found_sites": [], "custom_profiles": {},
    })

    result = _empty_result(email)
    result["breach"] = hr
    result["google_dork"] = dork_results
    result["summary"].update(
        breach_hudson_rock=hr.get("email", {}).get("total_infections", 0),
        dork_names_searched=list(dork_results.keys()),
    )
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(email, result, saved)


async def _run_face_search(username: str):
    from stalker.modules import custom_apis, face_search
    from stalker.pipeline import save_report, _run_maigret

    term.print_phase(1, "Quick Search", f"Finding avatars for {username}...")
    maigret_data = await _run_maigret(username, max_sites=100)
    avatar_urls = maigret_data.get("avatar_urls", [])

    if not avatar_urls:
        custom_results = await custom_apis.search_all_platforms(username)
        for data in custom_results.values():
            if data.get("avatar_url"):
                avatar_urls.append(data["avatar_url"])

    term.print_phase(2, "Face Search", f"5 engines on {len(avatar_urls[:3])} avatars...")
    fs_results = await face_search.search_all_engines(avatar_urls)

    result = _empty_result(username)
    result["maigret"] = maigret_data
    result["face_search"] = fs_results
    fs = face_search.summary(fs_results)
    result["summary"].update(
        profiles_found=len(maigret_data.get("found_sites", [])),
        sites_checked=maigret_data.get("total_checked", 0),
        avatars_found=len(avatar_urls),
        face_search_engines=fs.get("engines_used", {}),
        face_search_pages=fs.get("total_pages_found", 0),
    )
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(username, result, saved)


async def _run_phone_full(phone: str):
    from stalker.modules import phone_scanner, breach_check, anti_scammer
    from stalker.modules import auto_chaining
    from stalker.pipeline import save_report

    term.print_phase(1, "Phone Analysis", f"Analyzing {phone}...")
    full = await phone_scanner.full_scan(phone)

    term.print_phase(2, "Breach Check", "Querying Hudson Rock...")
    hr = await breach_check.check_hudson_rock(username=phone)

    result = _empty_result(phone)
    result["phone_scan"] = full["platforms"]
    result["breach"] = hr
    result["anti_scam"] = anti_scammer.exposure_report(full)

    analysis = full.get("analysis", {})
    result["summary"].update(
        phone_registered=phone_scanner.summary(full["platforms"])["registered_count"],
        platforms=phone_scanner.summary(full["platforms"])["registered_platforms"],
        sites_checked=len(full["platforms"]),
        breach_hudson_rock=hr.get("username", {}).get("total_infections", 0),
        phone_carrier=analysis.get("carrier", "?"),
        phone_country=analysis.get("country", "?"),
    )
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(phone, result, saved)
    await auto_chaining.ask_follow_up(result, phone)


async def _run_anti_scam(phone: str):
    from stalker.modules import phone_scanner, anti_scammer
    from stalker.pipeline import save_report

    term.print_phase(1, "Phone Analysis", f"Analyzing {phone}...")
    full = await phone_scanner.full_scan(phone)

    term.print_phase(2, "Anti-Scam", "Generating report + evidence...")
    evidence = anti_scammer.exposure_report(full)
    warning = anti_scammer.generate_warning_message(full)

    print()
    term.print_divider()
    term.print_header("ANTI-SCAM REPORT")
    print()
    a = full.get("analysis", {})
    print(f"  Phone    : {a.get('international', phone)}")
    print(f"  Carrier  : {a.get('carrier', '?')}")
    print(f"  Country  : {a.get('country', '?')}")
    print(f"  Line Type: {a.get('line_type', '?')}")
    print()

    tc = full.get("truecaller", {})
    if tc.get("name"):
        term.print_warning(f"  Truecaller name: {tc['name']}")

    for p in full.get("platforms", []):
        if p.get("registered"):
            term.print_success(f"  {p['platform']}: Registered")
        else:
            term.print_warning(f"  {p['platform']}: Not Found")

    print()
    print(warning)
    print()
    term.print_divider()
    print("  Report Links:")
    for r in evidence["report_links"]:
        print(f"    {r['action']}: {r['url'][:70]}")

    try:
        import webbrowser
        for r in evidence["report_links"][:3]:
            webbrowser.open(r["url"])
    except Exception:
        pass

    result = _empty_result(phone)
    result["phone_scan"] = full["platforms"]
    result["anti_scam"] = evidence
    result["summary"].update(
        phone_registered=phone_scanner.summary(full["platforms"])["registered_count"],
        phone_carrier=a.get("carrier", "?"),
    )
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(phone, result, saved)


async def _run_phone_only(phone: str):
    from stalker.modules import phone_scanner
    from stalker.pipeline import save_report

    term.print_phase(1, "Phone Scanner", f"Checking {phone} across 6 platforms...")
    ps_results = await phone_scanner.scan_phone(phone)
    ps = phone_scanner.summary(ps_results)

    result = _empty_result(phone)
    result["phone_scan"] = ps_results
    result["summary"].update(
        phone_registered=ps["registered_count"],
        platforms=ps["registered_platforms"],
        sites_checked=ps["platforms_checked"],
    )
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(phone, result, saved)


async def _run_guided(username: str):
    from stalker.pipeline import run_investigation, save_report

    print()
    print("  Select modules to enable (y/n):")
    print()

    mods = {
        "enable_exif": ("EXIF Metadata", False),
        "enable_dork": ("Smart Dork", True),
        "skip_face_search": ("Face Search", False),
        "skip_reverse": ("Reverse Image", False),
        "skip_recursive": ("Recursive Search", False),
        "skip_social": ("Social Graph", False),
    }
    kwargs = {"max_sites": 100}
    for key, (label, default) in mods.items():
        ans = input(f"  {label}? [{'Y' if not default else 'y'}/{'n' if not default else 'N'}]: ").strip().lower()
        kwargs[key] = ans not in ("n", "no") if not default else ans not in ("y", "yes")

    result = await run_investigation(username, **kwargs)
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(username, result, saved)


# ============================================================
#  NEW MODULES ROUTINES (Linktree, Pastebin, WHOIS)
# ============================================================

async def _run_linktree(username: str):
    from stalker.modules import linktree_detector
    from stalker.pipeline import save_report
    result = _empty_result(username)
    link_data = await linktree_detector.check_link_aggregators(username)
    result["link_aggregators"] = link_data
    found = [k for k, v in link_data.items() if v.get("links")]
    result["summary"]["link_aggregators_found"] = found
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(username, result, saved)


async def _run_pastebin(username: str):
    from stalker.modules import pastebin_scraper
    from stalker.pipeline import save_report
    result = _empty_result(username)
    paste_data = await pastebin_scraper.pastebin_scan(username)
    result["pastebin"] = paste_data
    result["summary"]["pastebin_urls"] = paste_data.get("urls", [])
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(username, result, saved)


async def _run_whois(email: str):
    from stalker.modules import whois_checker
    from stalker.pipeline import save_report
    result = _empty_result(email)
    whois_data = await whois_checker.check_domain(email)
    result["whois"] = whois_data
    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(email, result, saved)


# ============================================================
#  HELPER
# ============================================================

def _empty_result(username: str) -> dict:
    import datetime
    return {
        "username": username,
        "timestamp": datetime.datetime.now().isoformat(),
        "maigret": {"found_sites": [], "total_checked": 0},
        "custom_apis": {},
        "exif": {},
        "google_dork": {},
        "reverse_image": {},
        "face_search": {},
        "recursive": {},
        "breach": {},
        "email_scan": {},
        "telegram": {},
        "text_profile": {},
        "phone_scan": {},
        "password_leak": {},
        "social_graph": None,
        "images": [],
        "link_aggregators": {},
        "pastebin": {},
        "whois": {},
        "summary": {"username": username, "profiles_found": 0, "sites_checked": 0,
                     "platforms": [], "real_names_found": [], "avatars_found": 0,
                     "duration": "0s"},
        "duration_seconds": 0,
    }


def _clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


if __name__ == "__main__":
    try:
        show_menu()
    except KeyboardInterrupt:
        print("\n\n  Aborted.\n")
        sys.exit(0)


# ============================================================
#  NEW v2.0 MODES (append to existing menu flow)
# ============================================================

async def _run_ip_tracker(ip_or_text: str):
    from stalker.modules.ip_tracker import track_ip, get_my_ip, extract_ips_from_text
    from stalker.pipeline import save_report
    from stalker.reporters import terminal as term

    ips = extract_ips_from_text(ip_or_text)
    if not ips:
        if ip_or_text.lower() in ("me", "myip"):
            ip_or_text = await get_my_ip()
            ips = [ip_or_text]
        else:
            ips = [ip_or_text.strip()]

    term.print_phase(1, "IP Tracker", f"Investigating {len(ips)} IP(s)...")
    for ip in ips[:5]:
        result = await track_ip(ip)
        term.print_divider()
        print(f"\n  IP       : {ip}")
        print(f"  Country  : {result.get('country','?')} ({result.get('country_code','?')})")
        print(f"  Region   : {result.get('region','?')}")
        print(f"  City     : {result.get('city','?')}")
        print(f"  ISP      : {result.get('isp','?')}")
        print(f"  ASN      : {result.get('asn','?')}")
        if result.get('geo_confidence'):
            print(f"  Geo conf : {result['geo_confidence']} (konsensus 8 sumber)")
        if result.get('geo_note'):
            print(f"  Geo note : {result['geo_note']}")
        if result.get('is_proxy'):
            term.print_warning("  ⚠  Proxy/VPN detected!")
        if result.get('shodan', {}).get('open_ports'):
            print(f"  Ports    : {', '.join(str(p) for p in result['shodan']['open_ports'])}")
        if result.get('shodan', {}).get('vulns'):
            term.print_warning(f"  CVEs     : {', '.join(result['shodan']['vulns'][:3])}")
        rev = result.get('reverse_ip', {})
        if rev.get('count'):
            doms = rev['domains'][:8]
            more = f" +{rev['count'] - 8}" if rev['count'] > 8 else ""
            print(f"  ReverseIP: {', '.join(doms)}{more}")
        if result.get('threat', {}).get('listed'):
            term.print_warning("  ⚠  IP ada di daftar CINS Army (berbahaya)")
        if result.get('map_url'):
            print(f"  Map      : {result['map_url']}")
        print()


async def _run_username_variants(username: str):
    from stalker.modules.username_variants import generate_variants
    from stalker.reporters import terminal as term

    term.print_phase(1, "Username Variants", f"Generating permutations for '{username}'...")
    variants = generate_variants(username, max_variants=100)
    term.print_success(f"Generated {len(variants)} variants")
    print()
    for i, v in enumerate(variants, 1):
        print(f"  {i:>3}. {v}")
    print()

    do_search = input("  Search top 5 variants in Maigret? (y/n): ").strip().lower()
    if do_search == 'y':
        from stalker.pipeline import _run_maigret
        for v in variants[1:6]:
            term.print_warning(f"\n  Searching: {v}...")
            data = await _run_maigret(v, max_sites=100)
            found = len(data.get("found_sites", []))
            if found:
                term.print_success(f"  {v}: {found} profiles found!")
            else:
                term.print_warning(f"  {v}: not found")


async def _run_darkweb_check(query: str, query_type: str = "email"):
    from stalker.modules.dark_web_checker import full_darkweb_check, summary as dw_summary
    from stalker.reporters import terminal as term

    term.print_phase(1, "Dark Web Check", f"Searching paste sites + breach databases...")
    results = await full_darkweb_check(query, query_type)
    s = dw_summary(results)

    if s["sources_found"] > 0:
        term.print_warning(f"\n  FOUND in {s['sources_found']} dark web source(s)! ({s['total_records']} records)")
        for source_name in s["found_in"]:
            data = results.get(source_name, {})
            print(f"    ✓ {source_name}: {data.get('count','?')} record(s)")
            for p in data.get("pastes", [])[:2]:
                print(f"      → {p.get('url', '-')}")
    else:
        term.print_success(f"\n  Not found in {s['sources_checked']} dark web sources checked")


def show_ip_menu():
    """Standalone IP tracker menu."""
    ip = input("\n  Enter IP address (or 'me' for your IP): ").strip()
    if ip:
        asyncio.run(_run_ip_tracker(ip))


def show_iplogger_menu():
    """Standalone IP Logger — tracking link to capture a target's IP silently."""
    from stalker.modules.ip_logger import run_ip_logger
    from stalker.reporters import terminal as term

    print("\n  IP LOGGER — tangkap IP target saat mereka klik link")
    print("  [1] Redirect + LIVE — redirect ke URL, tetap ping tiap 15s sambil terbuka")
    print("  [2] Halaman HTML custom (mis. 'loading...', fake login)")
    print("  [3] Pixel 1x1 (untuk email tracking)")
    print()
    choice = input("  Pilih decoy [1]: ").strip() or "1"
    redirect_url = None
    page_html = None
    pixel = False
    live = False

    if choice == "1":
        live = True
        redirect_url = input(
            "  URL redirect (kosong = default): ").strip() or \
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    elif choice == "2":
        page_html = input("  HTML (kosong = default): ").strip() or (
            "<!doctype html><html><body style='background:#000;color:#fff;"
            "font-family:sans-serif;display:flex;align-items:center;"
            "justify-content:center;height:100vh;margin:0'>"
            "<h1>Loading…</h1></body></html>")
    else:
        pixel = True

    port_raw = input("  Port [8080]: ").strip() or "8080"
    try:
        port = int(port_raw)
    except ValueError:
        port = 8080

    term.print_header("IP LOGGER — TRACKING LINK")
    print()

    async def _run():
        try:
            await run_ip_logger(port=port, redirect_url=redirect_url,
                                page_html=page_html, pixel=pixel, live=live,
                                public_tunnel=True)
        except OSError as e:
            term.print_error(f"Port {port} tidak bisa dipakai: {e}")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\n  Logger dihentikan.")


def show_new_osint_menu(key: str):
    """Menu dispatcher 10 fitur OSINT baru (reuse output CLI stalker)."""
    from stalker.reporters import terminal as term
    tools = {
        "k": ("NIK/KTP lookup", "NIK 16 digit", "nik"),
        "q": ("QR/barcode decoder", "path file / URL gambar", "qr"),
        "w": ("E-wallet OSINT", "nomor HP (08xx)", "ewallet"),
        "o": ("Status online checker", "username Telegram / nomor HP", "online"),
        "h": ("Phone HLR lookup", "nomor HP", "hlr"),
        "r": ("Reverse email", "alamat email", "revemail"),
        "b": ("Gaming OSINT", "username", "gaming"),
        "s": ("IG/TikTok deep OSINT", "username", "social"),
        "v": ("Exposed device search", "alamat IP", "device"),
        "x": ("Visual geolocation", "path file / URL gambar", "geolocate"),
    }
    label, hint, cmd = tools.get(key, (None, None, None))
    if not label:
        term.print_error("Pilihan tidak dikenal.")
        return
    target = input(f"\n  {label} — target ({hint}): ").strip()
    if not target:
        term.print_error("Input kosong.")
        return
    import subprocess
    subprocess.run([sys.executable, "-m", "stalker.cli", cmd, target])


async def _run_real_name(full_name: str):
    """Investigate a person by real name (variants + dork queries)."""
    from stalker.modules.real_name_detector import (
        process_real_name_input, generate_name_search_queries,
    )
    term.print_phase(1, "Real Name Detection", f"Analyzing '{full_name}'...")
    res = await process_real_name_input(full_name)
    if not res.get("is_real_name"):
        term.print_warning(f"  '{full_name}' doesn't look like a real name.")
        return
    parts = res.get("name_parts", {})
    variants = res.get("search_variants", [])
    queries = await generate_name_search_queries(full_name)
    term.print_divider()
    term.print_header("REAL NAME REPORT")
    print(f"\n  Name     : {full_name}")
    print(f"  First    : {', '.join(parts.get('first', []) or ['-'])}")
    print(f"  Last     : {', '.join(parts.get('last', []) or ['-'])}")
    print(f"  Variants : {len(variants)}")
    print()
    for v in variants[:20]:
        print(f"    • {v}")
    print(f"\n  Google Dork queries:")
    for q in queries.get("fullname", []):
        print(f"    • {q}")
    print()


def show_name_menu():
    """Standalone real-name investigation menu."""
    name = input("\n  Enter full name (e.g., 'Zell Ishikawa'): ").strip()
    if name:
        asyncio.run(_run_real_name(name))


def show_monitor_menu():
    """Standalone target monitor menu (GitHub/Reddit/Pastebin alerts)."""
    from stalker.modules.realtime_monitor import monitor_once, monitor_loop
    target = input("\n  Enter target (username/email/phone): ").strip()
    if not target:
        return
    ttype = ("email" if "@" in target and "." in target.split("@")[-1]
             else "phone" if target.replace(" ", "").replace("-", "").replace("+", "").isdigit()
             else "username")
    once = input("  One-time check (y) or continuous loop (n)? [n]: ").strip().lower()
    if once == "y":
        asyncio.run(monitor_once(target, ttype))
    else:
        interval = input("  Check interval in minutes [30]: ").strip() or "30"
        asyncio.run(monitor_loop(target, ttype, int(interval)))


def show_leak_menu():
    """Standalone password leak check menu (Pwned Passwords, k-anonymity)."""
    from stalker.modules.password_leak import check_password_leak, check_from_text
    pw = input("\n  Enter password (or paste text to scan): ").strip()
    if not pw:
        return

    async def _run():
        term.print_phase(1, "Password Leak Check", "Checking against Pwned Passwords...")
        term.print_divider()
        term.print_header("PASSWORD LEAK REPORT")
        if " " in pw or len(pw) > 40:
            res = await check_from_text(pw)
            print(f"\n  Kandidat dicek: {len(res.get('details', []))}")
            for d in res.get("details", []):
                hint = d.get("password_hint", "***")
                if d.get("found"):
                    term.print_warning(f"  ⚠  '{hint}' bocor {d['count']:,} kali")
                elif d.get("error"):
                    print(f"  ?  '{hint}' gagal: {d['error']}")
                else:
                    print(f"  ✓  '{hint}' tidak ditemukan")
        else:
            res = await check_password_leak(pw)
            if res.get("found"):
                term.print_warning(f"\n  ⚠  Password BOCOR — muncul {res['count']:,} kali di data breach!")
            elif res.get("error"):
                term.print_error(f"\n  Gagal: {res['error']}")
            else:
                term.print_success("\n  ✓ Password tidak ditemukan di breach.")
        print()

    asyncio.run(_run())


async def _run_cyber_intel_full(target: str, input_type: str):
    """Run full cyber intelligence suite after base investigation."""
    from stalker.pipeline import run_investigation, save_report
    from stalker.cyber_intel import run_cyber_intel
    from stalker.modules.termux_tools import post_investigation_notify

    term.print_phase(1, "Base Investigation", f"Running standard pipeline for {target}...")
    result = await run_investigation(target, enable_exif=True, enable_dork=True)

    term.print_phase(2, "Cyber Intelligence", "Running advanced intel modules...")
    result = await run_cyber_intel(result, input_type=input_type)

    saved = await save_report(result, formats=["json", "html"])
    if IS_TERMUX and saved:
        await _telegram_send(target, result, saved)
    await post_investigation_notify(target, result.get("summary", {}), saved)


def _username_menu_v2(username: str):
    print("  [1] Full Investigation       — All modules (comprehensive)")
    print("  [2] Quick Profile            — Username + APIs + Breach + Telegram")
    print("  [3] Deep Telegram            — Telegram profiler only")
    print("  [4] Smart Dork Only          — Quick search -> Dork -> Report")
    print("  [5] Face Search              — 5 engines on avatar")
    print("  [6] Guided Mode              — Pick specific modules")
    print("  [7] Linktree/Bio.site/Carrd  — Check link aggregators")
    print("  [8] Pastebin Leak Check      — Search pastebin/justpaste")
    print("  [9] Username Variants        — Generate + search permutations")
    print("  [C] CYBER INTEL MODE         — Full suite: GitHub + Reddit + Gravatar")
    print("                                 Wayback + Correlation + Timeline + Risk Score")
    print("  [p] Show pipeline diagrams")
    print()
    choice = input("  Choose: ").strip().lower()

    mode_map = {
        "1": lambda: asyncio.run(_run_full(username)),
        "2": lambda: asyncio.run(_run_quick(username)),
        "3": lambda: asyncio.run(_run_telegram(username)),
        "4": lambda: asyncio.run(_run_dork_only(username)),
        "5": lambda: asyncio.run(_run_face_search(username)),
        "7": lambda: asyncio.run(_run_linktree(username)),
        "8": lambda: asyncio.run(_run_pastebin(username)),
        "9": lambda: asyncio.run(_run_username_variants(username)),
        "c": lambda: asyncio.run(_run_cyber_intel_full(username, "username")),
    }
    if choice == "p":
        print(PIPELINE_FULL); print(PIPELINE_QUICK); input("  Press Enter..."); return
    if choice == "6":
        asyncio.run(_run_guided(username)); return
    fn = mode_map.get(choice)
    if fn: fn()
    else: term.print_error("Invalid choice.")


def _email_menu_v2(email: str):
    print("  [1] Full Investigation       — Email Scanner + Breach + Dark Web + Dork")
    print("  [2] Email Scanner Only       — 30+ platforms")
    print("  [3] Breach Check + Dork      — Hudson Rock + Smart Dork")
    print("  [4] Dark Web Only            — Paste sites + breach DBs")
    print("  [5] Domain WHOIS Check       — WHOIS + CRT.sh")
    print("  [6] Guided Mode              — Pick specific modules")
    print("  [C] CYBER INTEL MODE         — Email Intel + Gravatar + CRT.sh")
    print("                                 Correlation + Timeline + Risk Score")
    print()
    choice = input("  Choose: ").strip().lower()

    if choice == "1": asyncio.run(_run_email_full(email))
    elif choice == "2": asyncio.run(_run_email(email))
    elif choice == "3": asyncio.run(_run_email_breach_dork(email))
    elif choice == "4": asyncio.run(_run_darkweb_check(email, "email"))
    elif choice == "5": asyncio.run(_run_whois(email))
    elif choice == "6": asyncio.run(_run_guided(email))
    elif choice == "c": asyncio.run(_run_cyber_intel_full(email, "email"))
    else: term.print_error("Invalid choice.")


def _phone_menu_v2(phone: str):
    print("  [1] Phone Investigation      — Phone Scanner (6 platforms) + Full Intel")
    print("  [2] Phone Scanner Only       — Check 6 social platforms")
    print("  [3] Anti-Scam Toolkit        — Report + expose scammer")
    print("  [4] Guided Mode              — Pick specific modules")
    print("  [C] CYBER INTEL MODE         — Full Intel + Correlation + Risk Score")
    print()
    choice = input("  Choose: ").strip().lower()

    if choice == "1": asyncio.run(_run_phone_full(phone))
    elif choice == "2": asyncio.run(_run_phone_only(phone))
    elif choice == "3": asyncio.run(_run_anti_scam(phone))
    elif choice == "4": asyncio.run(_run_guided(phone))
    elif choice == "c": asyncio.run(_run_cyber_intel_full(phone, "phone"))
    else: term.print_error("Invalid choice.")


def show_menu_v2():
    """Enhanced v2.0 menu with Cyber Intel Mode."""
    # Gate: database GeoIP wajib diunduh dulu sebelum akses
    try:
        from modules.geoip_local import require_geoip
        if not require_geoip():
            sys.exit(1)
    except ImportError:
        pass

    while True:
        _clear_screen()
        term.print_banner()
        term.print_divider()
        print()
        print("  [u] Update Maigret database")
        print("  [i] Track an IP address")
        print("  [g] IP Logger (tracking link)")
        print("  [n] Search by real name")
        print("  [m] Monitor a target")
        print("  [l] Check password leak")
        print("  [k] NIK/KTP lookup         [q] QR/barcode decoder")
        print("  [w] E-wallet OSINT         [o] Status online checker")
        print("  [h] Phone HLR lookup       [r] Reverse email")
        print("  [b] Gaming OSINT           [s] IG/TikTok deep")
        print("  [v] Exposed device search  [x] Visual geolocation")
        print()
        value = input("  Enter username, email, or phone (or 'exit'): ").strip()
        if value.lower() in ("exit", "quit", "0"):
            print("\n  Goodbye!"); break
        if value.lower() == "u":
            os.system("python -m maigret --update-db")
            input("  Update complete. Press Enter..."); continue
        if value.lower() == "i":
            show_ip_menu(); input("  Press Enter..."); continue
        if value.lower() == "g":
            show_iplogger_menu(); input("  Press Enter..."); continue
        if value.lower() == "n":
            show_name_menu(); input("  Press Enter..."); continue
        if value.lower() == "m":
            show_monitor_menu(); input("  Press Enter..."); continue
        if value.lower() == "l":
            show_leak_menu(); input("  Press Enter..."); continue
        if value.lower() in ("k", "q", "w", "o", "h", "r", "b", "s", "v", "x"):
            show_new_osint_menu(value.lower()); input("  Press Enter..."); continue
        if not value:
            term.print_error("Input required!"); input("  Press Enter..."); continue

        is_email = "@" in value and "." in value.split("@")[-1]
        is_phone = bool(PHONE_RE.match(value.replace(" ","").replace("-","")))
        input_type = "PHONE" if is_phone else "EMAIL" if is_email else "USERNAME"
        print(f"\n  Detected: {input_type}")
        print()

        if is_phone: _phone_menu_v2(value)
        elif is_email: _email_menu_v2(value)
        else: _username_menu_v2(value)

        print(); input("  Press Enter to return to main menu...")


async def _run_whatsapp_intel(phone: str):
    """Standalone WhatsApp intelligence for a phone number."""
    from stalker.modules.whatsapp_intel import full_whatsapp_intel, format_wa_report
    from stalker.modules.stealth_reporter import save_full_report
    term.print_phase(1, "WhatsApp Intel", f"Investigating {phone}...")
    data = await full_whatsapp_intel(phone)
    print(format_wa_report(data))
    saved = await save_full_report({"phone": phone, "whatsapp_intel": data}, output_dir="output")
    if saved.get("json"):     term.print_success(f"  Saved: {saved['json']}")
    if saved.get("markdown"): term.print_success(f"  Saved: {saved['markdown']}")
