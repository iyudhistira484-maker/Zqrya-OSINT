"""Stalker CLI - OSINT All-in-One Investigation Tool.

Usage:
    stalker search <username> [--exif] [--dork] [--output json|html]
    stalker quick <username>
    stalker exif <path_or_url>
    stalker dork <name> [--categories ...]
    stalker email <email>
    stalker phone <phone>
    stalker ip <ip>
    stalker variants <username>
    stalker darkweb <query>
    stalker name <full_name>
    stalker monitor <target> [--interval N] [--once]
    stalker leak <password>
    stalker reverseip <ip>
    stalker iplogger [--redirect URL] [--page HTML] [--pixel]
    stalker nik <16-digit-nik>
    stalker qr <file-or-url>
    stalker ewallet <phone>
    stalker online <target> [--type auto|telegram|phone]
    stalker hlr <phone>
    stalker revemail <email>
    stalker gaming <username>
    stalker social <username>
    stalker device <ip>
    stalker geolocate <file-or-url>
    stalker menu
"""

import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import click
except ImportError:
    print("Click not installed. Run: pip install click")
    print("Or use the interactive menu: python -m stalker.menu")
    sys.exit(1)


@click.group()
@click.version_option(version="2.0.0", prog_name="stalker")
def cli():
    """Zqrya — OSINT All-in-One Investigation Tool.
    
    \b
    Examples:
      stalker search johndoe
      stalker email test@gmail.com
      stalker phone +62812345678
      stalker ip 8.8.8.8
      stalker variants johndoe
      stalker darkweb test@gmail.com
    """
    # Gate: database GeoIP wajib diunduh dulu sebelum akses
    try:
        from modules.geoip_local import require_geoip
        if not require_geoip():
            sys.exit(1)
    except ImportError:
        pass


@cli.command()
@click.argument("username")
@click.option("--exif/--no-exif", default=True, help="Enable EXIF metadata extraction")
@click.option("--dork/--no-dork", default=True, help="Enable Google Dork search")
@click.option("--output", "-o", multiple=True, default=["json", "html"],
              type=click.Choice(["json", "html"]), help="Output formats")
@click.option("--sites", "-s", default=None, type=int, help="Max sites to check")
@click.option("--variants/--no-variants", default=False, help="Also search username variants")
def search(username, exif, dork, output, sites, variants):
    """Run a full OSINT investigation on a username."""
    from stalker.pipeline import run_investigation, save_report
    from stalker.modules.termux_tools import post_investigation_notify

    async def _run():
        result = await run_investigation(
            username,
            enable_exif=exif,
            enable_dork=dork,
            max_sites=sites,
        )

        if variants:
            from stalker.modules.username_variants import generate_variants
            v = generate_variants(username, max_variants=20)
            click.echo(f"\n  Username variants ({len(v)} generated): {', '.join(v[:10])}")

        saved = []
        if output:
            saved = await save_report(result, formats=list(output))

        # Termux native notification
        await post_investigation_notify(username, result.get("summary", {}), saved)

    asyncio.run(_run())


@cli.command()
@click.argument("username")
def quick(username):
    """Quick username search only (100 sites, no EXIF/dork)."""
    from stalker.pipeline import run_quick_search

    async def _run():
        await run_quick_search(username)

    asyncio.run(_run())


@cli.command()
@click.argument("source")
def exif(source):
    """Extract EXIF metadata from image file or URL."""
    from stalker.pipeline import run_exif_only

    async def _run():
        await run_exif_only(source)

    asyncio.run(_run())


@cli.command()
@click.argument("name")
@click.option("--categories", "-c", multiple=True,
              help="Dork categories (linkedin, facebook, twitter, github, etc.)")
def dork(name, categories):
    """Search person by name using Google Dork queries."""
    from stalker.pipeline import run_dork_only

    cats = list(categories) if categories else None

    async def _run():
        await run_dork_only(name, cats)

    asyncio.run(_run())


@cli.command()
@click.argument("email_addr")
@click.option("--breach/--no-breach", default=True, help="Include breach check")
@click.option("--darkweb/--no-darkweb", default=True, help="Include dark web check")
@click.option("--output", "-o", multiple=True, default=["json", "html"],
              type=click.Choice(["json", "html"]))
def email(email_addr, breach, darkweb, output):
    """Scan email: 30+ platforms, breach, dark web check."""
    from stalker.modules import email_scanner, breach_check
    from stalker.modules.dark_web_checker import full_darkweb_check, summary as dw_summary
    from stalker.pipeline import save_report
    from stalker.reporters import terminal as term

    async def _run():
        term.print_phase(1, "Email Scanner", f"Checking {email_addr} across 30+ platforms...")
        results = await email_scanner.scan_email(email_addr)
        s = email_scanner.summary(results)
        term.print_success(f"Registered on {s['registered_count']}/{s['platforms_checked']} platforms")

        hr = {}
        if breach:
            term.print_phase(2, "Breach Check", "Querying Hudson Rock...")
            hr = await breach_check.check_hudson_rock(email=email_addr)

        dw = {}
        if darkweb:
            term.print_phase(3, "Dark Web Check", "Checking paste sites + breach DBs...")
            dw = await full_darkweb_check(email_addr, "email")
            dws = dw_summary(dw)
            if dws["sources_found"] > 0:
                term.print_warning(f"  Found in {dws['sources_found']} dark web sources ({dws['total_records']} records)")
            else:
                term.print_success(f"  Not found in dark web sources checked")

        from stalker.menu import _empty_result
        result = _empty_result(email_addr)
        result["email_scan"] = results
        result["breach"] = hr
        result["dark_web"] = dw
        result["summary"].update(
            email_registered=s["registered_count"],
            breach_hudson_rock=hr.get("email", {}).get("total_infections", 0),
        )
        if output:
            await save_report(result, formats=list(output))

    asyncio.run(_run())


@cli.command()
@click.argument("phone_number")
@click.option("--output", "-o", multiple=True, default=["json", "html"],
              type=click.Choice(["json", "html"]))
def phone(phone_number, output):
    """Scan phone number across 6+ platforms + carrier/geo analysis."""
    from stalker.modules import phone_scanner, breach_check
    from stalker.pipeline import save_report
    from stalker.reporters import terminal as term
    from stalker.menu import _empty_result

    async def _run():
        term.print_phase(1, "Phone Analysis", f"Analyzing {phone_number}...")
        full = await phone_scanner.full_scan(phone_number)
        a = full.get("analysis", {})
        term.print_success(f"Carrier: {a.get('carrier','?')} | Country: {a.get('country','?')} | Type: {a.get('line_type','?')}")

        plats = full.get("platforms", [])
        for p in plats:
            if p.get("registered"):
                term.print_warning(f"  ✓ {p['platform'].upper()}: Registered")

        term.print_phase(2, "Breach Check", "Querying Hudson Rock...")
        hr = await breach_check.check_hudson_rock(username=phone_number)

        result = _empty_result(phone_number)
        result["phone_scan"] = plats
        result["breach"] = hr
        result["summary"].update(
            phone_registered=phone_scanner.summary(plats)["registered_count"],
            phone_carrier=a.get("carrier", "?"),
            phone_country=a.get("country", "?"),
        )
        if output:
            await save_report(result, formats=list(output))

    asyncio.run(_run())


@cli.command()
@click.argument("ip_address")
@click.option("--shodan/--no-shodan", default=True, help="Include Shodan InternetDB check")
def ip(ip_address, shodan):
    """Geolocate IP + Shodan ports/vulns + reverse DNS (no API key needed)."""
    from stalker.modules.ip_tracker import track_ip, get_my_ip
    from stalker.reporters import terminal as term

    async def _run():
        target = ip_address
        if target in ("me", "myip", "self"):
            term.print_phase(1, "My IP", "Getting your public IP...")
            target = await get_my_ip()
            term.print_success(f"Your IP: {target}")

        term.print_phase(1, "IP Tracker", f"Investigating {target}...")
        result = await track_ip(target)

        term.print_divider()
        term.print_header(f"IP REPORT: {target}")
        print()
        fields = [
            ("Country", result.get("country", "?")),
            ("Region", result.get("region", "?")),
            ("City", result.get("city", "?")),
            ("ISP", result.get("isp", "?")),
            ("ASN", result.get("asn", "?")),
            ("Geo conf", result.get("geo_confidence", "")),
            ("Timezone", result.get("timezone", "?")),
            ("Reverse DNS", result.get("reverse_dns", "-")),
            ("Is Proxy/VPN", "YES" if result.get("is_proxy") else "No"),
            ("Is Hosting", "YES" if result.get("is_hosting") else "No"),
            ("Map", result.get("map_url", "-")),
        ]
        for label, val in fields:
            if val and val not in ("?", "-", ""):
                print(f"  {label:<15}: {val}")

        if result.get("geo_note"):
            print(f"  {'Geo note':<15}: {result['geo_note']}")

        shodan_data = result.get("shodan", {})
        if shodan_data.get("open_ports"):
            print(f"\n  {'Open Ports':<15}: {', '.join(str(p) for p in shodan_data['open_ports'])}")
        if shodan_data.get("vulns"):
            term.print_warning(f"  CVEs: {', '.join(shodan_data['vulns'][:5])}")
        if shodan_data.get("tags"):
            print(f"  {'Tags':<15}: {', '.join(shodan_data['tags'])}")

        rev = result.get("reverse_ip", {})
        if rev.get("count"):
            doms = rev["domains"][:10]
            more = f" +{rev['count'] - 10}" if rev['count'] > 10 else ""
            print(f"\n  {'Reverse IP':<15}: {', '.join(doms)}{more} ({rev['count']} domain)")

        threat = result.get("threat", {})
        if threat.get("listed"):
            term.print_warning("  ⚠  IP listed in CINS Army bad-guys list (malicious)")
        print()

    asyncio.run(_run())


@cli.command()
@click.argument("username")
@click.option("--max", "max_vars", default=50, help="Max variants to generate")
@click.option("--search/--no-search", default=False, help="Also search top variants in Maigret")
def variants(username, max_vars, search):
    """Generate username permutations for deeper OSINT searches."""
    from stalker.modules.username_variants import generate_variants
    from stalker.reporters import terminal as term

    vars_list = generate_variants(username, max_variants=max_vars)
    term.print_header(f"USERNAME VARIANTS: {username}")
    print()
    print(f"  Generated {len(vars_list)} variants:\n")
    for i, v in enumerate(vars_list, 1):
        print(f"  {i:>3}. {v}")
    print()

    if search:
        from stalker.pipeline import _run_maigret, save_report

        async def _run():
            term.print_phase(1, "Variant Search", f"Searching top 5 variants...")
            for v in vars_list[1:6]:
                term.print_warning(f"\n  Searching: {v}")
                data = await _run_maigret(v, max_sites=100)
                found = len(data.get("found_sites", []))
                term.print_success(f"  {v}: {found} profiles found")

        asyncio.run(_run())


@cli.command()
@click.argument("query")
@click.option("--type", "query_type", default="auto",
              type=click.Choice(["auto", "email", "username", "phone"]),
              help="Query type (auto-detected by default)")
def darkweb(query, query_type):
    """Check query against dark web paste sites and breach databases."""
    from stalker.modules.dark_web_checker import full_darkweb_check, summary as dw_summary
    from stalker.reporters import terminal as term

    async def _run():
        # Auto-detect type
        detected = query_type
        if detected == "auto":
            if "@" in query and "." in query:
                detected = "email"
            elif query.startswith("+") or query.replace("-", "").replace(" ", "").isdigit():
                detected = "phone"
            else:
                detected = "username"

        term.print_phase(1, "Dark Web Check", f"Checking {query} ({detected}) across paste/breach sites...")
        results = await full_darkweb_check(query, detected)
        s = dw_summary(results)

        term.print_divider()
        term.print_header("DARK WEB REPORT")
        print(f"\n  Query        : {query}")
        print(f"  Type         : {detected}")
        print(f"  Sources      : {s['sources_checked']} checked")
        print()

        if s["sources_found"] > 0:
            term.print_warning(f"  FOUND in {s['sources_found']} source(s)! ({s['total_records']} records)")
            for source_name in s["found_in"]:
                data = results.get(source_name, {})
                count = data.get("count", "?")
                print(f"    ✓ {source_name}: {count} record(s)")
                pastes = data.get("pastes", [])
                for p in pastes[:3]:
                    print(f"      → {p.get('url', '-')}")
                    if p.get("preview"):
                        print(f"        {p['preview'][:80]}...")
        else:
            term.print_success("  NOT found in any dark web source checked")

        print()

    asyncio.run(_run())


@cli.command()
def termux():
    """Show Termux setup guide and test Termux:API features."""
    from stalker.modules.termux_tools import is_available, setup_instructions, notify, vibrate, toast

    click.echo("\n  Termux:API Status:")
    if is_available():
        click.echo("  ✓ Termux:API is available — all features enabled")

        async def _test():
            click.echo("\n  Testing notifications...")
            ok1 = await notify("Zqrya", "Termux:API test — working!")
            ok2 = await vibrate(300)
            ok3 = await toast("Zqrya: API test OK", short=True)
            click.echo(f"  Notification: {'✓' if ok1 else '✗'}")
            click.echo(f"  Vibrate     : {'✓' if ok2 else '✗'}")
            click.echo(f"  Toast       : {'✓' if ok3 else '✗'}")

        import asyncio
        asyncio.run(_test())
    else:
        click.echo("  ✗ Termux:API not available")
        click.echo(setup_instructions())


@cli.command()
@click.argument("full_name")
def name(full_name):
    """Investigate a person by real name (variants + search queries)."""
    import asyncio
    from stalker.modules.real_name_detector import (
        process_real_name_input, generate_name_search_queries,
    )
    from stalker.reporters import terminal as term

    async def _run():
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
        if parts.get("middle"):
            print(f"  Middle   : {', '.join(parts['middle'])}")
        print(f"  Variants : {len(variants)}")
        print()
        for v in variants[:20]:
            print(f"    • {v}")
        print(f"\n  Google Dork queries:")
        for q in queries.get("fullname", []):
            print(f"    • {q}")
        if queries.get("variations"):
            print(f"\n  Variasi (untuk username scan):")
            for q in queries["variations"]:
                print(f"    • {q}")
        print()

    asyncio.run(_run())


@cli.command()
@click.argument("target")
@click.option("--type", "target_type", default="auto",
              type=click.Choice(["auto", "username", "email", "phone"]),
              help="Target type (auto-detected by default)")
@click.option("--interval", "interval_minutes", default=30, type=int,
              help="Minutes between checks (loop mode)")
@click.option("--once/--loop", default=False,
              help="Run a single check instead of continuous monitoring")
def monitor(target, target_type, interval_minutes, once):
    """Monitor a target for new activity (GitHub/Reddit/Pastebin) with alerts."""
    import asyncio
    from stalker.modules.realtime_monitor import monitor_once, monitor_loop

    if target_type == "auto":
        if "@" in target and "." in target.split("@")[-1]:
            target_type = "email"
        elif target.replace(" ", "").replace("-", "").replace("+", "").isdigit():
            target_type = "phone"
        else:
            target_type = "username"

    if once:
        asyncio.run(monitor_once(target, target_type))
    else:
        asyncio.run(monitor_loop(target, target_type, interval_minutes))


@cli.command()
@click.argument("input_text")
def leak(input_text):
    """Check a password (or text) against Pwned Passwords (k-anonymity)."""
    import asyncio
    from stalker.modules.password_leak import check_password_leak, check_from_text
    from stalker.reporters import terminal as term

    async def _run():
        term.print_phase(1, "Password Leak Check", "Checking against Pwned Passwords...")
        term.print_divider()
        term.print_header("PASSWORD LEAK REPORT")
        if " " in input_text or len(input_text) > 40:
            res = await check_from_text(input_text)
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
            res = await check_password_leak(input_text)
            if res.get("found"):
                term.print_warning(f"\n  ⚠  Password ini BOCOR — muncul {res['count']:,} kali di data breach!")
            elif res.get("error"):
                term.print_error(f"\n  Gagal: {res['error']}")
            else:
                term.print_success("\n  ✓ Password tidak ditemukan di breach (aman via Pwned).")
        print()

    asyncio.run(_run())


@cli.command()
@click.argument("ip_address")
def reverseip(ip_address):
    """Find domains hosted on the same IP (reverse IP lookup)."""
    import asyncio
    from stalker.modules.ip_intel import reverse_ip_lookup
    from stalker.reporters import terminal as term

    async def _run():
        term.print_phase(1, "Reverse IP Lookup", f"Finding domains on {ip_address}...")
        res = await reverse_ip_lookup(ip_address)
        term.print_divider()
        term.print_header("REVERSE IP REPORT")
        print(f"\n  IP       : {ip_address}")
        print(f"  Domains  : {res.get('count', 0)}")
        if res.get("note"):
            term.print_warning(f"  Note     : {res['note']}")
        print()
        for d in res.get("domains", [])[:25]:
            print(f"    • {d}")
        print()

    asyncio.run(_run())


@cli.command()
@click.option("--port", default=8080, type=int, help="Local port for the tracking server")
@click.option("--redirect", "redirect_url", default=None,
              help="Decoy: redirect the target to this URL after logging")
@click.option("--page", "page_html", default=None, help="Decoy: serve this custom HTML")
@click.option("--page-file", "page_file", default=None, help="Decoy: serve HTML from this file")
@click.option("--pixel/--no-pixel", default=False,
              help="Decoy: 1x1 transparent GIF (email tracking pixel)")
@click.option("--live/--no-live", default=False,
              help="Live tracking: page keeps pinging every 15s + movement alerts")
@click.option("--shorten/--no-shorten", default=True,
              help="Shorten the tracking link via is.gd/tinyurl")
@click.option("--public/--local-only", "public_tunnel", default=True,
              help="Try to expose publicly via localhost.run/serveo")
def iplogger(port, redirect_url, page_html, page_file, pixel, live, shorten, public_tunnel):
    """Generate a tracking link to capture a target's IP when they click it."""
    from stalker.modules.ip_logger import run_ip_logger
    from stalker.reporters import terminal as term

    if page_file:
        try:
            page_html = Path(page_file).read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            term.print_error(f"Cannot read --page-file: {e}")
            sys.exit(1)

    term.print_header("IP LOGGER — TRACKING LINK")
    print()
    if live:
        print("  Decoy   : LIVE TRACKING page (Loading…, ping tiap 15s)")
    elif redirect_url:
        print(f"  Decoy   : redirect -> {redirect_url}")
    elif page_html:
        print(f"  Decoy   : custom HTML page ({len(page_html)} chars)")
    else:
        print("  Decoy   : 1x1 tracking pixel (email)")
    print(f"  Port    : {port}")
    print()

    async def _run():
        try:
            await run_ip_logger(port=port, redirect_url=redirect_url,
                                page_html=page_html, pixel=pixel, live=live,
                                shorten=shorten, public_tunnel=public_tunnel)
        except OSError as e:
            term.print_error(f"Port {port} tidak bisa dipakai: {e}")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\n  Logger dihentikan.")


@cli.command()
@click.argument("nik")
def nik(nik):
    """Parse & validate Indonesian NIK/KTP (16 digit)."""
    from stalker.modules.nik_lookup import parse_nik, check_active
    from stalker.reporters import terminal as term

    async def _run():
        r = parse_nik(nik)
        term.print_header(f"NIK / KTP: {nik}")
        print(f"  Valid     : {'YES' if r.get('valid') else 'NO'}")
        print(f"  Gender    : {r.get('gender')}")
        print(f"  Lahir     : {r.get('birth_date')} (umur {r.get('age')})")
        print(f"  Provinsi  : {r.get('province')}")
        print(f"  Kab/Kota  : {r.get('kabupaten')}")
        print(f"  Kec kode  : {r.get('kec_code')}")
        print(f"  Serial    : {r.get('serial')}")
        if r.get('errors'):
            for e in r['errors']:
                term.print_warning(f"  ⚠ {e}")
        act = await check_active(nik)
        print(f"  Status    : {'aktif' if act.get('likely_active') else 'tidak valid'}")
        _show_nik_localdb(nik)
        print()
    asyncio.run(_run())


def _show_nik_localdb(nik: str):
    """Tampilkan nama & data dari DB lokal (SIAK/NPWP) bila tersedia."""
    try:
        from stalker.modules.localdb import search_by_nik, db_count
        hits = search_by_nik(nik)
        if hits:
            for db, rows in hits.items():
                for row in rows[:3]:
                    print(f"  Nama      : {row.get('name', '-')}  [{row.get('source', db)}]")
                    birth = row.get('birth_date') or row.get('birth')
                    if birth:
                        tempat = f" ({row.get('birth_place')})" if row.get('birth_place') else ""
                        print(f"  Lahir Db  : {birth}{tempat}")
                    if row.get('address'):
                        print(f"  Alamat    : {row.get('address')[:100]}")
                    if row.get('occupation'):
                        print(f"  Pekerjaan : {row.get('occupation')}")
                    if row.get('npwp'):
                        print(f"  NPWP      : {row.get('npwp')}")
        else:
            n = db_count()
            print(f"  Nama      : - (dicek {n} DB lokal)")
            if n == 0:
                from stalker.modules.localdb import db_dir_hint
                print(f"  Lokasi DB : {db_dir_hint()}")
                term.print_warning("  ⚠ Letakkan CSV SIAK/NPWP (nama kolom NIK) di folder itu agar nama muncul.")
    except Exception:
        pass


@cli.command()
@click.argument("nkk")
def nkk(nkk):
    """Parse & validate Nomor Kartu Keluarga (NKK, 16 digit) + anggota keluarga."""
    from stalker.modules.nkk_lookup import parse_nkk, check_active, search_family
    from stalker.reporters import terminal as term

    async def _run():
        r = parse_nkk(nkk)
        term.print_header(f"NKK / KARTU KELUARGA: {nkk}")
        print(f"  Valid     : {'YES' if r.get('valid') else 'NO'}")
        print(f"  Terbit    : {r.get('issue_date')}")
        print(f"  Provinsi  : {r.get('province')}")
        print(f"  Kab/Kota  : {r.get('kabupaten')}")
        print(f"  Kec kode  : {r.get('kec_code')}")
        print(f"  Serial    : {r.get('serial')}")
        if r.get('errors'):
            for e in r['errors']:
                term.print_warning(f"  ⚠ {e}")

        # Anggota keluarga dari DB lokal (SIAK dll) bila tersedia
        fam = search_family(nkk)
        total_members = sum(len(v) for v in fam.values())
        if total_members:
            print(f"\n  Anggota   : {total_members} orang")
            for db, rows in fam.items():
                for row in rows:
                    status = row.get('marital') or '?'
                    if status:
                        status = {'K': 'kawin', 'K0': 'kawin', 'K1': 'kawin', 'K2': 'kawin',
                                  'BK': 'belum kawin', 'CB': 'cerai hidup', 'C': 'cerai',
                                  'CT': 'cerai mati', 'D': 'mati'}.get(status.upper(), status)
                    print(f"  • {row.get('name', '?')}  | NIK {row.get('nik', '?')}"
                          f"  | {status}  | {row.get('gender') or '?'}")
                    if row.get('birth_date'):
                        print(f"      Lahir: {row.get('birth_date')} ({row.get('birth_place')})")
                    if row.get('occupation'):
                        print(f"      Pekerjaan: {row.get('occupation')}")
        else:
            try:
                from stalker.modules.localdb import db_count
                n = db_count()
            except Exception:
                n = 0
            print(f"\n  Anggota   : - (dicek {n} DB lokal — tidak ada data NKK)")
            term.print_warning("  ⚠ Data anggota keluarga hanya dari DB lokal (SIAK).")

        act = await check_active(nkk)
        print(f"  Status    : {'aktif (struktural)' if act.get('likely_active') else 'tidak valid'}")
        print(f"  Cek manual: {act['manual_check']['dukcapil']}")
        print()
    asyncio.run(_run())


@cli.command()
@click.argument("source")
def qr(source):
    """Decode QR/barcode from image file or URL."""
    from stalker.modules.qr_decoder import decode_and_expand
    from stalker.reporters import terminal as term

    async def _run():
        res = await decode_and_expand(source)
        term.print_header(f"QR DECODE: {source}")
        if res.get("error"):
            term.print_error(res["error"])
            return
        print(f"  Method    : {res.get('method')}")
        for item in res.get("decoded", []):
            print(f"  Type      : {item.get('type')}")
            print(f"  Data      : {item.get('raw')}")
            if item.get('ssid'):
                print(f"  WiFi      : SSID={item.get('ssid')} pass={item.get('password')}")
            if item.get('redirect'):
                print(f"  Final URL : {item['redirect'].get('final')}")
        print()
    asyncio.run(_run())


@cli.command()
@click.argument("phone")
def ewallet(phone):
    """Check phone on GoPay/OVO/DANA/ShopeePay + manual verify guide."""
    from stalker.modules.ewallet_osint import check_ewallets, manual_verify_guide
    from stalker.reporters import terminal as term

    async def _run():
        res = await check_ewallets(phone)
        term.print_header(f"E-WALLET OSINT: {phone}")
        print(f"  Nomor     : {res.get('national')}")
        print(f"  Carrier   : {res.get('carrier')}")
        if res.get('analysis'):
            a = res['analysis']
            if a.get('region') or a.get('province'):
                print(f"  Wilayah   : {' '.join(x for x in (a.get('region'), a.get('province')) if x)}")
        print()
        for w in res.get("ewallets", []):
            st = w['status']
            if st == 'unknown':
                st = 'belum diverifikasi (butuh cek manual)'
            print(f"  [{w['platform']}] {w['name']}: {st}")
        print()
        term.print_warning("  Status 'belum diverifikasi' = Zqrya tidak bisa cek langsung dari luar.")
        term.print_warning("  Satu-satunya cara andal: transfer nominal kecil → nama pemilik tampil.")
        print()
        print("  Panduan verifikasi (transfer kecil → cek nama):")
        for step in manual_verify_guide():
            print(f"    {step}")
        print()
    asyncio.run(_run())


@cli.command()
@click.argument("target")
@click.option("--type", "kind", default="auto", type=click.Choice(["auto", "telegram", "phone"]))
def online(target, kind):
    """Check online/last-seen status (Telegram public; WhatsApp privasi)."""
    from stalker.modules.status_online import check_status
    from stalker.reporters import terminal as term

    async def _run():
        res = await check_status(target, kind)
        term.print_header(f"STATUS ONLINE: {target}")
        exists = res.get('exists', res.get('account_exists'))
        print(f"  Ada       : {exists}")
        print(f"  Status    : {res.get('status') or '-'}")
        if res.get('display_name'):
            print(f"  Nama      : {res['display_name']}")
        if res.get('wa_link'):
            print(f"  WA link   : {res['wa_link']}")
        if res.get('note'):
            term.print_warning(f"  Catatan   : {res['note']}")
        if not exists and res.get('error'):
            term.print_warning(f"  Error     : {res['error']}")
        print()
    asyncio.run(_run())


@cli.command()
@click.argument("phone")
def hlr(phone):
    """HLR-style lookup: carrier/line-type/status (best-effort)."""
    from stalker.modules.phone_hlr import hlr_lookup
    from stalker.reporters import terminal as term

    async def _run():
        res = await hlr_lookup(phone)
        term.print_header(f"HLR LOOKUP: {phone}")
        print(f"  Valid     : {res.get('valid')}")
        print(f"  Carrier   : {res.get('carrier')}")
        print(f"  Line type : {res.get('line_type')}")
        print(f"  Country   : {res.get('country')}")
        print(f"  Location  : {res.get('location') or '-'}")
        print(f"  Live      : {res.get('live_status')}")
        print()
    asyncio.run(_run())


@cli.command()
@click.argument("email_addr")
def revemail(email_addr):
    """Reverse email: reputation + nama/telepon (data broker, best-effort)."""
    from stalker.modules.reverse_email import reverse_email_full
    from stalker.reporters import terminal as term

    async def _run():
        from stalker.modules.reverse_email import is_email
        if not is_email(email_addr):
            term.print_header(f"REVERSE EMAIL: {email_addr}")
            term.print_error("  ⚠ Format email tidak valid — cek lagi typo (contoh: user@gmail.com, bukan gmail.comm).")
            print()
            return
        res = await reverse_email_full(email_addr)
        term.print_header(f"REVERSE EMAIL: {email_addr}")
        rep = res.get("reputation", {})
        rep_label = rep.get('reputation') or '-'
        susp = rep.get('suspicious')
        if susp is True:
            susp_label = '⚠ YA'
        elif susp is False:
            susp_label = 'tidak'
        else:
            susp_label = '-'
        print(f"  Reputasi  : {rep_label}")
        print(f"  Suspicious: {susp_label}")
        print(f"  Nama      : {res.get('found_name') or '-'}")
        print(f"  Telepon   : {', '.join(res.get('found_phones', [])) or '-'}")
        wm = res.get("web_mentions") or {}
        if wm.get("mentions") is not None:
            print(f"  Sebutan web: {wm.get('mentions')} ({wm.get('engine','')})")
        if res.get('reputation_error'):
            term.print_warning(f"  ⚠ {res['reputation_error']}")
        if res.get('error'):
            term.print_warning(f"  Error     : {res['error']}")
        print("  Link cek  :")
        for l in res.get("manual_links", []):
            print(f"    {l['platform']}: {l['url']}")
        print()
    asyncio.run(_run())


@cli.command()
@click.argument("username")
def gaming(username):
    """Gaming OSINT: Steam + Roblox + Minecraft (keyless)."""
    from stalker.modules.gaming_osint import gaming_osint
    from stalker.reporters import terminal as term

    async def _run():
        res = await gaming_osint(username)
        term.print_header(f"GAMING OSINT: {username}")
        for k, v in res.get("platforms", {}).items():
            if v.get("found"):
                term.print_success(f"{k.upper()}: {v.get('display_name') or v.get('current_name')}")
                for field in ("steamID64", "user_id", "uuid", "friends_count", "member_since", "location"):
                    if v.get(field):
                        print(f"    {field}: {v[field]}")
            else:
                print(f"  {k.upper()}: not found {('(' + v.get('error','') + ')') if v.get('error') else ''}")
        print()
    asyncio.run(_run())


@cli.command()
@click.argument("username")
def social(username):
    """IG/TikTok deep OSINT: followers, bio, verified (best-effort)."""
    from stalker.modules.social_deep import social_deep
    from stalker.reporters import terminal as term

    async def _run():
        res = await social_deep(username)
        term.print_header(f"SOCIAL DEEP: {username}")
        for k, v in res.items():
            if k == "username" or not isinstance(v, dict):
                continue
            if v.get("found"):
                term.print_success(f"{k.upper()}: {v.get('nickname') or v.get('title')}")
                for field in ("followers", "following", "likes", "videos", "verified", "bio"):
                    if v.get(field) is not None:
                        print(f"    {field}: {v[field]}")
            else:
                print(f"  {k.upper()}: {v.get('error', 'not found')}")
        print()
    asyncio.run(_run())


@cli.command()
@click.argument("ip_address")
def device(ip_address):
    """Exposed device search: ports + device type + CVEs (Shodan InternetDB)."""
    from stalker.modules.exposed_device import scan_device
    from stalker.reporters import terminal as term

    async def _run():
        res = await scan_device(ip_address)
        term.print_header(f"EXPOSED DEVICE: {ip_address}")
        print(f"  Device    : {res.get('device_type')}")
        print(f"  Ports     : {', '.join(map(str, res.get('open_ports', []))) or '-'}")
        if res.get("services"):
            print(f"  Services  : {', '.join(res['services'][:10])}")
        if res.get("vulns"):
            term.print_warning(f"  CVEs      : {', '.join(res['vulns'][:5])}")
        if res.get("hints"):
            print(f"  Hint      : {', '.join(res['hints'][:5])}")
        print("  Links     :")
        for k, u in res.get("links", {}).items():
            print(f"    {k}: {u}")
        print()
    asyncio.run(_run())


@cli.command()
@click.argument("source")
def geolocate(source):
    """Visual geolocation: EXIF GPS + reverse image search (heuristic)."""
    from stalker.modules.visual_geolocation import geolocate_image
    from stalker.reporters import terminal as term

    async def _run():
        res = await geolocate_image(source)
        term.print_header(f"VISUAL GEOLOCATION: {source}")
        gps = res.get("gps", {})
        if gps.get("found"):
            print(f"  GPS       : {gps['lat']}, {gps['lon']}")
            print(f"  Map       : {gps['map_url']}")
        else:
            print(f"  GPS       : {gps.get('error', 'tidak ada')}")
        for l in res.get("reverse_search_links", []):
            print(f"  {l['engine']}: {l['url']}")
        if res.get("note"):
            print(f"  Note      : {res['note']}")
        print(f"  Tip       : {res.get('manual_tip')}")
        print()
    asyncio.run(_run())


@cli.command()
def menu():
    """Launch interactive menu."""
    from stalker.menu import show_menu
    show_menu()


if __name__ == "__main__":
    cli()
