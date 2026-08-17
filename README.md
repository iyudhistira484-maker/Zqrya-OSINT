<div align="center">

<img src="assets/webui-dashboard.png" alt="Zqrya Web UI Dashboard" width="900"/>

# 🕵️ Zqrya v3.0

### The Ultimate API-Free OSINT Framework

**Zero API Keys • 100% Public Data • Made in Indonesia 🇮🇩**

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Version](https://img.shields.io/badge/Version-3.0.0-8b5cf6?style=for-the-badge&logo=semanticrelease&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Platforms](https://img.shields.io/badge/Username%20Platforms-160%2B-blueviolet?style=for-the-badge&logo=githubsponsors&logoColor=white)]()
[![Made in Indonesia](https://img.shields.io/badge/MADE_IN-INDONESIA-red?style=for-the-badge&logo=ko-fi&logoColor=white)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=for-the-badge&logo=git&logoColor=white)](CONTRIBUTING.md)

> **OSINT Intelligence Suite** — investigate usernames, emails, phone numbers, domains, IPs, NIK/NKK,
> and more from **public data only**. No API keys. No registration. Fast, async, and free.

</div>

---

## 📑 Table of Contents

| Section | Description |
|---------|-------------|
| [Features](#-core-features) | What Zqrya can do |
| [Quick Start](#-quick-start) | Install + first scan (2 minutes) |
| [Interactive Shell](#-interactive-shell) | 27-tool menu-driven CLI |
| [CLI Reference](#-cli-reference) | One-liners for every tool |
| [OSINT Tools](#-osint-tools) | NIK, NKK, QR, e-wallet, HLR & more |
| [IP Logger](#-ip-logger--tracking-links) | Capture IPs with a tracking link |
| [Web UI](#-web-ui--professional-dashboard) | Localhost dashboard |
| [Full Pipeline](#-full-intelligence-pipeline) | Maigret 600+ & dark web |
| [Configuration](#-configuration) | `.env` options |
| [Reports & Batch](#-reports--batch-processing) | Export + multi-target scans |
| [Disclaimer](#-legal-disclaimer) | Read before using |

---

## ⚡ Core Features

| # | Feature | What It Means |
|---|---------|---------------|
| 1 | **Zero API Keys** | Use immediately — no signup, no payment, no hidden costs |
| 2 | **27 Tools, One Shell** | Everything from username scans to NIK/NKK to IP logging |
| 3 | **Async & Fast** | Parallel scanning across platforms |
| 4 | **Auto Detect** | Paste anything, Zqrya detects the entity type |
| 5 | **Web UI** | Professional dashboard with dark/light theme |
| 6 | **Maigret 600+** | Deep username search with real names, avatars, bios |
| 7 | **Dark Web Check** | Paste sites + breach DBs (GhostProject, Psbdmp, IntelX...) |
| 8 | **NIK / NKK Lookup** | Parse & validate Indonesian ID / Family Card numbers |
| 9 | **IP Logger** | Tracking link → captures target IP + device + geo live |
| 10 | **E-wallet OSINT** | GoPay / OVO / DANA / ShopeePay / LinkAja / Sakuku |
| 11 | **QR/Barcode Decoder** | Decode from file or URL, expand short links, WiFi creds |
| 12 | **Phone HLR** | Carrier, line type, live status (best-effort) |
| 13 | **Gaming OSINT** | Steam + Roblox + Minecraft profile data |
| 14 | **Exposed Devices** | Shodan InternetDB: ports, CVEs, tags |
| 15 | **Visual Geolocation** | EXIF GPS + reverse-image search links |
| 16 | **Username Variants** | 150+ permutations for deeper searches |
| 17 | **Batch Processing** | Scan multiple targets from one file |
| 18 | **4 Report Formats** | JSON, HTML, TXT, Markdown |

---

## 🚀 Quick Start

> ⚠️ **GeoIP database is required** — Zqrya blocks access until at least one local
> GeoIP database is present (offline IP geolocation). One command downloads it, no account needed.

### Installation

```bash
# 1. Clone
git clone https://github.com/webdev11-code/Zqrya-OSINT.git
cd Zqrya-OSINT

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install vendored Maigret engine (600+ platforms)
pip install -e maigret/

# 4. Download GeoIP database (~60 MB, keyless) — REQUIRED before first run
python sources/download_geoip.py

# 5. Verify
python zqrya.py -h
```

> **GeoIP options:** DB-IP Lite (default, no account) · `MAXMIND_LICENSE_KEY=... python sources/download_geoip.py --geoip2` for GeoLite2 · `IP2LOCATION_TOKEN=... --ip2location` for IP2Location. Use `--all` for all three.

### First Scan

```bash
# Interactive shell (menu-driven)
python zqrya.py

# One-liners
python zqrya.py -u username          # Username OSINT (160+ platforms)
python zqrya.py -e user@gmail.com    # Email + breach check
python zqrya.py -p 08123456789       # Phone (8 countries)
python zqrya.py -d example.com       # Domain recon + WHOIS
python zqrya.py -i 8.8.8.8           # IP geolocation + risk
python zqrya.py -url https://site.com # Website footprint
python zqrya.py -m username          # Maigret deep search (600+)
python zqrya.py --darkweb user@gmail.com  # Dark web / breach
python zqrya.py --full username      # Combined: Zqrya + deep pipeline
python zqrya.py --variants username  # 150+ username variants
python zqrya.py -web                 # Launch web dashboard
```

---

## 🖥️ Interactive Shell

Run `python zqrya.py` (or `python zqrya.py -sh`) — a complete **27-tool menu**:

```
 1.  👤  Username OSINT                       15.  👛  E-wallet OSINT
 2.  📧  Email OSINT                          16.  🟢  Status online checker
 3.  📱  Phone OSINT                          17.  📶  Phone HLR lookup
 4.  🌐  Domain Recon                         18.  ↩️  Reverse email
 5.  🌍  IP Address                           19.  🎮  Gaming OSINT
 6.  🕸️  Website Footprint (URL)              20.  📸  IG/TikTok deep
 7.  🧠  Maigret Deep Search (600+)           21.  🖧  Exposed device search
 8.  🌑  Dark Web / Breach Check              22.  📍  Visual geolocation
 9.  🧬  Username Variants                    23.  🎯  IP Logger (tracking link)
10.  🚀  Combined OSINT (Full Pipeline)       24.  🖥️  Launch Web Dashboard
11.  📦  Batch Scan                           25.  🕘  History
12.  🪪  NIK/KTP lookup                       26.  ⚙️  Settings
13.  📇  NKK / Kartu Keluarga                 27.  ℹ️  About / Help
14.  🔳  QR/barcode decoder                    0.  🚪  Exit
```

**In-shell commands:** `u <name>` · `e <email>` · `p <phone>` · `d <domain>` · `i <ip>` · `url <url>` · `m <name>` · `dw <target>` · `var <name>` · `full <target>` · `batch <file>` · `deep` · `report` · `set-format <fmt>` · `history` / `again <n>` · `web` · `help` / `menu` / `clear` / `exit`

---

## 🔧 CLI Reference

Zqrya ships with **two CLIs**: `zqrya.py` (quick scans + shell) and `stalker` (per-tool commands).

```bash
# zqrya.py
python zqrya.py -u name            python zqrya.py -e email
python zqrya.py -p phone           python zqrya.py -d domain
python zqrya.py -i ip              python zqrya.py -url url
python zqrya.py -m name            python zqrya.py --darkweb target
python zqrya.py --full target      python zqrya.py --variants name
python zqrya.py --batch file.txt   python zqrya.py -web --port 7331
python zqrya.py --iplogger --redirect https://site.com

# stalker CLI (per-tool)
python -m stalker.cli nik 3523151001740001
python -m stalker.cli nkk 3510080101010001
python -m stalker.cli ewallet 08123456789
python -m stalker.cli online username
python -m stalker.cli hlr 08123456789
python -m stalker.cli revemail user@gmail.com
python -m stalker.cli gaming username
python -m stalker.cli social username
python -m stalker.cli device 8.8.8.8
python -m stalker.cli geolocate photo.jpg
python -m stalker.cli qr qr.png
python -m stalker.cli leak password123
python -m stalker.cli reverseip 8.8.8.8
python -m stalker.cli monitor username --interval 30
```

---

## 🛠️ OSINT Tools

### 🇮🇩 Indonesian Identity

| Tool | Menu | Command | What You Get |
|------|:----:|---------|--------------|
| **NIK / KTP** | 12 | `nik <16-digit>` | Parse + validate: gender, birth date, province/city, serial, active status |
| **NKK / Kartu Keluarga** | 13 | `nkk <16-digit>` | Parse + validate, **family members list** (NIK, marital status, occupation) from local SIAK DB |

> NIK/NKK names & family data come from a **local SIAK/NPWP database** you provide in `databaselocal/`
> (CSV with a `NIK` column). Without it, Zqrya still parses/validates the number structure.
> Generate a sample DB with `python sources/generate_sample_db.py` (fictional data).

### 🔎 Everyday Tools

| Tool | Menu | Command | What You Get |
|------|:----:|---------|--------------|
| **QR/Barcode decoder** | 14 | `qr <file-or-url>` | Decode QR/barcode, classify payload (URL/WiFi/vCard), expand short links |
| **E-wallet OSINT** | 15 | `ewallet <phone>` | GoPay / OVO / DANA / ShopeePay / LinkAja / Sakuku + verify guide |
| **Status online** | 16 | `online <target>` | Telegram presence + name; WhatsApp link (privacy-limited) |
| **Phone HLR** | 17 | `hlr <phone>` | Carrier, line type, country, live status (best-effort) |
| **Reverse email** | 18 | `revemail <email>` | Reputation, suspicious flag, found name/phone, manual links |
| **Gaming OSINT** | 19 | `gaming <username>` | Steam + Roblox + Minecraft (keyless) |
| **IG/TikTok deep** | 20 | `social <username>` | Followers, bio, verified (best-effort) |
| **Exposed device** | 21 | `device <ip>` | Shodan InternetDB: ports, services, CVEs |
| **Visual geolocation** | 22 | `geolocate <file-or-url>` | EXIF GPS + reverse-image search (Yandex/Lens/TinEye/Bing) |

---

## 🎯 IP Logger — Tracking Links

Generate a link that captures a target's **IP + device + location** the moment they click:

```bash
# Interactive (menu 23): pick a decoy — redirect / custom page / pixel / live tracking
python zqrya.py --iplogger --redirect https://example.com
python zqrya.py --iplogger --page "<h1>Loading...</h1>"
python zqrya.py --iplogger --pixel           # 1x1 email-tracking pixel
```

- **Public tunnel** via localhost.run/serveo (keyless) → shareable link
- **Short link** via is.gd / tinyurl / clck.ru (fallback chain)
- **Live hits** — IP, device (OS/browser), language, referer, geo + map link
- **Live tracking mode** — page pings every 15s, alerts when target moves networks or closes the page
- Logs saved to `output/iplogger/`

> ⚠️ **Ethical use only** — only track people who consented or assets you own.

---

## 🌐 Web UI — Professional Dashboard

```bash
python zqrya.py -web
# Open http://localhost:7331
```

| Feature | Description |
|---------|-------------|
| **All 27 tools** | Full tool set in the browser, not just core scans |
| **Dark/Light theme** | Toggle, preference saved |
| **IP Logger panel** | Start/stop logger + live hit feed with map |
| **Server-side history** | Persists to disk, click to re-run |
| **Batch scan** | Paste multiple targets |
| **Monitor terus** | Polling loop mode without the CLI |
| **Live detection** | Entity-type detection as you type |
| **Export** | JSON / Markdown / print-to-PDF |
| **Responsive** | Works on phone/tablet |

---

## 🛰️ Full Intelligence Pipeline

`--full` (any target), `--deep` (username/email/phone) and the shell's deep mode run **both engines**:
Zqrya modules **and** the deep pipeline — merged into one report.

| Capability | Source | What You Get |
|------------|--------|--------------|
| 🧠 **Maigret Engine** | vendored `maigret/` | 600+ platforms, real names, avatars, bios |
| 🌑 **Dark Web Checker** | `dark_web_checker.py` | GhostProject, Psbdmp, BreachDirectory, LeakCheck, IntelX |
| 🦠 **Hudson Rock** | `breach_check.py` | Infostealer infection intelligence (free) |
| 📧 **Email Scanner** | `email_scanner.py` | Registration on 30+ platforms |
| 📱 **Phone Scanner** | `phone_scanner.py` | Truecaller + 6 platforms + carrier/geo |
| 🛰️ **Shodan InternetDB** | `ip_tracker.py` | Open ports, CVEs, tags (keyless) |
| 🧬 **Username Variants** | `username_variants.py` | 150+ permutations |
| 🔄 **Recursive Search** | `recursive_search.py` | Re-runs on discovered usernames |
| 🎭 **Face Search** | `face_search.py` | 5 reverse-image engines on avatars |
| 🕸️ **Social Graph** | `social_graph.py` | Interactive visualization (pyvis) |

---

## ⚙️ Configuration

Copy `.env.example` to `.env` to enable optional integrations:

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Send reports to Telegram |
| `EXIFTOOLS_API_KEY` | EXIF metadata extraction |
| `NUMVERIFY_API_KEY` | Phone verification API |
| `VERIPHONE_API_KEY` | City-level phone location (best for ID) |
| `MAIGRET_MAX_SITES` | Max sites for Maigret |
| `STEALTH_MODE` | Random delays + header rotation |
| `LOCALDB_DIR` | Folder with SIAK/NPWP CSVs (NIK/NKK names) |
| `ZQRYA_ALLOW_NO_GEOIP=1` | Dev-only: skip the GeoIP requirement |

---

## 📄 Reports & Batch Processing

### Report formats

| Format | Command | Best For |
|--------|---------|----------|
| JSON | `--format json` | Machine parsing / integration |
| HTML | `--format html` | Interactive visual report |
| TXT | `--format txt` | Lightweight, readable anywhere |
| Markdown | `--format md` | Docs / READMEs |

```bash
python zqrya.py -u name --format html -o report.html
python zqrya.py -d example.com --format all -o domain_report
python zqrya.py -e user@gmail.com --format json --compress
```

### Batch scan

```bash
cat > targets.txt << EOF
username
user@gmail.com
08123456789
example.com
8.8.8.8
EOF

python zqrya.py --batch targets.txt --deep --format all
# Options: --batch-delay 2 · --output-dir ./reports · --quiet
```

---

## 🛡️ Legal Disclaimer

**Designed for:** education, security research, and testing systems you own or have permission to test.

**Prohibited use (STRICTLY FORBIDDEN):**
- Doxing or exposing personal data without consent
- Stalking, harassment, or intimidation
- Illegal or criminal activities
- Accessing systems or data without authorization

> **By using Zqrya, you take full responsibility for how you use this tool. The author is not responsible for any misuse.**

---

## 🤝 Contributing

```bash
1. Fork the repository
2. Create a branch: git checkout -b feature/amazing-feature
3. Commit: git commit -m 'Add amazing feature'
4. Push: git push origin feature/amazing-feature
5. Open a Pull Request
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

---

## 📜 License

MIT License — Feel free to use, modify, and distribute with credit.

---

<div align="center">

### 🕵️ **Zqrya v3.0**

*OSINT Intelligence Suite • 100% Public Data • For Cybersecurity Education*

**© 2026 Zqrya.** Built with ❤️ in Indonesia 🇮🇩

**If Zqrya helps you, give it a ⭐ on GitHub!**

</div>
