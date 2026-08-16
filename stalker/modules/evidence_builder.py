"""Evidence Builder — compile formal cyber investigation report.

Generates a professional evidence dossier including:
- Chain of custody (timestamps, sources, investigator notes)
- Structured evidence catalog (each finding = one evidence item)
- Source URLs for verification
- Screenshot text evidence from social profiles
- Risk classification per finding
- Export formats: Markdown, TXT, JSON

Format follows law enforcement intelligence report conventions.
"""
from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime
import json, os, re

SEV = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "INFO"}
SEV_COLOR = {4:"\033[35m", 3:"\033[31m", 2:"\033[33m", 1:"\033[36m", 0:"\033[37m"}

def build_evidence_catalog(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    catalog = []
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    target = result.get("username","") or result.get("email","") or result.get("phone","")

    def add(title, description, source_url="", severity=0, category="", raw_data=None):
        catalog.append({
            "id": f"EVD-{len(catalog)+1:04d}",
            "timestamp": ts,
            "target": target,
            "title": title,
            "description": description,
            "source_url": source_url,
            "severity": severity,
            "severity_label": SEV.get(severity,"INFO"),
            "category": category,
            "raw_data": raw_data or {},
        })

    # Social profiles
    for site in result.get("maigret",{}).get("found_sites",[]):
        add(f"Profile found: {site.get('site_name','')}",
            f"Username found on {site.get('site_name','')}. Real name: {site.get('real_name','N/A')}. "
            f"Location: {site.get('location','N/A')}. Bio: {(site.get('bio','') or '')[:100]}",
            source_url=site.get("url_user",""), severity=1, category="social_profile",
            raw_data={"site": site.get("site_name",""), "url": site.get("url_user","")})

    # GitHub emails
    for email_data in result.get("github_intel",{}).get("extracted_emails",[]):
        if isinstance(email_data,dict):
            add(f"Real email extracted: {email_data.get('email','')}",
                f"Email {email_data['email']} found in Git commit by {email_data.get('name','')} "
                f"in repo {email_data.get('repo','')} on {email_data.get('date','')[:10]}",
                source_url=f"https://github.com/{result.get('username','')}/{email_data.get('repo','')}",
                severity=3, category="email_leak", raw_data=email_data)

    # WhatsApp
    wa = result.get("whatsapp_intel",{})
    if wa.get("whatsapp",{}).get("wa_exists"):
        add(f"WhatsApp active: {wa.get('phone_normalized','')}",
            f"Phone number has active WhatsApp. Country: {wa.get('country',{}).get('country','')}. "
            f"Carrier: {wa.get('country',{}).get('carrier','')}. Is business: {wa.get('whatsapp',{}).get('is_business',False)}",
            source_url=wa.get("whatsapp",{}).get("wa_link",""),
            severity=2, category="phone_intelligence", raw_data={"phone": wa.get("phone_normalized","")})

    # Breach data
    hudson = result.get("breach",{}).get("username",result.get("breach",{}).get("email",{})) or {}
    if hudson.get("total_infections",0) > 0:
        add(f"Infostealer infection: {hudson['total_infections']} device(s)",
            f"Hudson Rock database shows {hudson['total_infections']} infostealer infections. "
            f"Credentials are likely compromised. Infection dates: {hudson.get('dates',[])}",
            source_url="https://cavalier.hudsonrock.com", severity=4, category="breach",
            raw_data=hudson)

    # Dark web
    for source, dw_data in result.get("dark_web",{}).items():
        if isinstance(dw_data,dict) and dw_data.get("found"):
            add(f"Dark web presence: {source}",
                f"Target found in {source} with {dw_data.get('count',0)} record(s). "
                f"Sample URLs: {', '.join(str(p.get('url','')) for p in dw_data.get('pastes',[])[:2])}",
                severity=3, category="dark_web", raw_data=dw_data)

    # Keyword alerts
    for flag in result.get("keyword_alerts",{}).get("findings",[]):
        if flag.get("severity",0) >= 2:
            add(f"Keyword flag: {flag['keyword']} [{flag['category']}]",
                f"Found in {flag['source']}: ...{flag.get('context','')}...",
                severity=flag["severity"], category="keyword_alert", raw_data=flag)

    # Gravatar
    grav = result.get("gravatar",{})
    if grav.get("found"):
        add(f"Gravatar profile found",
            f"Display name: {grav.get('display_name','')}. Location: {grav.get('location','')}. "
            f"Linked accounts: {', '.join(a.get('domain','') for a in grav.get('accounts',[])[:5])}",
            source_url=grav.get("profile_url",""), severity=1, category="social_profile")

    # Crypto wallets
    for addr, trace in result.get("crypto_trace",{}).get("traces",{}).items():
        add(f"Crypto wallet: {addr[:20]}...",
            f"{trace.get('chain','').upper()} wallet with {trace.get('n_tx',0)} transactions. "
            f"First tx: {trace.get('first_tx','')}. Balance: {trace.get('balance_btc',trace.get('balance_eth',''))}",
            source_url=trace.get("explorer_url",""), severity=2, category="financial", raw_data=trace)

    # Timeline anomalies
    tl_analysis = result.get("timeline",{}).get("analysis",{})
    if tl_analysis.get("is_new_account"):
        add("Account created recently (<90 days)",
            f"Digital footprint spans only {tl_analysis.get('span_days',0)} days. "
            f"May be fake/newly created account.",
            severity=2, category="timeline_anomaly")

    # Automation
    pol = result.get("pattern_of_life",{})
    auto = pol.get("automation",{})
    if auto.get("is_bot"):
        add("Bot/automation detected",
            f"{auto.get('verdict','')}. CV={auto.get('coefficient_of_variation',0)}. "
            f"Average post interval: {auto.get('avg_interval_minutes',0)} minutes.",
            severity=3, category="behavior_anomaly", raw_data=auto)

    return sorted(catalog, key=lambda e: -e["severity"])


def generate_evidence_report(result: Dict[str, Any]) -> str:
    """Generate formal evidence report text."""
    target = result.get("username","") or result.get("email","") or result.get("phone","")
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    catalog = build_evidence_catalog(result)
    risk = result.get("risk_score",{})

    BOLD="\033[1m"; RED="\033[31m"; YELLOW="\033[33m"; CYAN="\033[36m"; NC="\033[0m"; DIM="\033[2m"

    lines = [
        f"\n{BOLD}{'═'*52}{NC}",
        f"{BOLD}  CYBER INVESTIGATION DOSSIER{NC}",
        f"{'═'*52}",
        f"  Case Subject:  {BOLD}{target}{NC}",
        f"  Report Date:   {ts}",
        f"  Tool:          Zqrya v3.0",
        f"  Evidence Items: {len(catalog)}",
        f"  Risk Score:    {risk.get('score',0)}/100 — {risk.get('level','')}",
        f"{'═'*52}\n",
    ]

    cat_groups = {}
    for ev in catalog:
        cat_groups.setdefault(ev["category"], []).append(ev)

    for cat, items in cat_groups.items():
        lines.append(f"{BOLD}  ▶ {cat.replace('_',' ').upper()} ({len(items)} item(s)){NC}")
        for ev in items:
            color = SEV_COLOR.get(ev["severity"],"\033[0m")
            lines.append(f"  [{color}{ev['severity_label']}{NC}] {ev['id']} {ev['title']}")
            lines.append(f"  {DIM}{ev['description'][:120]}{NC}")
            if ev.get("source_url"): lines.append(f"  Source: {ev['source_url'][:80]}")
            lines.append("")

    lines.append(f"{'═'*52}")
    lines.append(f"  END OF DOSSIER — {len(catalog)} evidence items cataloged")
    lines.append(f"{'═'*52}")
    return "\n".join(lines)


async def save_evidence_dossier(result: Dict[str, Any], output_dir: str = "output") -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    target = (result.get("username","") or result.get("email","") or result.get("phone",""))
    safe = re.sub(r'[^a-z0-9_]', '_', target.lower())[:30]
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    catalog = build_evidence_catalog(result)
    saved = {}

    # JSON dossier
    json_path = f"{output_dir}/{safe}_{ts}_dossier.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"target": target, "timestamp": ts, "evidence_count": len(catalog),
                       "risk_score": result.get("risk_score",{}), "catalog": catalog}, f, indent=2, default=str)
        saved["dossier_json"] = json_path
    except Exception as e: saved["dossier_json_error"] = str(e)

    # Markdown dossier
    md_lines = [f"# Cyber Investigation Dossier — `{target}`\n",
                f"**Date:** {ts} | **Evidence items:** {len(catalog)}\n",
                f"**Risk Score:** {result.get('risk_score',{}).get('score',0)}/100 — "
                f"{result.get('risk_score',{}).get('level','')}\n",
                "## Evidence Catalog\n"]
    for ev in catalog:
        md_lines.append(f"### {ev['id']} — {ev['title']}")
        md_lines.append(f"- **Severity:** {ev['severity_label']}")
        md_lines.append(f"- **Category:** {ev['category']}")
        md_lines.append(f"- **Description:** {ev['description']}")
        if ev.get("source_url"): md_lines.append(f"- **Source:** [{ev['source_url']}]({ev['source_url']})")
        md_lines.append("")

    md_path = f"{output_dir}/{safe}_{ts}_dossier.md"
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
        saved["dossier_md"] = md_path
    except Exception as e: saved["dossier_md_error"] = str(e)

    return saved
