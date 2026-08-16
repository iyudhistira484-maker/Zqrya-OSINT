"""Pipeline orchestrator - ties username search, ExifTools, and Google Dork together.

Flow:
  1. Username search (with progress display) -> profiles + real names + avatar URLs
  2. PARALLEL: EXIF + Google Dork + Face Search + Reverse Image + Recursive via asyncio.gather
  3. Social graph generation
  4. Generate report
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Set, Tuple
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import Config
from .modules import exif_analyzer, google_dork, image_downloader, flaresolverr, custom_apis, recursive_search, reverse_image, face_search, social_graph, breach_check, email_scanner, telegram_profiler, text_profiler, phone_scanner, password_leak, localdb
from .reporters import terminal as term
from .reporters import json_report, html_report


# ============================================================
#  PUBLIC API
# ============================================================


async def run_investigation(
    username: str,
    phone: str = "",
    enable_exif: bool = True,
    enable_dork: bool = True,
    max_sites: int = None,
    dork_categories: List[str] = None,
    skip_face_search: bool = False,
    skip_reverse: bool = False,
    skip_recursive: bool = False,
    skip_social: bool = False,
    **maigret_kwargs,
) -> Dict[str, Any]:
    """Run a full OSINT investigation pipeline."""
    Config.ensure_dirs()
    start_time = datetime.now()

    result: Dict[str, Any] = {
        "username": username,
        "timestamp": start_time.isoformat(),
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
        "localdb": {},
        "images": [],
        "summary": {},
    }

    # ---- Phase 1: Maigret Username Search ----
    term.print_phase(1, "Username Search", f"Searching '{username}' across social networks...")
    maigret_data = await _run_maigret(username, max_sites, **maigret_kwargs)
    result["maigret"] = maigret_data

    found_sites = maigret_data.get("found_sites", [])
    real_names = maigret_data.get("real_names", [])
    avatar_urls = maigret_data.get("avatar_urls", [])

    term.print_success(f"Found {len(found_sites)} profile(s) across {maigret_data.get('total_checked', 0)} sites")
    for site in found_sites:
        extra = ""
        if site.get("real_name"):
            extra = f"  name={site['real_name']}"
        if site.get("avatar_url"):
            extra += "  [has avatar]"
        term.print_warning(f"  {site['site_name']}: {site.get('url_user', site.get('url_main', ''))}{extra}")

    if real_names:
        term.print_success(f"Real names found: {', '.join(real_names[:5])}")
    if avatar_urls:
        term.print_success(f"Avatar URLs found: {len(avatar_urls)}")

    # ---- Phase 1.5: Custom APIs (Instagram, TikTok, Twitter, YouTube, GitHub) ----
    term.print_phase(1.5, "Custom APIs", f"Enriching data via xemoz API (5 platforms parallel)...")
    try:
        custom_results = await custom_apis.search_all_platforms(username)

        success_count = sum(1 for v in custom_results.values() if v.get("success"))
        term.print_success(f"Custom APIs: {success_count}/5 platforms responded")

        for platform, data in custom_results.items():
            if data.get("success"):
                name = data.get("real_name") or "-"
                avatar = "yes" if data.get("avatar_url") else "no"
                followers = data.get("followers")
                followers_str = f"  followers={followers}" if followers is not None else ""
                term.print_warning(f"  {platform}: name={name}, avatar={avatar}{followers_str}")
            else:
                err = data.get("error", "unknown")
                term.print_warning(f"  {platform}: failed ({err})")

        # Merge custom API data into Maigret results
        result["maigret"] = custom_apis.merge_with_maigret(custom_results, result["maigret"])

        # Update local references after merge
        found_sites = result["maigret"]["found_sites"]
        real_names = result["maigret"]["real_names"]
        avatar_urls = result["maigret"]["avatar_urls"]

        term.print_success(f"After merge: {len(found_sites)} profiles, {len(real_names)} names, {len(avatar_urls)} avatars")

    except Exception as e:
        term.print_error(f"Custom APIs failed: {e}")

    result["custom_apis"] = custom_results if "custom_results" in locals() else {}

    # ---- Phase 1.7: Telegram Profiler ----
    result["telegram"] = {}
    try:
        term.print_phase(1.7, "Telegram Profiler", f"Looking up @{username} on Telegram...")
        tg = await telegram_profiler.profile(username)
        if tg.get("success"):
            result["telegram"] = tg
            term.print_success(f"Telegram: {tg.get('display_name', tg.get('username'))} ({tg.get('type', 'user')})")
            if tg.get("numeric_id"):
                term.print_warning(f"  Numeric ID: {tg['numeric_id']}")
            if tg.get("members_text"):
                term.print_warning(f"  {tg['members_text']}")
        else:
            term.print_warning(f"  Telegram: {tg.get('error', 'not found')}")
    except Exception as e:
        term.print_error(f"Telegram profiler failed: {e}")

    # ---- Phase 1.8: Email Scanner + Breach Check + Text Profiler (parallel) ----
    phrases = []
    if any(r.get("bio") or r.get("real_name") for r in found_sites):
        phrases.append("Text Profile")
    phrases.append("Breach Check")
    term.print_phase(1.8, f"Intel ({', '.join(phrases)})", "Extracting data + breach lookup...")

    gather_tasks = []
    gather_labels = []

    # Breach check
    gather_tasks.append(breach_check.check_hudson_rock(username=username))
    gather_labels.append("breach")

    # Text profiler
    gather_tasks.append(asyncio.to_thread(text_profiler.extract_from_sites, found_sites))
    gather_labels.append("text_profile")

    gather_results = await asyncio.gather(*gather_tasks, return_exceptions=True)
    for label, res in zip(gather_labels, gather_results):
        if isinstance(res, Exception):
            term.print_warning(f"  {label} failed: {res}")
            continue
        if label == "breach":
            result["breach"] = res
            if res.get("username", {}).get("total_infections"):
                n = res["username"]["total_infections"]
                term.print_warning(f"  Hudson Rock: {n} infostealer infection(s) for username")
            else:
                term.print_success("  Hudson Rock: clean (no infections)")
        elif label == "text_profile":
            result["text_profile"] = res
            if res:
                keys = list(res.keys())
                term.print_success(f"  Text Profiler: found {len(keys)} entity types ({', '.join(keys[:5])})")

    # ---- Phase 1.9: Phone Scanner + Password Leak (parallel) ----
    combined_text = " ".join(
        (s.get("bio") or "") + " " + (s.get("real_name") or "")
        for s in found_sites
    )[:2000] if found_sites else ""
    phones_found = text_profiler.extract(combined_text) if found_sites else {}
    bio_phones = phones_found.get("phones", [])
    has_phone_data = bool(phone) or bool(bio_phones)
    has_bio_data = bool(found_sites)

    if has_phone_data or has_bio_data:
        phrases = []
        if has_phone_data: phrases.append("Phone Scanner")
        if has_bio_data: phrases.append("Password Leak")
        phase_id = 1.9
        term.print_phase(phase_id, f"Phone + Leak ({', '.join(phrases)})", "Checking registrations + leaked credentials...")

        ptasks = []
        plabels = []

        if has_phone_data:
            phone_to_use = phone or (bio_phones[0] if bio_phones else "")
            country = ""
            ptasks.append(phone_scanner.scan_phone(phone_to_use, country))
            plabels.append("phone_scan")

        if has_bio_data:
            all_bios = " ".join(
                (s.get("bio") or "") + " " + (s.get("real_name") or "")
                for s in found_sites
            )[:2000]
            ptasks.append(password_leak.check_from_text(all_bios))
            plabels.append("password_leak")

        presults = await asyncio.gather(*ptasks, return_exceptions=True)
        for label, res in zip(plabels, presults):
            if isinstance(res, Exception):
                term.print_warning(f"  {label} failed: {res}")
                continue
            if label == "phone_scan":
                result["phone_scan"] = res
                reg = phone_scanner.summary(res)
                term.print_success(f"  Phone Scanner: {reg['registered_count']}/{reg['platforms_checked']} registered ({', '.join(reg.get('registered_platforms',[]))})")
            elif label == "password_leak":
                result["password_leak"] = res
                if res.get("leaked_count"):
                    term.print_warning(f"  Password Leak: {res['leaked_count']} leaked password pattern(s) found!")

    # ---- Phase 1.95: Local Database Search ----
    names_for_db = real_names[:5]
    emails_for_db = list(set(
        s.get("email") or s.get("EMAIL") or ""
        for s in found_sites
        if s.get("email") or s.get("EMAIL")
    ))[:3]
    phones_for_db = bio_phones if bio_phones else []

    if names_for_db or emails_for_db or phones_for_db:
        term.print_phase(1.95, "Local DB", f"Searching {localdb.db_count()} local databases...")
        try:
            db_results = localdb.search_all(
                real_names=names_for_db,
                emails=emails_for_db,
                phones=phones_for_db,
            )
            result["localdb"] = db_results
            total = localdb.summary(db_results).get("total_matches", 0)
            if total > 0:
                term.print_warning(f"  Local DB: {total} match(es) found across local databases")
            else:
                term.print_success("  Local DB: no matches found")
        except Exception as e:
            term.print_warning(f"  Local DB search failed: {e}")

    # ---- Phase 2: PARALLEL EXIF + Dork + Face Search + Reverse Image + Recursive ----
    has_exif_work = enable_exif and avatar_urls
    has_dork_work = enable_dork and real_names
    has_face_work = len(avatar_urls) > 0 and not skip_face_search
    has_reverse_work = len(avatar_urls) > 0 and not skip_reverse
    has_recursive_work = bool(found_sites) and not skip_recursive

    if has_exif_work or has_dork_work or has_face_work or has_reverse_work or has_recursive_work:
        task_count = sum([bool(has_exif_work), bool(has_dork_work), bool(has_face_work), bool(has_reverse_work), bool(has_recursive_work)])
        term.print_phase(2, f"Analysis ({task_count} parallel tasks)", "EXIF + Dork + Face Search + Reverse Image + Recursive...")

        tasks = []
        task_labels = []

        if has_exif_work:
            tasks.append(_run_exif_pipeline(avatar_urls, username))
            task_labels.append("exif")

        if has_dork_work:
            dork_data = {
                "username": username,
                "real_names": real_names,
                "found_sites": found_sites,
                "custom_profiles": result.get("maigret", {}).get("custom_profiles", {}),
            }
            tasks.append(google_dork.smart_dork(dork_data))
            task_labels.append("dork")

        if has_face_work:
            tasks.append(face_search.search_all_engines(avatar_urls))
            task_labels.append("face_search")

        if has_reverse_work:
            tasks.append(reverse_image.search_all_avatars(avatar_urls))
            task_labels.append("reverse_image")

        if has_recursive_work:
            tasks.append(recursive_search.recursive_search(
                username, result["maigret"], max_depth=2, max_sites=max_sites,
            ))
            task_labels.append("recursive")

        if Config.STEALTH_MODE:
            await asyncio.sleep(Config.REQUEST_DELAY)

        parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

        for label, pr in zip(task_labels, parallel_results):
            if isinstance(pr, Exception):
                term.print_error(f"{label} task failed: {pr}")
                continue
            if label == "exif":
                result["exif"] = pr.get("exif", {})
                result["images"] = pr.get("images", [])
                exif_count = sum(1 for v in result["exif"].values() if v)
                term.print_success(f"EXIF: analyzed {len(avatar_urls)} images, {exif_count} had metadata")
                for img_url, meta in result["exif"].items():
                    if meta:
                        summary = exif_analyzer.summarize_metadata(meta)
                        for k, v in summary.items():
                            term.print_warning(f"    {k}: {v}")
            elif label == "dork":
                result["google_dork"] = pr
                total_hits = sum(len(links) for links in pr.values() if isinstance(links, list))
                term.print_success(f"Dork: {len(pr)} queries executed, {total_hits} total results")
            elif label == "reverse_image":
                result["reverse_image"] = pr
                success_count = sum(1 for v in pr.values() if v.get("success"))
                term.print_success(f"Reverse Image: {success_count}/{len(pr)} avatars searched")
            elif label == "face_search":
                result["face_search"] = pr
                fs = face_search.summary(pr)
                term.print_success(f"Face Search: {fs['avatars_searched']} avatars across {len(fs['engines_used'])} engines")
            elif label == "recursive":
                result["recursive"] = {
                    "discovered_usernames": pr.get("discovered_usernames", []),
                    "recursive_results": {},
                }
                discovered = pr.get("discovered_usernames", [])
                term.print_success(f"Recursive: discovered {len(discovered)} new username(s)")
                
                all_sites = pr.get("all_found_sites", [])
                if all_sites and len(all_sites) > len(found_sites):
                    result["maigret"]["found_sites"] = all_sites
                    result["maigret"]["real_names"] = pr.get("all_real_names", real_names)
                    result["maigret"]["avatar_urls"] = pr.get("all_avatar_urls", avatar_urls)

    # ---- FIX: Avatar Download (Cegah Unduh Ulang Jika Sudah Diunduh Modul EXIF) ----
    all_avatar_urls = result.get("maigret", {}).get("avatar_urls", [])
    if all_avatar_urls:
        term.print_phase(2.4, "Avatar Download", f"Processing avatars locally for HTML report...")
        unique_urls = list(dict.fromkeys(all_avatar_urls))
        
        # Ambil daftar gambar yang sudah berhasil diunduh sebelumnya
        url_to_local = {img["url"]: img["local_path"] for img in result.get("images", []) if img.get("success") and img.get("local_path")}
        
        # Saring URL yang belum diunduh
        urls_to_download = [u for u in unique_urls if u not in url_to_local]
        
        if urls_to_download:
            downloads = await image_downloader.download_images_from_urls(urls_to_download, username)
            for d in downloads:
                if d.get("local_path"):
                    url_to_local[d["url"]] = d["local_path"]
                    result["images"].append(d) # Tambahkan ke record utama
                    
        term.print_success(f"Processed {len(url_to_local)}/{len(unique_urls)} avatars")

        # Embed local paths in found_sites
        all_found = result["maigret"].get("found_sites", [])
        for site in all_found:
            av = site.get("avatar_url")
            if av and av in url_to_local:
                site["local_avatar"] = "images/" + Path(url_to_local[av]).name
                
        # Embed in custom API results
        for platform, data in result.get("custom_apis", {}).items():
            if isinstance(data, dict) and data.get("avatar_url"):
                if data["avatar_url"] in url_to_local:
                    data["local_avatar"] = "images/" + Path(url_to_local[data["avatar_url"]]).name

    # ---- Social Graph ----
    if not skip_social:
        term.print_phase(2.5, "Social Graph", "Building interactive network graph...")
        try:
            graph_filename = f"stalker_{username}_graph.html"
            graph_path = Config.OUTPUT_DIR / graph_filename
            social_graph.generate(result, graph_path)
            result["social_graph"] = graph_filename
            term.print_success(f"Social graph saved: {graph_filename}")
        except ImportError:
            term.print_warning("  Social graph skipped — pyvis/networkx not installed")
        except Exception as e:
            term.print_warning(f"  Social graph failed: {e}")

    # ---- Phase 3: Summary ----
    result["summary"] = _build_summary(result)
    result["duration_seconds"] = (datetime.now() - start_time).total_seconds()

    term.print_phase(3, "Summary", f"Investigation complete in {result['duration_seconds']:.1f}s")
    _print_summary(result["summary"])

    return result


async def run_dork_pipeline(username: str, max_sites: int = 100) -> Dict[str, Any]:
    """Dork-only pipeline: quick search + Custom APIs -> Smart Dork -> report-ready result."""
    Config.ensure_dirs()
    start_time = datetime.now()

    result: Dict[str, Any] = {
        "username": username,
        "timestamp": start_time.isoformat(),
        "maigret": {"found_sites": [], "total_checked": 0},
        "custom_apis": {},
        "google_dork": {},
        "exif": {},
        "reverse_image": {},
        "face_search": {},
        "recursive": {},
        "breach": {},
        "email_scan": {},
        "telegram": {},
        "text_profile": {},
        "phone_scan": {},
        "password_leak": {},
        "images": [],
        "summary": {},
    }

    term.print_phase(1, "Quick Search", f"Searching '{username}' (100 sites)...")
    maigret_data = await _run_maigret(username, max_sites=max_sites)
    result["maigret"] = maigret_data

    found_sites = maigret_data.get("found_sites", [])
    real_names = maigret_data.get("real_names", [])
    term.print_success(f"Found {len(found_sites)} profile(s), {len(real_names)} name(s)")

    term.print_phase(1.5, "Custom APIs", "Enriching data (5 platforms parallel)...")
    try:
        custom_results = await custom_apis.search_all_platforms(username)
        result["maigret"] = custom_apis.merge_with_maigret(custom_results, result["maigret"])
        result["custom_apis"] = custom_results
        found_sites = result["maigret"]["found_sites"]
        real_names = result["maigret"]["real_names"]
    except Exception as e:
        term.print_error(f"Custom APIs failed: {e}")

    if real_names or found_sites:
        term.print_phase(2, "Smart Dork", "Building queries from all extracted data...")
        dork_data = {
            "username": username,
            "real_names": real_names,
            "found_sites": found_sites,
            "custom_profiles": result.get("maigret", {}).get("custom_profiles", {}),
        }
        dork_results = await google_dork.smart_dork(dork_data)
        result["google_dork"] = dork_results
    else:
        term.print_warning("  No data for dork queries")

    result["summary"] = _build_summary(result)
    result["duration_seconds"] = (datetime.now() - start_time).total_seconds()
    term.print_phase(3, "Done", f"Complete in {result['duration_seconds']:.1f}s")
    _print_summary(result["summary"])

    return result


async def run_quick_search(username: str, **maigret_kwargs) -> Dict[str, Any]:
    Config.ensure_dirs()
    term.print_phase(1, "Username Search", f"Searching '{username}'...")
    maigret_data = await _run_maigret(username, **maigret_kwargs)
    return maigret_data


async def run_exif_only(source: str) -> Dict[str, Any]:
    Config.ensure_dirs()
    term.print_phase(1, "EXIF Analysis", f"Analyzing: {source}")

    if source.startswith("http://") or source.startswith("https://"):
        metadata = await exif_analyzer.extract_from_url(source)
    else:
        filepath = Path(source)
        if not filepath.exists():
            return {"error": "file_not_found"}
        metadata = await exif_analyzer.extract_from_file(filepath)

    return {"exif": metadata}


async def run_dork_only(name: str, categories: List[str] = None) -> Dict[str, Any]:
    Config.ensure_dirs()
    term.print_phase(1, "Google Dork Search", f"Searching: {name}")
    results = await google_dork.search_person(name, categories)
    return {"dork": results}


# ============================================================
#  MAIGRET SEARCH
# ============================================================

async def _run_maigret(username: str, max_sites: int = None, **kwargs) -> Dict[str, Any]:
    # DNS FIX: Apply mobile optimization before any network calls
    try:
        from stalker.modules.dns_fix import patch_dns_for_termux
        patch_dns_for_termux()
    except ImportError:
        pass
    from stalker.config import IS_TERMUX
    import socket as _sock
    if IS_TERMUX:
        _sock.setdefaulttimeout(30)

    maigret_root = Path(__file__).resolve().parent.parent / "maigret"
    maigret_pkg = maigret_root / "maigret"

    for p in [str(maigret_root), str(maigret_pkg.parent)]:
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        import maigret as maigret_module
        from maigret.sites import MaigretDatabase
        from maigret.notify import QueryNotifyPrint

        db_path = maigret_pkg / "resources" / "data.json"
        site_limit = max_sites or Config.MAIGRET_MAX_SITES

        loop = asyncio.get_event_loop()

        def _load_db():
            if not db_path.exists():
                return MaigretDatabase([])
            return MaigretDatabase().load_from_path(str(db_path))

        db = await loop.run_in_executor(None, _load_db)
        site_dict = await loop.run_in_executor(
            None, lambda: db.ranked_sites_dict(top=site_limit),
        )

        if not site_dict:
            return {"found_sites": [], "real_names": [], "avatar_urls": [], "total_checked": 0}

        maigret_logger = logging.getLogger("stalker.maigret")
        maigret_logger.setLevel(logging.ERROR)
        logging.getLogger("maigret").setLevel(logging.ERROR)

        query_notify = QueryNotifyPrint(color=False)
        cf_config = await flaresolverr.detect()

        results = await maigret_module.search(
            username=username,
            site_dict=site_dict,
            logger=maigret_logger,
            query_notify=query_notify,
            timeout=Config.MAIGRET_TIMEOUT,
            is_parsing_enabled=True,
            no_progressbar=True,
            cloudflare_bypass=cf_config,
            **kwargs,
        )

        found_sites = []
        real_names: Set[str] = set()
        avatar_urls: List[str] = []

        for site_name, siteresult in results.items():
            status = siteresult.get("status")
            if not status:
                continue

            if status.is_found():
                ids = status.ids_data or {}
                name = ids.get("fullname") or ids.get("name") or ids.get("display_name")
                if name and len(str(name).strip()) > 1:
                    real_names.add(str(name).strip())

                avatar = ids.get("image") or ids.get("avatar") or ids.get("profile_image")
                if avatar and str(avatar).startswith("http"):
                    avatar_urls.append(str(avatar))

                other_usernames = siteresult.get("ids_usernames", {})
                other_links = siteresult.get("ids_links", [])

                found_sites.append({
                    "site_name": site_name,
                    "url_user": status.site_url_user or siteresult.get("url_user", ""),
                    "url_main": siteresult.get("url_main", ""),
                    "real_name": name,
                    "avatar_url": avatar,
                    "bio": ids.get("bio") or ids.get("about") or ids.get("description"),
                    "location": ids.get("location") or ids.get("city") or ids.get("country"),
                    "other_usernames": dict(other_usernames) if other_usernames else {},
                    "other_links": list(other_links) if other_links else [],
                    "ids_data": dict(ids) if ids else {},
                })

        return {
            "found_sites": found_sites,
            "real_names": list(real_names),
            "avatar_urls": avatar_urls,
            "total_checked": len(site_dict),
        }

    except ImportError:
        return {"found_sites": [], "real_names": [], "avatar_urls": [], "total_checked": 0}
    except Exception:
        return {"found_sites": [], "real_names": [], "avatar_urls": [], "total_checked": 0}


# ============================================================
#  PARALLEL PIPELINES (Phase 2)
# ============================================================

async def _run_exif_pipeline(avatar_urls: List[str], username: str) -> Dict[str, Any]:
    download_tasks = [
        image_downloader.download_profile_image(url, username)
        for url in avatar_urls[:10]
    ]
    downloaded_paths = await asyncio.gather(*download_tasks)

    images = []
    for url, path in zip(avatar_urls[:10], downloaded_paths):
        images.append({
            "url": url,
            "local_path": str(path) if path else None,
            "success": path is not None,
        })

    valid_images = [i for i in images if i["success"] and i["local_path"]]
    exif_tasks = [
        exif_analyzer.extract_from_file(Path(i["local_path"]))
        for i in valid_images
    ]
    exif_results = await asyncio.gather(*exif_tasks)

    exif_map = {}
    for img, meta in zip(valid_images, exif_results):
        if meta:
            exif_map[img["url"]] = meta

    return {"exif": exif_map, "images": images}


def _extract_real_names(result: Dict[str, Any]) -> List[str]:
    names = set()
    for name in result.get("maigret", {}).get("real_names", []):
        if name and len(name.split()) >= 2:
            names.add(name)
    for site in result.get("maigret", {}).get("found_sites", []):
        name = site.get("real_name")
        if name and len(str(name).split()) >= 2:
            names.add(str(name))
    return list(names)


def _build_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    profiles = result.get("maigret", {}).get("found_sites", [])
    reverse_data = result.get("reverse_image", {})
    face_data = result.get("face_search", {})
    recursive_data = result.get("recursive", {})
    breach_data = result.get("breach", {})
    email_data = result.get("email_scan", [])
    telegram_data = result.get("telegram", {})
    text_data = result.get("text_profile", {})

    return {
        "username": result["username"],
        "profiles_found": len(profiles),
        "sites_checked": result.get("maigret", {}).get("total_checked", 0),
        "platforms": list(set(s.get("site_name", "?") for s in profiles)),
        "real_names_found": _extract_real_names(result),
        "avatars_found": len(result.get("maigret", {}).get("avatar_urls", [])),
        "exif_images_analyzed": sum(1 for v in result.get("exif", {}).values() if v),
        "dork_names_searched": list(result.get("google_dork", {}).keys()),
        "reverse_image_pages": sum(len(v.get("pages_found", [])) for v in reverse_data.values() if isinstance(v, dict) and v.get("success")),
        "reverse_image_similar": sum(len(v.get("similar_images", [])) for v in reverse_data.values() if isinstance(v, dict) and v.get("success")),
        "face_search_engines": face_search.summary(face_data).get("engines_used", {}) if face_data else {},
        "face_search_pages": sum(len(eng.get("pages_found", [])) for engines in face_data.values() for eng in engines.values() if isinstance(eng, dict) and eng.get("success")),
        "recursive_usernames": [d.get("username") for d in recursive_data.get("discovered_usernames", [])],
        "custom_api_platforms": [k for k, v in result.get("custom_apis", {}).items() if isinstance(v, dict) and v.get("success")],
        "breach_hudson_rock": breach_data.get("username", {}).get("total_infections", 0),
        "email_registered": email_scanner.summary(email_data).get("registered_count", 0) if email_data else 0,
        "telegram_found": 1 if telegram_data.get("success") else 0,
        "telegram_display": telegram_data.get("display_name", "") if telegram_data.get("success") else "",
        "phone_registered": phone_scanner.summary(result.get("phone_scan", [])).get("registered_count", 0),
        "password_leaks": result.get("password_leak", {}).get("leaked_count", 0),
        "localdb_matches": localdb.summary(result.get("localdb", {})).get("total_matches", 0),
        "text_entities": list(text_data.keys())[:10] if text_data else [],
        "duration": f"{result.get('duration_seconds', 0):.1f}s",
    }


def _print_summary(summary: Dict[str, Any]):
    term.print_divider()
    term.print_header("RESULTS")
    term.print_info(f"  Username: {summary['username']}")
    term.print_info(f"  Profiles found: {summary['profiles_found']} / {summary['sites_checked']} sites")
    if summary.get("platforms"):
        term.print_info(f"  Platforms: {', '.join(summary['platforms'][:15])}")
    term.print_divider()


# ============================================================
#  REPORT SAVING
# ============================================================

async def save_report(result: Dict[str, Any], output_dir: Path = None, formats: List[str] = None):
    if output_dir is None:
        output_dir = Config.OUTPUT_DIR
    if formats is None:
        formats = ["json", "html"]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    username = result.get("username", "unknown")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    saved = []
    for fmt in formats:
        if fmt == "json":
            path = json_report.save(result, output_dir, username, ts)
        elif fmt == "html":
            try:
                path = html_report.save(result, output_dir, username, ts)
            except Exception as e:
                term.print_error(f"HTML report failed: {e}")
                path = None
        else:
            continue
        if path:
            saved.append(path)
            term.print_success(f"Report saved: {path}")

    return saved
