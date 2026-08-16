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
            ("Timezone", result.get("timezone", "?")),
            ("Reverse DNS", result.get("reverse_dns", "-")),
            ("Is Proxy/VPN", "YES" if result.get("is_proxy") else "No"),
            ("Is Hosting", "YES" if result.get("is_hosting") else "No"),
            ("Map", result.get("map_url", "-")),
        ]
        for label, val in fields:
            if val and val not in ("?", "-", ""):
                print(f"  {label:<15}: {val}")

        shodan_data = result.get("shodan", {})
        if shodan_data.get("open_ports"):
            print(f"\n  {'Open Ports':<15}: {', '.join(str(p) for p in shodan_data['open_ports'])}")
        if shodan_data.get("vulns"):
            term.print_warning(f"  CVEs: {', '.join(shodan_data['vulns'][:5])}")
        if shodan_data.get("tags"):
            print(f"  {'Tags':<15}: {', '.join(shodan_data['tags'])}")
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
def menu():
    """Launch interactive menu."""
    from stalker.menu import show_menu
    show_menu()


if __name__ == "__main__":
    cli()
