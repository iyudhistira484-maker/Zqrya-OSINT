"""Intelligence Timeline Builder — chronological activity reconstruction.

Builds a unified timeline from:
- Account creation dates (Maigret, GitHub, Reddit)
- Last active dates
- Post/commit timestamps
- Breach dates
- Snapshot history (Wayback Machine)
- Telegram join dates

Useful for:
- Establishing when target first appeared online
- Detecting coordinated account creation (bot/fake indicator)
- Reconstructing timeline of events
- Identifying gaps (went dark after specific date)
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d", "%Y%m%d",
]

def parse_date(s: str) -> Optional[datetime]:
    if not s: return None
    s = str(s).strip()
    for fmt in TIMESTAMP_FORMATS:
        try: return datetime.strptime(s[:len(fmt)], fmt)
        except Exception: continue
    # Unix timestamp
    try:
        ts = float(s)
        if ts > 1e9: return datetime.utcfromtimestamp(ts)
    except Exception: pass
    return None

def fmt_date(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "unknown"

def build_timeline(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all timestamped events from investigation result."""
    events: List[Dict[str, Any]] = []

    def add(dt_str: str, label: str, source: str, detail: str = ""):
        dt = parse_date(dt_str)
        if dt:
            events.append({
                "datetime": dt, "date": fmt_date(dt),
                "label": label, "source": source, "detail": detail,
            })

    # ── GitHub ────────────────────────────────────────────────
    gh = result.get("github_intel", {})
    gh_profile = gh.get("profile", {})
    if gh_profile.get("created_at"):
        add(gh_profile["created_at"], "GitHub account created", "github", f"@{gh_profile.get('username','')}")
    for commit in gh.get("extracted_emails", []):
        if isinstance(commit, dict) and commit.get("date"):
            add(commit["date"], "GitHub commit (email exposed)", "github_commit", commit.get("repo",""))

    # ── Reddit ────────────────────────────────────────────────
    reddit = result.get("reddit_intel", {})
    rp = reddit.get("profile", {})
    if rp.get("created_at"):
        add(rp["created_at"], "Reddit account created", "reddit", f"u/{rp.get('username','')}")
    for post in reddit.get("recent_posts", []):
        if post.get("created_utc"):
            add(str(post["created_utc"]), f"Reddit post: {post.get('title','')[:50]}", "reddit_post", post.get("subreddit",""))
    for comment in reddit.get("recent_comments", []):
        if comment.get("created_utc"):
            add(str(comment["created_utc"]), "Reddit comment", "reddit_comment", comment.get("subreddit",""))

    # ── Wayback Machine (first/last seen) ─────────────────────
    wayback = result.get("wayback_intel", {})
    for platform, wb_data in wayback.get("platforms_archived", {}).items():
        if wb_data.get("first_seen"):
            add(wb_data["first_seen"], f"First archived: {platform} profile", "wayback", wb_data.get("snapshot_url",""))
        if wb_data.get("last_seen") and wb_data.get("last_seen") != wb_data.get("first_seen"):
            add(wb_data["last_seen"], f"Last archived: {platform} profile", "wayback", "")

    # ── Maigret profiles ──────────────────────────────────────
    for site in result.get("maigret", {}).get("found_sites", []):
        for date_field in ["created", "joined", "registered", "created_at"]:
            val = (site.get("ids_data") or {}).get(date_field) or site.get(date_field,"")
            if val:
                add(str(val), f"Profile: {site.get('site_name','')}", "maigret_profile", site.get("url_user",""))
                break

    # ── Custom APIs ───────────────────────────────────────────
    for platform, data in result.get("custom_apis", {}).items():
        if isinstance(data, dict):
            for field in ["created_at", "joined", "registered"]:
                if data.get(field):
                    add(data[field], f"{platform} account", f"custom_api:{platform}", "")
                    break

    # ── Sort chronologically ──────────────────────────────────
    events.sort(key=lambda e: e["datetime"])
    return events


def analyze_timeline(events: List[Dict]) -> Dict[str, Any]:
    if not events: return {"total_events": 0}
    first = events[0]
    last = events[-1]
    span_days = (last["datetime"] - first["datetime"]).days
    # Detect burst activity (many events within short period)
    bursts = []
    for i in range(len(events)-2):
        delta = (events[i+1]["datetime"] - events[i]["datetime"]).days
        if delta <= 1:
            bursts.append(events[i]["date"])
    return {
        "total_events": len(events),
        "first_event": first,
        "last_event": last,
        "span_days": span_days,
        "span_years": round(span_days / 365, 1),
        "burst_periods": list(set(bursts))[:5],
        "is_new_account": span_days < 90,
        "is_dormant": span_days > 0 and (datetime.utcnow() - last["datetime"]).days > 180,
    }


def format_timeline(events: List[Dict], analysis: Dict) -> str:
    BOLD = "\033[1m"; CYAN = "\033[36m"; NC = "\033[0m"; DIM = "\033[2m"
    lines = [f"\n{BOLD}  ┌─── INTELLIGENCE TIMELINE ───┐{NC}"]
    lines.append(f"  {analysis.get('total_events',0)} events | Span: {analysis.get('span_years',0)} year(s)")
    if analysis.get("is_new_account"): lines.append(f"  ⚠  New account — created <90 days ago")
    if analysis.get("is_dormant"): lines.append(f"  ⚠  Dormant — no activity for 180+ days")
    lines.append("")
    for evt in events[:20]:
        source_label = f"{DIM}[{evt['source']}]{NC}"
        lines.append(f"  {CYAN}{evt['date']}{NC}  {evt['label']}  {source_label}")
        if evt.get("detail"): lines.append(f"              {DIM}{evt['detail'][:60]}{NC}")
    if len(events) > 20: lines.append(f"  ... and {len(events)-20} more events")
    return "\n".join(lines)
