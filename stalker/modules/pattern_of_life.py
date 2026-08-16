"""Pattern of Life Analyzer — reconstruct behavioral patterns from timestamps.

From posting timestamps across Reddit, GitHub, Twitter etc:
- Exact timezone estimation (not just region — down to UTC offset)
- Sleep/wake schedule
- Work hours vs personal hours
- Weekend vs weekday activity ratio
- Peak activity windows
- Inactivity gaps (went dark = event happened?)
- Account automation detection (too regular = bot)

Zero network calls — pure data analysis on already-collected timestamps.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import math
from collections import Counter, defaultdict


def extract_all_timestamps(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract every timestamp from all investigation sources."""
    events = []

    def add(ts, source: str, label: str = ""):
        if ts:
            try:
                if isinstance(ts, (int, float)) and ts > 1e9:
                    dt = datetime.utcfromtimestamp(float(ts))
                elif isinstance(ts, str):
                    for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
                                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                                "%Y-%m-%d", "%Y%m%d"]:
                        try:
                            dt = datetime.strptime(ts[:len(fmt)], fmt)
                            break
                        except Exception:
                            continue
                    else:
                        return
                elif isinstance(ts, datetime):
                    dt = ts
                else:
                    return
                events.append({"dt": dt, "source": source, "label": label,
                               "hour": dt.hour, "weekday": dt.weekday(),
                               "timestamp": dt.timestamp()})
            except Exception:
                pass

    # Reddit
    reddit = result.get("reddit_intel", {})
    for post in reddit.get("recent_posts", []):
        add(post.get("created_utc"), "reddit_post", post.get("title","")[:30])
    for comment in reddit.get("recent_comments", []):
        add(comment.get("created_utc"), "reddit_comment", "")

    # GitHub commits
    gh = result.get("github_intel", {})
    for commit in gh.get("extracted_emails", []):
        if isinstance(commit, dict):
            add(commit.get("date"), "github_commit", commit.get("repo",""))

    # Timeline events (already parsed)
    tl = result.get("timeline", {})
    for evt in tl.get("events", []):
        add(evt.get("date"), evt.get("source",""), evt.get("label",""))

    # Custom APIs
    for platform, data in result.get("custom_apis", {}).items():
        if isinstance(data, dict):
            for field in ["last_seen", "last_active", "updated_at", "last_post"]:
                if data.get(field):
                    add(data[field], f"custom:{platform}", field)

    return sorted(events, key=lambda e: e["timestamp"])


def estimate_timezone(events: List[Dict]) -> Dict[str, Any]:
    """Estimate UTC offset from peak activity hours.
    
    Assumes people are most active 18:00-23:00 local time.
    Peak UTC hour - 20 (local evening) = UTC offset.
    """
    if not events:
        return {"utc_offset": None, "confidence": 0}

    hours = [e["hour"] for e in events]
    hour_counts = Counter(hours)

    # Find peak activity window (3-hour block)
    best_window = 0
    best_count = 0
    for start in range(24):
        window = sum(hour_counts.get((start + i) % 24, 0) for i in range(3))
        if window > best_count:
            best_count = window
            best_window = start

    peak_hour = best_window + 1  # center of window

    # Estimate: people typically peak at ~20:00 local time (after work/dinner)
    assumed_local_peak = 20
    utc_offset = (peak_hour - assumed_local_peak) % 24
    if utc_offset > 12:
        utc_offset -= 24

    # Timezone mapping
    TZ_MAP = {
        7: "WIB (Indonesia Barat)", 8: "WITA (Indonesia Tengah) / SGT (Singapore) / MYT (Malaysia)",
        9: "WIT (Indonesia Timur) / JST (Japan)", -5: "EST (USA East)",
        -6: "CST (USA Central)", -7: "MST (USA Mountain)", -8: "PST (USA West)",
        0: "GMT/UTC (UK)", 1: "CET (Europe West)", 2: "EET (Europe East)",
        3: "MSK (Moscow) / AST (Arab)", 5.5: "IST (India)", 10: "AEST (Australia East)",
    }

    tz_name = TZ_MAP.get(utc_offset, f"UTC{'+' if utc_offset >= 0 else ''}{utc_offset}")
    confidence = min(100, int((best_count / max(len(events), 1)) * 200))

    return {
        "utc_offset": utc_offset,
        "timezone_name": tz_name,
        "peak_hour_utc": peak_hour,
        "peak_local_estimate": assumed_local_peak,
        "confidence_pct": confidence,
        "activity_by_hour": dict(sorted(hour_counts.items())),
    }


def estimate_sleep_schedule(events: List[Dict]) -> Dict[str, Any]:
    """Estimate sleep/wake times from activity gaps."""
    if len(events) < 10:
        return {}

    hours = [e["hour"] for e in events]
    hour_counts = Counter(hours)
    total = len(events)

    # Find lowest activity period (sleep window = 3+ consecutive low-activity hours)
    low_threshold = total * 0.02  # <2% of activity per hour = sleep
    sleep_hours = [h for h in range(24) if hour_counts.get(h, 0) <= low_threshold]

    # Find longest consecutive sleep window
    best_start = None
    best_len = 0
    current_start = None
    current_len = 0

    for h in range(48):
        if h % 24 in sleep_hours:
            if current_start is None:
                current_start = h % 24
                current_len = 1
            else:
                current_len += 1
            if current_len > best_len:
                best_len = current_len
                best_start = current_start
        else:
            current_start = None
            current_len = 0

    if best_start is None:
        return {}

    wake_utc = (best_start + best_len) % 24
    sleep_utc = best_start

    return {
        "sleep_start_utc": sleep_utc,
        "wake_start_utc": wake_utc,
        "sleep_duration_hrs": best_len,
        "note": f"Low activity {sleep_utc:02d}:00-{wake_utc:02d}:00 UTC",
    }


def analyze_weekday_pattern(events: List[Dict]) -> Dict[str, Any]:
    """Weekday vs weekend activity."""
    if not events:
        return {}
    DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    day_counts = Counter(e["weekday"] for e in events)
    weekday = sum(day_counts.get(d, 0) for d in range(5))
    weekend = sum(day_counts.get(d, 0) for d in range(5, 7))
    total = weekday + weekend
    return {
        "weekday_pct": round(weekday / total * 100) if total else 0,
        "weekend_pct": round(weekend / total * 100) if total else 0,
        "busiest_day": DAYS[day_counts.most_common(1)[0][0]] if day_counts else "",
        "quietest_day": DAYS[day_counts.most_common()[-1][0]] if day_counts else "",
        "by_day": {DAYS[d]: day_counts.get(d, 0) for d in range(7)},
    }


def detect_automation(events: List[Dict]) -> Dict[str, Any]:
    """Detect bot/automated account from posting regularity."""
    if len(events) < 20:
        return {"is_bot": False, "confidence": 0}

    # Calculate intervals between posts
    sorted_ts = sorted(e["timestamp"] for e in events)
    intervals = [sorted_ts[i+1] - sorted_ts[i] for i in range(len(sorted_ts)-1)]

    if not intervals:
        return {"is_bot": False, "confidence": 0}

    avg = sum(intervals) / len(intervals)
    variance = sum((x - avg) ** 2 for x in intervals) / len(intervals)
    std_dev = math.sqrt(variance)
    cv = std_dev / avg if avg > 0 else 0  # Coefficient of variation

    # Bots have very low CV (posts at exact intervals)
    # Humans have high CV (irregular posting)
    is_bot = cv < 0.3 and len(events) >= 30
    confidence = max(0, int((1 - cv) * 100)) if cv < 1 else 0

    return {
        "is_bot": is_bot,
        "coefficient_of_variation": round(cv, 3),
        "avg_interval_minutes": round(avg / 60, 1),
        "confidence": confidence,
        "verdict": "Likely automated/bot" if is_bot else "Human posting pattern",
    }


def detect_inactivity_gaps(events: List[Dict]) -> List[Dict]:
    """Find suspicious gaps — went silent after key event?"""
    if len(events) < 2:
        return []
    sorted_ts = sorted(e["timestamp"] for e in events)
    gaps = []
    for i in range(len(sorted_ts) - 1):
        delta_days = (sorted_ts[i+1] - sorted_ts[i]) / 86400
        if delta_days >= 30:
            start = datetime.utcfromtimestamp(sorted_ts[i])
            end = datetime.utcfromtimestamp(sorted_ts[i+1])
            gaps.append({
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
                "days": round(delta_days),
                "suspicious": delta_days >= 90,
            })
    return sorted(gaps, key=lambda g: -g["days"])[:5]


def full_pattern_of_life(result: Dict[str, Any]) -> Dict[str, Any]:
    events = extract_all_timestamps(result)
    if not events:
        return {"total_events": 0, "note": "No timestamps available for analysis"}

    tz = estimate_timezone(events)
    sleep = estimate_sleep_schedule(events)
    weekday = analyze_weekday_pattern(events)
    automation = detect_automation(events)
    gaps = detect_inactivity_gaps(events)

    return {
        "total_events_analyzed": len(events),
        "timezone": tz,
        "sleep_schedule": sleep,
        "weekday_pattern": weekday,
        "automation": automation,
        "inactivity_gaps": gaps,
        "sources": list(set(e["source"] for e in events)),
    }


def format_pattern_report(data: Dict[str, Any]) -> str:
    BOLD = "\033[1m"; CYAN = "\033[36m"; YELLOW = "\033[33m"
    RED = "\033[31m"; GREEN = "\033[32m"; NC = "\033[0m"

    if not data.get("total_events_analyzed"):
        return "  Pattern of Life: insufficient data"

    lines = [f"\n{BOLD}  ┌─── PATTERN OF LIFE ANALYSIS ───┐{NC}"]
    lines.append(f"  Analyzed {data['total_events_analyzed']} timestamps from: {', '.join(data.get('sources',[]))}")

    tz = data.get("timezone", {})
    if tz.get("timezone_name"):
        lines.append(f"\n  {BOLD}Timezone (estimated):{NC}")
        lines.append(f"  → {CYAN}{tz['timezone_name']}{NC}  (UTC{'+' if tz.get('utc_offset',0)>=0 else ''}{tz.get('utc_offset','')})")
        lines.append(f"  → Confidence: {tz.get('confidence_pct',0)}%")
        lines.append(f"  → Peak UTC hour: {tz.get('peak_hour_utc','')}:00")

    sleep = data.get("sleep_schedule", {})
    if sleep.get("sleep_start_utc") is not None:
        lines.append(f"\n  {BOLD}Sleep Schedule (UTC):{NC}")
        lines.append(f"  → Likely asleep: {sleep['sleep_start_utc']:02d}:00 – {sleep['wake_start_utc']:02d}:00 UTC")
        lines.append(f"  → Sleep duration: ~{sleep.get('sleep_duration_hrs',0)} hours")

    wd = data.get("weekday_pattern", {})
    if wd:
        lines.append(f"\n  {BOLD}Weekly Activity:{NC}")
        lines.append(f"  → Weekday: {wd.get('weekday_pct',0)}%  |  Weekend: {wd.get('weekend_pct',0)}%")
        lines.append(f"  → Most active: {wd.get('busiest_day','')}  |  Least: {wd.get('quietest_day','')}")

    auto = data.get("automation", {})
    if auto.get("is_bot"):
        lines.append(f"\n  {RED}⚠  AUTOMATION DETECTED: {auto.get('verdict','')}{NC}")
        lines.append(f"  → Average post interval: {auto.get('avg_interval_minutes',0)} min")
    elif auto.get("confidence", 0) > 0:
        lines.append(f"\n  {GREEN}Human posting pattern{NC} (CV={auto.get('coefficient_of_variation',0)})")

    gaps = data.get("inactivity_gaps", [])
    if gaps:
        lines.append(f"\n  {BOLD}Suspicious Inactivity Gaps:{NC}")
        for g in gaps[:3]:
            mark = f"{RED}[SUSPICIOUS]{NC}" if g["suspicious"] else ""
            lines.append(f"  → {g['start']} → {g['end']} ({g['days']} days) {mark}")

    return "\n".join(lines)
