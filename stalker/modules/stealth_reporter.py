"""Stealth Reporter — Generate formatted cyber intelligence brief from all findings.

Produces a clean, actionable intelligence report in:
- Terminal (rich colored output)
- Markdown (.md) — shareable
- JSON — for further processing

The report aggregates: WhatsApp intel, phone carrier, name, social profiles,
breach data, risk score, timeline, correlation, keyword alerts.

No API keys needed — formats existing investigation data.
"""
from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime
import json, os


BOLD = "\033[1m"; GREEN = "\033[32m"; RED = "\033[31m"
YELLOW = "\033[33m"; CYAN = "\033[36m"; MAGENTA = "\033[35m"
DIM = "\033[2m"; NC = "\033[0m"

SECTION_WIDTH = 50


def _bar(label: str, char: str = "═") -> str:
    pad = (SECTION_WIDTH - len(label) - 2) // 2
    return f"{'═'*pad} {label} {'═'*(SECTION_WIDTH - len(label) - 2 - pad)}"


def generate_terminal_brief(result: Dict[str, Any]) -> str:
    """Generate a formatted cyber intelligence brief for terminal output."""
    target = result.get("username","") or result.get("email","") or result.get("phone","")
    input_type = ("email" if "@" in target else "phone" if any(c.isdigit() for c in target[:4]) else "username")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = []

    # ── Header ────────────────────────────────────────────────
    lines.append(f"\n{BOLD}{CYAN}")
    lines.append("  ╔══════════════════════════════════════════════════╗")
    lines.append("  ║     ZQRYA — CYBER INTELLIGENCE BRIEF            ║")
    lines.append("  ╚══════════════════════════════════════════════════╝")
    lines.append(f"{NC}")
    lines.append(f"  Target: {BOLD}{target}{NC}  |  Type: {input_type.upper()}")
    lines.append(f"  Generated: {timestamp}")

    # ── Risk Score Banner ─────────────────────────────────────
    risk = result.get("risk_score", {})
    if risk:
        score = risk.get("score", 0)
        level = risk.get("level", "?")
        color = risk.get("color", "")
        lines.append(f"\n  {BOLD}Risk Assessment: {color}{score}/100 — {level}{NC}")
        for finding in risk.get("key_findings", [])[:3]:
            lines.append(f"  ⚡ {finding}")

    # ── Identity Summary ──────────────────────────────────────
    lines.append(f"\n{BOLD}  {_bar('IDENTITY')}{NC}")
    corr = result.get("correlation", {})
    if corr.get("real_names"):
        lines.append(f"  Real Name(s):   {', '.join(corr['real_names'][:3])}")
    if corr.get("correlated_emails"):
        lines.append(f"  Linked Emails:  {', '.join(corr['correlated_emails'][:4])}")
    if corr.get("correlated_phones"):
        lines.append(f"  Linked Phones:  {', '.join(corr['correlated_phones'][:3])}")
    if corr.get("correlated_usernames"):
        lines.append(f"  Alt Usernames:  {', '.join(corr['correlated_usernames'][:5])}")

    # ── WhatsApp / Phone ──────────────────────────────────────
    wa_data = result.get("whatsapp_intel", {})
    if wa_data:
        wa = wa_data.get("whatsapp", {})
        country = wa_data.get("country", {})
        lines.append(f"\n{BOLD}  {_bar('WHATSAPP & PHONE')}{NC}")
        lines.append(f"  Phone:    {wa_data.get('phone_normalized','')}")
        lines.append(f"  Country:  {country.get('flag','')} {country.get('country','')} | {country.get('carrier','')}")
        wa_status = f"{GREEN}ACTIVE{NC}" if wa.get("wa_exists") else f"{RED}NOT FOUND{NC}"
        lines.append(f"  WhatsApp: {wa_status}")
        if wa.get("is_business"): lines.append(f"  Account type: WhatsApp Business")
        if wa.get("wa_link"): lines.append(f"  Chat link: {CYAN}{wa['wa_link']}{NC}")
        tc = wa_data.get("truecaller", {})
        if tc.get("name"): lines.append(f"  Caller name (Truecaller): {BOLD}{tc['name']}{NC}")
        rep = wa_data.get("reputation", {})
        if rep.get("total_reports",0) > 0:
            lines.append(f"  {RED}Spam reports: {rep['total_reports']}{NC}")

    # ── Social Profiles ───────────────────────────────────────
    maigret = result.get("maigret", {})
    sites = maigret.get("found_sites", [])
    if sites:
        lines.append(f"\n{BOLD}  {_bar('SOCIAL PROFILES')}{NC}")
        lines.append(f"  Found: {len(sites)} platform(s) of {maigret.get('total_checked', '?')} checked")
        for site in sites[:12]:
            name = site.get("site_name","")
            url = site.get("url_user","")
            lines.append(f"  {GREEN}✓{NC} {name:<20} {DIM}{url[:50]}{NC}")
        if len(sites) > 12:
            lines.append(f"  ... and {len(sites)-12} more platforms")

    # ── GitHub Intel ──────────────────────────────────────────
    gh = result.get("github_intel", {})
    if gh.get("found"):
        p = gh.get("profile", {})
        lines.append(f"\n{BOLD}  {_bar('GITHUB INTELLIGENCE')}{NC}")
        lines.append(f"  Profile:  @{p.get('username','')} | repos={p.get('public_repos',0)} | followers={p.get('followers',0)}")
        if p.get("location"): lines.append(f"  Location: {p['location']}")
        if p.get("name"): lines.append(f"  Name:     {p['name']}")
        emails = [e["email"] for e in gh.get("extracted_emails",[]) if isinstance(e,dict)]
        if emails:
            lines.append(f"  {YELLOW}⚡ Real emails from commits: {', '.join(emails[:5])}{NC}")
        orgs = [o["name"] for o in gh.get("organizations",[])]
        if orgs: lines.append(f"  Orgs:     {', '.join(orgs[:5])}")
        langs = list(gh.get("languages",{}).keys())[:5]
        if langs: lines.append(f"  Languages: {', '.join(langs)}")

    # ── Reddit Intel ──────────────────────────────────────────
    reddit = result.get("reddit_intel", {})
    if reddit.get("found"):
        p = reddit.get("profile", {}); a = reddit.get("activity", {})
        lines.append(f"\n{BOLD}  {_bar('REDDIT INTELLIGENCE')}{NC}")
        lines.append(f"  Karma: {p.get('total_karma',0)} | Account age: {p.get('account_age_days',0)} days")
        subs = [s[0] for s in a.get("top_subreddits",[])[:6]]
        if subs: lines.append(f"  Top communities: {', '.join(subs)}")
        if a.get("estimated_timezone"): lines.append(f"  Estimated timezone: {a['estimated_timezone']}")
        if a.get("location_clues"): lines.append(f"  Location clues: {', '.join(a['location_clues'])}")
        if a.get("emails_in_content"): lines.append(f"  {YELLOW}Emails in posts: {', '.join(a['emails_in_content'])}{NC}")

    # ── Gravatar ──────────────────────────────────────────────
    grav = result.get("gravatar", {})
    if grav.get("found") or grav.get("has_avatar"):
        lines.append(f"\n{BOLD}  {_bar('GRAVATAR')}{NC}")
        if grav.get("display_name"): lines.append(f"  Name: {grav['display_name']}")
        if grav.get("location"): lines.append(f"  Location: {grav['location']}")
        accs = [a["domain"] for a in grav.get("accounts",[])[:6]]
        if accs: lines.append(f"  Linked accounts: {', '.join(accs)}")
        if grav.get("avatar_url"): lines.append(f"  Avatar: {CYAN}{grav['avatar_url']}{NC}")

    # ── Wayback Machine ───────────────────────────────────────
    wb = result.get("wayback_intel", {})
    if wb.get("total_archived",0) > 0:
        lines.append(f"\n{BOLD}  {_bar('ARCHIVED PROFILES')}{NC}")
        for plat, d in wb.get("platforms_archived",{}).items():
            lines.append(f"  {GREEN}✓{NC} {plat}: first={d.get('first_seen','')} last={d.get('last_seen','')}")
            if d.get("snapshot_url"): lines.append(f"    {DIM}{d['snapshot_url'][:70]}{NC}")

    # ── Dark Web ──────────────────────────────────────────────
    dw = result.get("dark_web", {})
    dw_found = [s for s,d in dw.items() if isinstance(d,dict) and d.get("found")] if isinstance(dw,dict) else []
    if dw_found:
        lines.append(f"\n{BOLD}  {_bar('DARK WEB PRESENCE')}{NC}")
        lines.append(f"  {RED}Found in {len(dw_found)} source(s): {', '.join(dw_found)}{NC}")

    # ── Breach ────────────────────────────────────────────────
    breach = result.get("breach", {})
    hudson = breach.get("username", breach.get("email", {})) or {}
    if hudson.get("total_infections",0) > 0:
        lines.append(f"\n{BOLD}  {_bar('BREACH & CREDENTIALS')}{NC}")
        lines.append(f"  {RED}⚠  Hudson Rock: {hudson['total_infections']} infostealer infection(s){NC}")
        lines.append(f"  Credentials likely compromised!")

    # ── Keyword Alerts ────────────────────────────────────────
    kw = result.get("keyword_alerts", {})
    if kw.get("total_flags",0) > 0:
        lines.append(f"\n{BOLD}  {_bar('KEYWORD ALERTS')}{NC}")
        color = kw.get("alert_color","")
        lines.append(f"  Alert level: {color}{kw.get('alert_level','')}{NC} — {kw['total_flags']} flag(s)")
        lines.append(f"  Categories: {', '.join(kw.get('categories_flagged',[]))}")
        for f in kw.get("findings",[])[:4]:
            lines.append(f"  [{['','INFO','WARN','HIGH','CRIT'][f['severity']]}] \"{f['keyword']}\" — {f['source']}")

    # ── Timeline ──────────────────────────────────────────────
    tl = result.get("timeline", {})
    if tl.get("events"):
        lines.append(f"\n{BOLD}  {_bar('TIMELINE')}{NC}")
        ana = tl.get("analysis", {})
        lines.append(f"  {ana.get('total_events',0)} events | Span: {ana.get('span_years',0)} year(s)")
        if ana.get("is_new_account"): lines.append(f"  {YELLOW}⚠  New account (<90 days){NC}")
        if ana.get("is_dormant"): lines.append(f"  {YELLOW}⚠  Dormant (180+ days inactive){NC}")
        for evt in tl["events"][:6]:
            lines.append(f"  {CYAN}{evt['date']}{NC}  {evt['label']}")

    # ── Recommendations ───────────────────────────────────────
    if risk.get("recommendations"):
        lines.append(f"\n{BOLD}  {_bar('RECOMMENDED ACTIONS')}{NC}")
        for rec in risk["recommendations"]:
            lines.append(f"  → {rec}")

    # ── Footer ────────────────────────────────────────────────
    lines.append(f"\n{DIM}  Report generated by Zqrya v3.0 — github.com/webdev11-code/Zqrya-OSINT{NC}")
    lines.append("")

    return "\n".join(lines)


def generate_markdown_brief(result: Dict[str, Any], filename: str = "") -> str:
    """Generate Markdown version for sharing / archiving."""
    target = result.get("username","") or result.get("email","") or result.get("phone","")
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    risk = result.get("risk_score", {})
    score = risk.get("score",0); level = risk.get("level","?")
    corr = result.get("correlation", {})
    maigret = result.get("maigret", {})
    sites = maigret.get("found_sites", [])

    md = [f"# 🔍 Cyber Intelligence Report — `{target}`\n",
          f"**Generated:** {ts}  ",
          f"**Tool:** Zqrya v3.0\n",
          f"## 🎯 Risk Score: {score}/100 — {level}\n",]

    for f in risk.get("key_findings",[])[:5]:
        md.append(f"- ⚡ {f}")
    md.append("")

    if corr.get("real_names") or corr.get("correlated_emails") or corr.get("correlated_phones"):
        md.append("## 👤 Identity Correlation\n")
        if corr.get("real_names"): md.append(f"- **Real Names:** {', '.join(corr['real_names'])}")
        if corr.get("correlated_emails"): md.append(f"- **Linked Emails:** {', '.join(corr['correlated_emails'])}")
        if corr.get("correlated_phones"): md.append(f"- **Linked Phones:** {', '.join(corr['correlated_phones'])}")
        if corr.get("correlated_usernames"): md.append(f"- **Alt Usernames:** {', '.join(corr['correlated_usernames'])}")
        md.append("")

    wa_data = result.get("whatsapp_intel", {})
    if wa_data:
        wa = wa_data.get("whatsapp", {}); country = wa_data.get("country", {})
        md.append("## 📱 WhatsApp & Phone\n")
        md.append(f"- **Phone:** {wa_data.get('phone_normalized','')}")
        md.append(f"- **Country:** {country.get('flag','')} {country.get('country','')} | {country.get('carrier','')}")
        md.append(f"- **WhatsApp:** {'✅ ACTIVE' if wa.get('wa_exists') else '❌ Not Found'}")
        if wa.get("wa_link"): md.append(f"- **Chat:** [{wa['wa_link']}]({wa['wa_link']})")
        tc = wa_data.get("truecaller", {})
        if tc.get("name"): md.append(f"- **Caller Name:** {tc['name']}")
        md.append("")

    if sites:
        md.append(f"## 🌐 Social Profiles ({len(sites)} found)\n")
        md.append("| Platform | URL |")
        md.append("|---|---|")
        for site in sites[:15]:
            md.append(f"| {site.get('site_name','')} | {site.get('url_user','')} |")
        md.append("")

    gh = result.get("github_intel", {})
    if gh.get("found"):
        p = gh.get("profile", {})
        md.append("## 💻 GitHub Intelligence\n")
        md.append(f"- Profile: https://github.com/{p.get('username','')}")
        md.append(f"- Repos: {p.get('public_repos',0)} | Followers: {p.get('followers',0)}")
        emails = [e["email"] for e in gh.get("extracted_emails",[]) if isinstance(e,dict)]
        if emails: md.append(f"- **⚡ Real emails from commits:** {', '.join(emails)}")
        md.append("")

    kw = result.get("keyword_alerts", {})
    if kw.get("total_flags",0) > 0:
        md.append(f"## 🚨 Keyword Alerts — {kw['alert_level']}\n")
        md.append(f"- {kw['total_flags']} flag(s) in categories: {', '.join(kw.get('categories_flagged',[]))}")
        for f in kw.get("findings",[])[:5]:
            md.append(f"- `[{['','INFO','WARN','HIGH','CRIT'][f['severity']]}]` \"{f['keyword']}\" — {f['source']}: ...{f['context']}...")
        md.append("")

    md.append("---\n*Report generated by [Zqrya](https://github.com/webdev11-code/Zqrya-OSINT)*")
    return "\n".join(md)


async def save_full_report(result: Dict[str, Any], output_dir: str = "output") -> Dict[str, str]:
    """Save terminal + markdown + JSON reports."""
    os.makedirs(output_dir, exist_ok=True)
    target = result.get("username","") or result.get("email","") or result.get("phone","")
    safe = target.replace("@","_at_").replace("+","").replace(" ","_")[:30]
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    base = f"{output_dir}/{safe}_{ts}"

    saved = {}

    # JSON
    json_path = f"{base}.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        saved["json"] = json_path
    except Exception as e:
        saved["json_error"] = str(e)

    # Markdown
    md_path = f"{base}.md"
    try:
        md_content = generate_markdown_brief(result, md_path)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        saved["markdown"] = md_path
    except Exception as e:
        saved["markdown_error"] = str(e)

    return saved
