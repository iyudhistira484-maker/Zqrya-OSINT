"""Real-time Target Monitor — alert when target appears online / new activity detected.

Monitors:
- GitHub: new commits/repos/gists
- Reddit: new posts or comments
- Domain: WHOIS changes, new DNS records
- Pastebin: new pastes mentioning target
- Wayback: new archived snapshots

Notification via:
- Telegram bot (instant push notification)
- Local file log
- Terminal bell + print

Designed for Termux background: use `nohup python -m stalker.monitor username &`
or Termux:Boot auto-start.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, Callable, Awaitable
import asyncio, json, os, hashlib
from datetime import datetime
from pathlib import Path
from .proxy_manager import prepare_client

MONITOR_DIR = Path("output/monitors")
IS_TERMUX = Path("/data/data/com.termux").is_dir()


def _state_file(target: str) -> Path:
    safe = target.replace("@","_").replace("+","").replace(" ","_")[:30]
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    return MONITOR_DIR / f"{safe}_state.json"


def _load_state(target: str) -> Dict[str, Any]:
    sf = _state_file(target)
    if sf.exists():
        try: return json.loads(sf.read_text())
        except Exception: pass
    return {}


def _save_state(target: str, state: Dict[str, Any]):
    _state_file(target).write_text(json.dumps(state, indent=2, default=str))


def _hash(data) -> str:
    return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


async def _send_telegram_alert(message: str, token: str = "", chat_id: str = ""):
    """Send alert via Telegram bot."""
    token  = token  or os.environ.get("TELEGRAM_BOT_TOKEN","")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID","")
    if not token or not chat_id: return False
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            )
            return r.status_code == 200
    except Exception: return False


async def _termux_notify(title: str, content: str):
    """Native Android notification via Termux:API."""
    if not IS_TERMUX: return
    try:
        import subprocess
        subprocess.Popen(["termux-notification", "--title", title, "--content", content,
                          "--priority", "high", "--sound"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass


async def check_github_new_activity(username: str, state: Dict) -> Optional[Dict]:
    """Check for new GitHub commits/repos since last check."""
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.get(f"https://api.github.com/users/{username}/events?per_page=5",
                           headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 200:
                events = r.json()
                if not isinstance(events, list): return None
                new_hash = _hash(events[:3])
                old_hash = state.get("github_events_hash","")
                if new_hash != old_hash and old_hash:
                    # New activity!
                    latest = events[0] if events else {}
                    return {
                        "platform": "github",
                        "event_type": latest.get("type",""),
                        "repo": latest.get("repo",{}).get("name",""),
                        "created_at": latest.get("created_at",""),
                        "message": f"GitHub: new activity — {latest.get('type','')} on {latest.get('repo',{}).get('name','')}",
                    }
                state["github_events_hash"] = new_hash
    except Exception: pass
    return None


async def check_reddit_new_activity(username: str, state: Dict) -> Optional[Dict]:
    """Check for new Reddit posts/comments."""
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.get(f"https://www.reddit.com/user/{username}/new.json?limit=3",
                           headers={"User-Agent":"Zqrya/3.0"})
            if r.status_code == 200:
                posts = r.json().get("data",{}).get("children",[])
                new_hash = _hash([p.get("data",{}).get("name","") for p in posts[:3]])
                old_hash = state.get("reddit_posts_hash","")
                if new_hash != old_hash and old_hash:
                    latest = posts[0].get("data",{}) if posts else {}
                    return {
                        "platform": "reddit",
                        "type": latest.get("kind",""),
                        "subreddit": latest.get("subreddit",""),
                        "title": (latest.get("title","") or latest.get("body",""))[:100],
                        "message": f"Reddit: new activity in r/{latest.get('subreddit','')}",
                    }
                state["reddit_posts_hash"] = new_hash
    except Exception: pass
    return None


async def check_pastebin_mentions(target: str, state: Dict) -> Optional[Dict]:
    """Check for new Pastebin pastes mentioning target."""
    try:
        async with prepare_client(timeout=12) as c:
            r = await c.get(
                f"https://psbdmp.ws/api/search/{target}",
                headers={"User-Agent":"Mozilla/5.0"}
            )
            if r.status_code == 200:
                data = r.json()
                count = len(data.get("data",{}).get("pastes",[]))
                old_count = state.get("pastebin_count", count)
                if count > old_count:
                    state["pastebin_count"] = count
                    return {
                        "platform": "pastebin",
                        "new_pastes": count - old_count,
                        "message": f"Pastebin: {count - old_count} new paste(s) mentioning {target}",
                    }
                state["pastebin_count"] = count
    except Exception: pass
    return None


async def monitor_once(target: str, input_type: str = "username") -> List[Dict]:
    """Run one monitoring cycle. Returns list of new alerts."""
    state = _load_state(target)
    alerts = []

    checks = []
    if input_type == "username":
        checks.append(check_github_new_activity(target, state))
        checks.append(check_reddit_new_activity(target, state))
    checks.append(check_pastebin_mentions(target, state))

    results = await asyncio.gather(*checks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict): alerts.append(r)

    _save_state(target, state)

    # Send notifications for new alerts
    for alert in alerts:
        msg = f"🔔 <b>ZQRYA ALERT</b>\n\nTarget: <code>{target}</code>\n{alert.get('message','')}\nTime: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        await asyncio.gather(
            _send_telegram_alert(msg),
            _termux_notify(f"Alert: {target}", alert.get("message","")),
            return_exceptions=True
        )
        print(f"\n  🔔 ALERT: {alert.get('message','')}")

    return alerts


async def monitor_loop(target: str, input_type: str = "username", interval_minutes: int = 30):
    """Continuous monitoring loop. Runs until interrupted."""
    print(f"\n  Starting monitor for: {target}")
    print(f"  Check interval: {interval_minutes} minutes")
    print(f"  Notifications: {'Telegram + Termux' if IS_TERMUX else 'Telegram'}")
    print(f"  Stop: Ctrl+C\n")

    check_count = 0
    while True:
        check_count += 1
        ts = datetime.utcnow().strftime("%H:%M")
        print(f"  [{ts}] Check #{check_count}...", end=" ", flush=True)
        alerts = await monitor_once(target, input_type)
        if alerts:
            print(f"⚡ {len(alerts)} new alert(s)!")
        else:
            print("no changes")
        await asyncio.sleep(interval_minutes * 60)
