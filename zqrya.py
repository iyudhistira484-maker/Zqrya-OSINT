#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZQRYA v3.0 - Advanced OSINT Intelligence Suite
Merged with the full deep pipeline: Maigret 600+ platforms, dark web,
breach intelligence, Shodan, username variants
"""
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.banner import show_banner, console
from core.engine import ZqryaEngine
from core.utils import print_help, print_version
from reports.generator import ReportGenerator


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Zqrya v3.0 - Advanced OSINT Intelligence Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False
    )
    
    # Main command
    parser.add_argument("command", nargs="?", choices=["investigate", "scan", "help"],
                        help="Command: investigate (default), scan, help")
    parser.add_argument("target", nargs="?", help="Target to investigate")
    
    # Investigation flags
    parser.add_argument("-u", "--username", metavar="USERNAME", help="Investigate username")
    parser.add_argument("-e", "--email", metavar="EMAIL", help="Investigate email")
    parser.add_argument("-p", "--phone", metavar="PHONE", help="Investigate phone number")
    parser.add_argument("-d", "--domain", metavar="DOMAIN", help="Investigate domain")
    parser.add_argument("-i", "--ip", metavar="IP", help="Investigate IP address")
    parser.add_argument("-url", "--url", metavar="URL", help="Website footprint analysis (URL)")
    parser.add_argument("-m", "--maigret", metavar="USERNAME", help="Deep username search via Maigret (600+ platforms)")
    parser.add_argument("--darkweb", metavar="TARGET", help="Dark web / paste / breach check (email, username, or phone)")
    parser.add_argument("--variants", metavar="USERNAME", help="Generate 150+ username variants")
    parser.add_argument("--full", metavar="TARGET", help="Combined OSINT investigation (Full Pipeline)")
    parser.add_argument("--maigret-sites", type=int, default=300, help="Max sites for Maigret scan (default: 300)")
    
    # Web UI
    parser.add_argument("-web", "--web", action="store_true", help="Launch web UI")
    parser.add_argument("--port", type=int, default=7331, help="Web UI port (default: 7331)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")

    # Interactive shell
    parser.add_argument("-sh", "--shell", action="store_true",
                        help="Launch interactive shell (default when no args)")
    
    # Report options
    parser.add_argument("--report", action="store_true", help="Generate comprehensive report")
    parser.add_argument("-o", "--output", metavar="FILE", help="Save report to file")
    parser.add_argument("--output-dir", metavar="DIR", default="output", 
                        help="Output directory for reports (default: output)")
    parser.add_argument("--format", choices=["json", "html", "txt", "md", "all"], 
                        default="json", help="Output format (default: json)")
    parser.add_argument("--compress", action="store_true", 
                        help="Compress JSON output with gzip")
    
    # Batch processing
    parser.add_argument("--batch", metavar="FILE", 
                        help="Batch scan: file with one target per line")
    parser.add_argument("--batch-delay", type=float, default=1.0,
                        help="Delay between batch scans in seconds (default: 1.0)")
    
    # Investigation options
    parser.add_argument("--timeout", type=int, default=12, 
                        help="Request timeout in seconds (default: 12)")
    parser.add_argument("--threads", type=int, default=25, 
                        help="Concurrent threads (default: 25)")
    parser.add_argument("--deep", action="store_true", 
                        help="Deep investigation (run all relevant modules)")
    
    # Output options
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    parser.add_argument("--quiet", action="store_true", help="Suppress output (only save report)")
    
    # Help flags
    parser.add_argument("-h", "--help", action="store_true", help="Show help")
    parser.add_argument("-v", "--version", action="store_true", help="Show version")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    
    return parser.parse_args()


async def batch_scan(targets: list, args) -> dict:
    """Scan multiple targets from a file"""
    results = {}
    engine = ZqryaEngine(timeout=args.timeout, max_concurrent=args.threads)
    
    console.print(f"\n[bold cyan]📦 Batch scanning {len(targets)} targets[/bold cyan]\n")
    
    async with engine:
        for idx, target in enumerate(targets, 1):
            target = target.strip()
            if not target or target.startswith('#'):
                continue
            
            console.print(f"[{idx}/{len(targets)}] 🔍 Scanning: [yellow]{target}[/yellow]")
            
            try:
                # Auto-detect type
                from core.detector import detector
                entity = detector.detect(target)
                target_type = entity.type
                norm_target = entity.normalized
                
                if args.deep:
                    result = await engine.investigate_all(norm_target, target_type)
                else:
                    result = await engine.investigate(norm_target, target_type)
                
                if result:
                    results[target] = result
                    console.print(f"  [green]✅ Found {len(result.get('data', {}).get('found', [])) if result.get('data') else 0} results[/green]")
                else:
                    console.print(f"  [yellow]⚠️ No results[/yellow]")
                    
            except Exception as e:
                console.print(f"  [red]❌ Error: {e}[/red]")
                if args.debug:
                    import traceback
                    traceback.print_exc()
            
            # Delay between scans
            if idx < len(targets):
                await asyncio.sleep(args.batch_delay)
    
    return results


async def run_full_investigation(target: str, args, zqrya_results=None):
    """Run the full combined investigation: Zqrya modules + full deep pipeline.

    Pass zqrya_results to reuse an already-completed Zqrya deep scan (avoids running it twice).
    """
    from stalker.pipeline import run_investigation, save_report, _run_maigret
    from stalker.modules import custom_apis, telegram_profiler, text_profiler, breach_check, username_variants
    from stalker.reporters import terminal as term

    console.print(f"\n[bold violet]🧠 Combined OSINT (Full Pipeline): [yellow]{target}[/yellow][/bold violet]\n")

    # Auto-detect type
    from core.detector import detector
    entity = detector.detect(target)
    ttype = entity.type

    # ── Phase A: Zqrya engine (deep multi-module scan) ──
    if zqrya_results is None:
        console.print("\n[bold cyan]▸ ZQRYA ENGINE[/bold cyan]")
        async with ZqryaEngine(timeout=args.timeout, max_concurrent=args.threads) as engine:
            zqrya_results = await engine.investigate_all(target, ttype)
            if zqrya_results:
                await engine.display_summary(zqrya_results)
    console.print("\n[bold cyan]▸ DEEP PIPELINE[/bold cyan]")

    if ttype == 'email':
        from stalker.modules import email_scanner, dark_web_checker
        result = {}
        # Email scanner 30+ platforms
        console.print("[cyan]📧 Email scanner (30+ platforms)...[/cyan]")
        results = await email_scanner.scan_email(entity.normalized)
        s = email_scanner.summary(results)
        console.print(f"  [green]Registered on {s['registered_count']}/{s['platforms_checked']} platforms[/green]")
        # Breach check
        console.print("[cyan]🌑 Dark web check...[/cyan]")
        hr = await breach_check.check_hudson_rock(email=entity.normalized)
        dw = await dark_web_checker.full_darkweb_check(entity.normalized, 'email')
        result = {
            'username': entity.normalized,
            'email_scan': results,
            'breach': hr,
            'dark_web': dw,
            'summary': {
                'profiles_found': s['registered_count'],
                'platforms': s['registered_platforms'],
                'breach_hudson_rock': hr.get('email', {}).get('total_infections', 0),
            }
        }
    elif ttype == 'phone':
        from stalker.modules import phone_scanner
        console.print("[cyan]📱 Phone scanner (6 platforms + Truecaller)...[/cyan]")
        full = await phone_scanner.full_scan(entity.normalized)
        a = full.get('analysis', {})
        result = {
            'username': entity.normalized,
            'phone_scan': full,
            'summary': {
                'phone_carrier': a.get('carrier', '?'),
                'phone_country': a.get('country', '?'),
                'profiles_found': phone_scanner.summary(full.get('platforms', []))['registered_count'],
            }
        }
        if full.get('truecaller', {}).get('name'):
            console.print(f"  [yellow]Truecaller: {full['truecaller']['name']}[/yellow]")
    else:
        # Username → full pipeline
        result = await run_investigation(
            entity.normalized,
            enable_exif=False,
            enable_dork=True,
            max_sites=args.maigret_sites,
            skip_social=True,
        )

    # ── Merge Zqrya results into the combined report ──
    if result:
        result["zqrya"] = zqrya_results or {}

    # Save reports
    if (args.report or args.output) and result:
        saved = await save_report(result, formats=['json', 'html'])
        for p in saved:
            console.print(f"[green]✅ Report saved: {p}[/green]")
    elif result:
        console.print(f"\n[bold green]📊 Summary:[/bold green]")
        s = result.get('summary', {})
        for k, v in s.items():
            if isinstance(v, (list, dict)):
                console.print(f"  [cyan]{k}:[/cyan] {str(v)[:80]}")
            else:
                console.print(f"  [cyan]{k}:[/cyan] {v}")


async def main_async():
    args = parse_arguments()
    
    # Version
    if args.version:
        print_version()
        return

    # Help
    if args.help or args.command == "help":
        print_help()
        return

    # Web UI
    if args.web:
        from web.server import start_web_server
        if not args.no_color:
            show_banner()
        start_web_server(port=args.port, open_browser=not args.no_browser)
        return

    # Interactive shell (explicit flag, or no arguments at all)
    has_target_args = any([args.username, args.email, args.phone, args.domain, args.ip,
                           args.url, args.maigret, args.darkweb, args.variants,
                           args.full, args.target, args.batch])
    if args.shell or not has_target_args:
        from core.interactive import InteractiveShell
        shell = InteractiveShell(timeout=args.timeout, threads=args.threads)
        await shell.run()
        return
    
    # Show banner
    if not args.no_color and not args.quiet:
        show_banner()
    
    # ── Full combined investigation ──
    if args.full:
        await run_full_investigation(args.full, args)
        return
    
    # ── Maigret deep username search ──
    if args.maigret:
        async with ZqryaEngine(timeout=args.timeout, max_concurrent=args.threads) as engine:
            mod = engine.modules['maigret']
            result = await mod.scan(args.maigret, max_sites=args.maigret_sites)
            if result and result.get('data'):
                if not args.quiet:
                    await engine.display_result(result)
                if args.report or args.output:
                    rg = ReportGenerator(output_dir=args.output_dir)
                    fname = args.output or None
                    if args.format == 'all':
                        await rg.save_all_formats({'maigret': result}, fname)
                    elif args.format == 'json':
                        await rg.save_json({'maigret': result}, fname, compress=args.compress)
                    elif args.format == 'html':
                        await rg.save_html({'maigret': result}, fname)
                    elif args.format == 'txt':
                        await rg.save_txt({'maigret': result}, fname)
                    elif args.format == 'md':
                        await rg.save_markdown({'maigret': result}, fname)
        return
    
    # ── Dark web checker ──
    if args.darkweb:
        async with ZqryaEngine(timeout=args.timeout, max_concurrent=args.threads) as engine:
            mod = engine.modules['darkweb']
            result = await mod.scan(args.darkweb, 'auto')
            if result and result.get('data'):
                if not args.quiet:
                    await engine.display_result(result)
                if args.report or args.output:
                    rg = ReportGenerator(output_dir=args.output_dir)
                    fname = args.output or None
                    if args.format == 'all':
                        await rg.save_all_formats({'darkweb': result}, fname)
                    elif args.format == 'json':
                        await rg.save_json({'darkweb': result}, fname, compress=args.compress)
                    elif args.format == 'html':
                        await rg.save_html({'darkweb': result}, fname)
                    elif args.format == 'txt':
                        await rg.save_txt({'darkweb': result}, fname)
                    elif args.format == 'md':
                        await rg.save_markdown({'darkweb': result}, fname)
        return
    
    # ── Username variants ──
    if args.variants:
        from stalker.modules.username_variants import generate_variants
        variants = generate_variants(args.variants, max_variants=150)
        console.print(f"\n[bold violet]🧬 Username Variants: [yellow]{args.variants}[/yellow][/bold violet]")
        console.print(f"[dim]Generated {len(variants)} variants[/dim]\n")
        for i, v in enumerate(variants, 1):
            console.print(f"  [cyan]{i:>3}.[/cyan] [white]{v}[/white]")
        console.print()
        return
    
    # Batch processing
    if args.batch:
        try:
            with open(args.batch, 'r', encoding='utf-8') as f:
                targets = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            if not targets:
                console.print("[red]❌ No targets found in batch file[/red]")
                return
            
            results = await batch_scan(targets, args)
            
            # Generate summary report for batch
            if results and (args.report or args.output):
                rg = ReportGenerator(output_dir=args.output_dir)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if args.format == "all":
                    # Save all formats
                    base_name = args.output or f"zqrya_batch_{timestamp}"
                    files = await rg.save_all_formats(results, base_name)
                    console.print(f"\n[green]✅ Batch reports saved: {len(files)} files[/green]")
                else:
                    fname = args.output or f"zqrya_batch_{timestamp}.{args.format}"
                    if args.format == "json":
                        f = await rg.save_json(results, fname, compress=args.compress)
                    elif args.format == "html":
                        f = await rg.save_html(results, fname)
                    elif args.format == "txt":
                        f = await rg.save_txt(results, fname)
                    elif args.format == "md":
                        f = await rg.save_markdown(results, fname)
                    console.print(f"\n[green]✅ Batch report saved: {f}[/green]")
            
            console.print(f"\n[bold green]📊 Batch Summary:[/bold green]")
            console.print(f"  Total targets: {len(targets)}")
            console.print(f"  Successful: {len(results)}")
            console.print(f"  Failed: {len(targets) - len(results)}")
            
        except FileNotFoundError:
            console.print(f"[red]❌ Batch file not found: {args.batch}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Batch error: {e}[/red]")
            if args.debug:
                import traceback
                traceback.print_exc()
        return
    
    # Single target
    engine = ZqryaEngine(timeout=args.timeout, max_concurrent=args.threads)
    
    target, target_type = None, None
    if args.username:   target, target_type = args.username, "username"
    elif args.email:    target, target_type = args.email,    "email"
    elif args.phone:    target, target_type = args.phone,    "phone"
    elif args.domain:   target, target_type = args.domain,   "domain"
    elif args.ip:       target, target_type = args.ip,       "ip"
    elif args.url:      target, target_type = args.url,      "url"
    elif args.target:   target, target_type = args.target,   "auto"
    
    if not target:
        console.print("[red]❌ No target specified[/red]")
        return
    
    # Deep investigation with report
    if args.report or args.output or args.deep:
        if not args.quiet:
            console.print(f"\n[bold cyan]🔍 Deep Investigation: [yellow]{target}[/yellow][/bold cyan]")
        
        # --deep juga menggabungkan deep pipeline (untuk target yang didukung)
        if args.deep:
            from core.detector import detector as det_combined
            det_type = det_combined.detect(target).type if target_type == 'auto' else target_type
            if det_type in ('username', 'email', 'phone'):
                async with engine:
                    results = await engine.investigate_all(target, target_type)
                if results:
                    if not args.quiet:
                        await engine.display_summary(results)
                    await run_full_investigation(target, args, zqrya_results=results)
                else:
                    if not args.quiet:
                        console.print("[red]❌ No results found[/red]")
                return
        
        async with engine:
            results = await engine.investigate_all(target, target_type)
        
        if results:
            rg = ReportGenerator(output_dir=args.output_dir)
            
            # Handle "all" format
            if args.format == "all":
                base_name = args.output or None
                files = await rg.save_all_formats(results, base_name)
                if not args.quiet:
                    console.print(f"\n[green]✅ Reports saved: {len(files)} files[/green]")
            else:
                fname = args.output
                if args.format == "json":
                    f = await rg.save_json(results, fname, compress=args.compress)
                elif args.format == "html":
                    f = await rg.save_html(results, fname)
                elif args.format == "txt":
                    f = await rg.save_txt(results, fname)
                elif args.format == "md":
                    f = await rg.save_markdown(results, fname)
                else:
                    f = await rg.save_json(results, fname)
                
                if not args.quiet:
                    console.print(f"\n[green]✅ Report saved: {f}[/green]")
            
            if not args.quiet:
                await engine.display_summary(results)
        else:
            if not args.quiet:
                console.print("[red]❌ No results found[/red]")
    
    # Quick investigation
    else:
        async with engine:
            result = await engine.investigate(target, target_type)
            if result and not args.quiet:
                await engine.display_result(result)
            elif not result and not args.quiet:
                console.print("[red]❌ No results found[/red]")


def main():
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main_async())
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠  Interrupted[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]❌ Fatal: {e}[/red]")
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    from datetime import datetime  # For batch timestamp
    main()