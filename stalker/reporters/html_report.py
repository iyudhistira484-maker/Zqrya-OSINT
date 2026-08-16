"""HTML report generator — clean, professional Stalker investigation report."""

import json
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from jinja2 import Environment, FileSystemLoader
    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zqrya OSINT Report — {{ result.username }}</title>
    <style>
        :root {
            --bg: #0d1117; --card: #161b22; --border: #30363d;
            --text: #c9d1d9; --muted: #8b949e; --accent: #58a6ff;
            --orange: #f0883e; --purple: #d2a8ff; --green: #3fb950;
            --red: #f85149; --pink: #e1306c;
        }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif; background: var(--bg); color: var(--text); line-height:1.6; }
        .container { max-width:960px; margin:0 auto; padding:2rem 1.5rem; }

        /* Hero */
        .hero { text-align:center; padding:2rem 0 2.5rem; border-bottom:1px solid var(--border); margin-bottom:2rem; }
        .hero h1 { font-size:2.4rem; color:var(--accent); font-weight:800; }
        .hero .username { font-size:1.1rem; color:var(--orange); margin:.3rem 0; }
        .hero .meta-row { display:flex; justify-content:center; gap:2rem; flex-wrap:wrap; margin:1rem 0; color:var(--muted); font-size:.9rem; }
        .hero .meta-row span { display:inline-flex; align-items:center; gap:.3rem; }
        .stat-badge { background:var(--card); border:1px solid var(--border); border-radius:6px; padding:.4rem 1rem; font-weight:600; color:var(--accent); }

        /* Section headers */
        h2 { font-size:1.5rem; color:var(--orange); border-bottom:1px solid var(--border); padding-bottom:.5rem; margin:2.5rem 0 1.2rem; }
        h3 { font-size:1.1rem; color:var(--purple); margin:1rem 0 .5rem; }

        /* Profile grid */
        .profile-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap:.8rem; }
        .profile-card { background:var(--card); border:1px solid var(--border); border-radius:10px; overflow:hidden; transition:border-color .2s; }
        .profile-card:hover { border-color:var(--accent); }
        .profile-card .card-header { display:flex; align-items:center; gap:.8rem; padding:1rem 1rem .6rem; }
        .profile-card .card-header img { width:52px; height:52px; border-radius:50%; object-fit:cover; border:2px solid var(--border); background:var(--bg); }
        .profile-card .card-header img.placeholder { filter:opacity(0.3); }
        .profile-card .card-header .info { flex:1; min-width:0; }
        .profile-card .card-header .info strong { display:block; color:var(--accent); font-size:.95rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .profile-card .card-header .info .url { font-size:.75rem; color:var(--muted); }
        .profile-card .card-header .info .url a { color:var(--accent); text-decoration:none; }
        .profile-card .card-header .info .url a:hover { text-decoration:underline; }
        .profile-card .card-body { padding:.3rem 1rem 1rem; font-size:.85rem; }
        .profile-card .card-body .kv { display:flex; gap:.3rem; padding:.15rem 0; }
        .profile-card .card-body .kv .k { color:var(--muted); min-width:70px; flex-shrink:0; }
        .profile-card .card-body .kv .v { color:var(--text); word-break:break-word; }

        /* Tag pills */
        .tag { display:inline-block; background:#1f6feb22; color:var(--accent); border:1px solid #1f6feb44; border-radius:4px; padding:1px 7px; font-size:.75rem; margin:1px; }
        .tag.name { background:#6f42c122; color:var(--purple); border-color:#6f42c144; }

        /* Dork results */
        .dork-block { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:1rem; margin-bottom:.8rem; }
        .dork-block summary { cursor:pointer; font-weight:600; color:var(--purple); font-size:1rem; user-select:none; }
        .dork-block ul { margin:.6rem 0 0 1.2rem; }
        .dork-block li { margin:.3rem 0; font-size:.85rem; }
        .dork-block li a { color:var(--accent); text-decoration:none; }
        .dork-block li a:hover { text-decoration:underline; }
        .dork-block .snip { color:var(--muted); font-size:.8rem; display:block; }

        /* Reverse image */
        .reverse-card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:1rem; margin-bottom:.8rem; }
        .reverse-card img { max-width:80px; max-height:80px; border-radius:8px; border:2px solid var(--border); margin:.5rem 0; }

        /* Recursive */
        .rec-item { background:var(--card); border:1px solid var(--border); border-radius:6px; padding:.7rem 1rem; margin:.4rem 0; }

        /* Graph iframe */
        .graph-frame { width:100%; height:620px; border:1px solid var(--border); border-radius:10px; margin:1rem 0; overflow:hidden; }

        /* Custom API table */
        .api-table { width:100%; border-collapse:collapse; margin:1rem 0; }
        .api-table th, .api-table td { text-align:left; padding:8px 14px; border-bottom:1px solid var(--border); font-size:.9rem; }
        .api-table th { color:var(--muted); font-weight:600; text-transform:uppercase; font-size:.75rem; letter-spacing:.05em; }
        .api-table td.avatar-cell { width:52px; }
        .api-table td.avatar-cell img { width:40px; height:40px; border-radius:50%; object-fit:cover; }

        /* Footer */
        .footer { text-align:center; color:var(--muted); font-size:.8rem; margin-top:3rem; padding-top:2rem; border-top:1px solid var(--border); }

        @media (max-width:600px) {
            .container { padding:1rem; }
            .hero h1 { font-size:1.6rem; }
            .profile-grid { grid-template-columns:1fr; }
            .hero .meta-row { gap:1rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- ========== HERO ========== -->
        <div class="hero">
            <h1>Zqrya OSINT Report</h1>
            <div class="username">@{{ result.username }}</div>
            <div class="meta-row">
                <span class="stat-badge">{{ result.summary.profiles_found }} profiles</span>
                <span class="stat-badge">{{ result.summary.sites_checked }} sites</span>
                <span class="stat-badge">{{ result.summary.duration }}</span>
            </div>
            <div class="meta-row">
                <span>Generated: {{ result.timestamp[:19] }}</span>
            </div>
        </div>

        <!-- ========== SUMMARY ========== -->
        <h2>Summary</h2>
        {% if result.summary.real_names_found %}
        <div class="dork-block">
            <div><strong>Real Names:</strong>
            {% for n in result.summary.real_names_found %}<span class="tag name">{{ n }}</span>{% endfor %}
            </div>
        </div>
        {% endif %}
        {% if result.summary.platforms %}
        <div class="dork-block">
            <div><strong>Platforms ({{ result.summary.platforms|length }}):</strong>
            {% for p in result.summary.platforms[:20] %}<span class="tag">{{ p }}</span>{% endfor %}
            {% if result.summary.platforms|length > 20 %}<span class="tag">+{{ result.summary.platforms|length - 20 }} more</span>{% endif %}
            </div>
        </div>
        {% endif %}
        {% if result.summary.custom_api_platforms %}
        <div class="dork-block">
            <div><strong>Custom API Platforms:</strong>
            {% for p in result.summary.custom_api_platforms %}<span class="tag name">{{ p }}</span>{% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- ========== SOCIAL GRAPH ========== -->
        {% if result.social_graph %}
        <h2>Social Graph</h2>
        <iframe class="graph-frame" src="{{ result.social_graph }}" title="Social Graph"></iframe>
        {% endif %}

        <!-- ========== PROFILES ========== -->
        <h2>Profiles Found ({{ result.maigret.found_sites|length }})</h2>
        {% if result.maigret.found_sites %}
        <div class="profile-grid">
        {% for site in result.maigret.found_sites %}
        <div class="profile-card">
            <div class="card-header">
                {% if site.local_avatar %}
                <img src="{{ site.local_avatar }}" alt="avatar" onerror="this.classList.add('placeholder');this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 52 52%22><rect fill=%22%2330363d%22 width=%2252%22 height=%2252%22 rx=%2226%22/><text fill=%22%238b949e%22 x=%2226%22 y=%2235%22 text-anchor=%22middle%22 font-size=%2224%22>?</text></svg>'">
                {% elif site.avatar_url %}
                <img src="{{ site.avatar_url }}" alt="avatar" onerror="this.classList.add('placeholder');this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 52 52%22><rect fill=%22%2330363d%22 width=%2252%22 height=%2252%22 rx=%2226%22/><text fill=%22%238b949e%22 x=%2226%22 y=%2235%22 text-anchor=%22middle%22 font-size=%2224%22>?</text></svg>'">
                {% else %}
                <img class="placeholder" src="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 52 52%22><rect fill=%22%2330363d%22 width=%2252%22 height=%2252%22 rx=%2226%22/><text fill=%22%238b949e%22 x=%2226%22 y=%2235%22 text-anchor=%22middle%22 font-size=%2224%22>?</text></svg>" alt="no avatar">
                {% endif %}
                <div class="info">
                    <strong>{{ site.site_name }}</strong>
                    <div class="url">
                        {% if site.url_user %}
                        <a href="{{ site.url_user }}" target="_blank" rel="noopener">{{ site.url_user[:55] }}{% if site.url_user|length > 55 %}...{% endif %}</a>
                        {% endif %}
                    </div>
                </div>
            </div>
            <div class="card-body">
                {% if site.real_name %}
                <div class="kv"><span class="k">Name</span><span class="v">{{ site.real_name }}</span></div>
                {% endif %}
                {% if site.bio %}
                <div class="kv"><span class="k">Bio</span><span class="v">{{ site.bio[:180] }}{% if site.bio|length > 180 %}...{% endif %}</span></div>
                {% endif %}
                {% if site.location %}
                <div class="kv"><span class="k">Location</span><span class="v">{{ site.location }}</span></div>
                {% endif %}
                {% if site.other_usernames %}
                <div class="kv"><span class="k">Usernames</span><span class="v">{% for k, v in site.other_usernames.items() %}<span class="tag">{{ k }}: {{ v }}</span>{% endfor %}</span></div>
                {% endif %}
                {% if site.other_links %}
                <div class="kv"><span class="k">Links</span><span class="v">{% for l in site.other_links[:3] %}<a href="{{ l }}" target="_blank" class="tag">{{ l[:30] }}</a>{% endfor %}</span></div>
                {% endif %}
            </div>
        </div>
        {% endfor %}
        </div>
        {% else %}
        <p style="color:var(--muted)">No profiles found.</p>
        {% endif %}

        <!-- ========== CUSTOM API RESULTS ========== -->
        {% if result.custom_apis %}
        <h2>Custom API Results</h2>
        <table class="api-table">
            <thead><tr><th></th><th>Platform</th><th>Name</th><th>Status</th><th>Details</th></tr></thead>
            <tbody>
            {% for platform, data in result.custom_apis.items() %}
            <tr>
                <td class="avatar-cell">
                    {% if data.local_avatar %}<img src="{{ data.local_avatar }}" alt="avatar" onerror="this.style.display='none'">
                    {% elif data.avatar_url %}<img src="{{ data.avatar_url }}" alt="avatar" onerror="this.style.display='none'">{% endif %}
                </td>
                <td><strong>{{ platform }}</strong></td>
                <td>{{ data.real_name or '-' }}</td>
                <td>{% if data.success %}<span style="color:var(--green)">OK</span>{% else %}<span style="color:var(--red)">Fail</span>{% endif %}</td>
                <td style="font-size:.8rem;color:var(--muted)">
                    {% if data.bio %}Bio: {{ data.bio[:60] }}<br>{% endif %}
                    {% if data.followers is not none %}Followers: {{ data.followers }}<br>{% endif %}
                    {% if data.location %}Location: {{ data.location }}{% endif %}
                    {% if not data.success %}{{ data.error }}{% endif %}
                </td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
        {% endif %}

        <!-- ========== EMAIL SCAN ========== -->
        {% if result.email_scan %}
        <h2>Email Scanner Results</h2>
        <table class="api-table">
            <thead><tr><th>Platform</th><th>Status</th><th>Details</th></tr></thead>
            <tbody>
            {% for r in result.email_scan %}
            <tr>
                <td><strong>{{ r.platform }}</strong></td>
                <td>{% if r.registered %}<span style="color:var(--green)">Registered</span>{% elif r.error %}<span style="color:var(--red)">Error</span>{% else %}<span style="color:var(--muted)">Not Found</span>{% endif %}</td>
                <td style="font-size:.8rem;color:var(--muted)">{% if r.error %}{{ r.error }}{% endif %}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
        {% endif %}

        <!-- ========== PHONE SCAN ========== -->
        {% if result.phone_scan %}
        <h2>Phone Scanner Results</h2>
        {% set phone_info = {'carrier': '', 'region': '', 'country': '', 'line_type': ''} %}
        {% for r in result.phone_scan %}
        {% if r.carrier %}{% set _ = phone_info.update({'carrier': r.carrier, 'region': r.region or '', 'country': r.country or '', 'line_type': r.line_type or ''}) %}{% endif %}
        {% endfor %}
        {% if phone_info.carrier %}
        <div class="dork-block">
            <strong>Carrier:</strong> <span class="badge" style="background:#6f42c1">{{ phone_info.carrier }}</span>
            <strong style="margin-left:1rem">Region:</strong> <span class="badge" style="background:#238636">{{ phone_info.region }}</span>
            <strong style="margin-left:1rem">Line:</strong> <span class="badge">{{ phone_info.line_type }}</span>
            <strong style="margin-left:1rem">Country:</strong> <span class="badge" style="background:#1f6feb44">{{ phone_info.country }}</span>
        </div>
        {% endif %}
        <table class="api-table">
            <thead><tr><th>Platform</th><th>Status</th><th>Carrier</th><th>Region</th></tr></thead>
            <tbody>
            {% for r in result.phone_scan %}
            <tr>
                <td><strong>{{ r.platform }}</strong></td>
                <td>{% if r.registered %}<span style="color:var(--green)">Registered</span>{% elif r.error %}<span style="color:var(--red)">Error</span>{% else %}<span style="color:var(--muted)">Not Found</span>{% endif %}</td>
                <td style="font-size:.85rem">{{ r.carrier or r.provider or '-' }}</td>
                <td style="font-size:.85rem;color:var(--muted)">{{ r.region or '-' }}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
        {% endif %}

        <!-- ========== PASSWORD LEAK ========== -->
        {% if result.password_leak and result.password_leak.leaked_count %}
        <h2>Password Leak Check</h2>
        <div class="dork-block" style="border-color:var(--red)">
            <div style="color:var(--red)"><strong>Warning:</strong> {{ result.password_leak.leaked_count }} password pattern(s) found in known data breaches.</div>
            {% for r in result.password_leak.results %}
            {% if r.found %}
            <div style="margin:4px 0 0 1rem;font-size:.85rem;">
                <span style="color:var(--red)">{{ r.password_hint }}</span> &mdash; seen {{ r.count }} times in breaches
            </div>
            {% endif %}
            {% endfor %}
        </div>
        {% endif %}

        <!-- ========== EXTRACTED ENTITIES ========== -->
        {% if result.breach %}
        <h2>Breach Intelligence</h2>
        {% if result.breach.username and result.breach.username.total_infections %}
        <div class="dork-block">
            <div style="color:var(--red)"><strong>Hudson Rock (Username):</strong> {{ result.breach.username.total_infections }} infostealer infection(s)</div>
            {% for inf in result.breach.username.infections[:5] %}
            <div style="margin:4px 0 0 1rem;font-size:.85rem;color:var(--muted)">
                <span class="tag">{{ inf.stealer_family }}</span>
                {{ inf.date_compromised }} &mdash; {{ inf.os }}
            </div>
            {% endfor %}
        </div>
        {% endif %}
        {% if result.breach.email and result.breach.email.total_infections %}
        <div class="dork-block">
            <div style="color:var(--red)"><strong>Hudson Rock (Email):</strong> {{ result.breach.email.total_infections }} infostealer infection(s)</div>
        </div>
        {% endif %}
        {% endif %}

        <!-- ========== TELEGRAM ========== -->
        {% if result.telegram and result.telegram.success %}
        <h2>Telegram Profile</h2>
        <div class="profile-card" style="max-width:400px">
            <div class="card-header">
                {% if result.telegram.avatar_url %}
                <img src="{{ result.telegram.avatar_url }}" alt="tg avatar" onerror="this.classList.add('placeholder')">
                {% endif %}
                <div class="info">
                    <strong>{{ result.telegram.display_name or result.telegram.username }}</strong>
                    <div class="url">@{{ result.telegram.username }} &middot; {{ result.telegram.type }}</div>
                </div>
            </div>
            <div class="card-body">
                {% if result.telegram.numeric_id %}<div class="kv"><span class="k">Numeric ID</span><span class="v">{{ result.telegram.numeric_id }}</span></div>{% endif %}
                {% if result.telegram.bio %}<div class="kv"><span class="k">Bio</span><span class="v">{{ result.telegram.bio[:200] }}</span></div>{% endif %}
                {% if result.telegram.members_text %}<div class="kv"><span class="k">Members</span><span class="v">{{ result.telegram.members_text }}</span></div>{% endif %}
            </div>
        </div>
        {% endif %}

        <!-- ========== TEXT PROFILE ========== -->
        {% if result.text_profile %}
        <h2>Extracted Entities</h2>
        {% for entity_type, values in result.text_profile.items() %}
        {% if values %}
        <div class="dork-block">
            <strong>{{ entity_type|replace('_', ' ')|title }}:</strong>
            {% for v in values[:10] %}<span class="tag">{{ v }}</span>{% endfor %}
        </div>
        {% endif %}
        {% endfor %}
        {% endif %}

        <!-- ========== LOCAL DATABASE MATCHES ========== -->
        {% if result.localdb %}
        <h2>Local Database Matches</h2>
        {% if result.localdb.by_name %}
        <h3>By Name</h3>
        {% for db, matches in result.localdb.by_name.items() %}
        <div class="dork-block">
            <strong>{{ db.replace('.csv','')|title }} ({{ matches|length }}):</strong>
            {% for m in matches[:10] %}
            <div style="margin:6px 0 0 1rem;font-size:.85rem">
                <span class="tag name">{{ m.name }}</span>
                {% if m.nik %}<span style="color:var(--muted)">NIK: {{ m.nik }}</span>{% endif %}
                {% if m.npwp %}<span style="color:var(--muted)">NPWP: {{ m.npwp }}</span>{% endif %}
                {% if m.phone %}<span style="color:var(--muted)">Telp: {{ m.phone }}</span>{% endif %}
                {% if m.email %}<span style="color:var(--muted)">Email: {{ m.email }}</span>{% endif %}
                {% if m.address %}<br><span style="color:var(--muted);font-size:.8rem">{{ m.address }}</span>{% endif %}
                {% if m.birth %}
                {% set birth = m.birth if m.birth is string else m.birth_place + ', ' + (m.birth_date or '') %}
                <br><span style="color:var(--muted);font-size:.8rem">{{ birth }}</span>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        {% endfor %}
        {% endif %}
        {% if result.localdb.by_email %}
        <h3>By Email</h3>
        {% for db, matches in result.localdb.by_email.items() %}
        <div class="dork-block">
            <strong>{{ db.replace('.csv','')|title }} ({{ matches|length }}):</strong>
            {% for m in matches[:10] %}
            <div style="margin:4px 0 0 1rem;font-size:.85rem">
                <span class="tag name">{{ m.name or m.email }}</span>
                {% if m.phone %}<span style="color:var(--muted)">Telp: {{ m.phone }}</span>{% endif %}
                {% if m.customer_id %}<span style="color:var(--muted)">ID: {{ m.customer_id }}</span>{% endif %}
            </div>
            {% endfor %}
        </div>
        {% endfor %}
        {% endif %}
        {% if result.localdb.by_phone %}
        <h3>By Phone</h3>
        {% for db, matches in result.localdb.by_phone.items() %}
        <div class="dork-block">
            <strong>{{ db.replace('.csv','')|title }} ({{ matches|length }}):</strong>
            {% for m in matches[:10] %}
            <div style="margin:4px 0 0 1rem;font-size:.85rem">
                <span class="tag name">{{ m.name or m.email }}</span>
                {% if m.phone %}<span style="color:var(--muted)">Telp: {{ m.phone }}</span>{% endif %}
            </div>
            {% endfor %}
        </div>
        {% endfor %}
        {% endif %}
        {% endif %}

        <!-- ========== SMART DORK ========== -->
        {% if result.google_dork %}
        <h2>Smart Dork Results</h2>
        {% for query_label, links in result.google_dork.items() %}
        {% if links and links is iterable and links is not string %}
        <details class="dork-block" {% if loop.index <= 3 %}open{% endif %}>
            <summary>{{ query_label }} ({{ links|length }} results)</summary>
            <ul>
                {% for link in links[:8] %}
                <li>
                    <a href="{{ link.url }}" target="_blank" rel="noopener">{{ link.title }}</a>
                    {% if link.snippet %}<span class="snip">{{ link.snippet[:180] }}</span>{% endif %}
                </li>
                {% endfor %}
            </ul>
        </details>
        {% endif %}
        {% endfor %}
        {% endif %}

        <!-- ========== REVERSE IMAGE ========== -->
        {% if result.reverse_image %}
        <h2>Reverse Image Search</h2>
        {% for avatar_url, data in result.reverse_image.items() %}
        <div class="reverse-card">
            <img src="{{ avatar_url }}" alt="searched avatar" onerror="this.style.display='none'">
            {% if data.success %}
            <p style="color:var(--green)">Found {{ data.pages_found|length }} pages, {{ data.similar_images|length }} similar</p>
            {% for page in data.pages_found[:5] %}
            <div class="result-link" style="margin:2px 0"><a href="{{ page.url }}" target="_blank" rel="noopener">{{ page.title }}</a></div>
            {% endfor %}
            {% else %}
            <p style="color:var(--red)">Failed: {{ data.error }}</p>
            {% endif %}
        </div>
        {% endfor %}
        {% endif %}

        <!-- ========== FACE SEARCH ========== -->
        {% if result.face_search %}
        <h2>Face Search (Multi-Engine)</h2>
        {% for avatar_url, engines in result.face_search.items() %}
        <div class="reverse-card">
            <img src="{{ avatar_url }}" alt="avatar" onerror="this.style.display='none'">
            {% for eng_name, eng in engines.items() %}
            {% if eng and eng.success %}
            <p style="color:var(--accent)"><strong>{{ eng_name }}</strong>: {{ eng.pages_found|length }} pages, {{ eng.similar_images|length }} similar</p>
            {% for page in eng.pages_found[:3] %}
            <div style="margin:1px 0 1px 1rem;font-size:.85rem">
                <a href="{{ page.url }}" target="_blank" rel="noopener">{{ page.title }}</a>
            </div>
            {% endfor %}
            {% endif %}
            {% endfor %}
        </div>
        {% endfor %}
        {% endif %}

        <!-- ========== RECURSIVE ========== -->
        {% if result.recursive and result.recursive.discovered_usernames %}
        <h2>Recursive Username Discovery</h2>
        {% for d in result.recursive.discovered_usernames %}
        <div class="rec-item">
            <span class="tag name">@{{ d.username }}</span>
            from <strong>{{ d.source_site }}</strong> ({{ d.source_field }})
            {% set rkey = d.username %}
            {% if result.recursive.recursive_results and rkey in result.recursive.recursive_results %}
            <span style="color:var(--muted)">
                — {{ result.recursive.recursive_results[rkey].found_sites }} profiles:
                {% for s in result.recursive.recursive_results[rkey].sites %}
                <span class="tag">{{ s }}</span>
                {% endfor %}
            </span>
            {% endif %}
        </div>
        {% endfor %}
        {% endif %}

        <!-- ========== EXIF ========== -->
        {% if result.exif %}
        <h2>EXIF Metadata</h2>
        {% for url, meta in result.exif.items() %}
        {% if meta %}
        <div class="dork-block">
            <div><strong>Image:</strong> <span style="font-size:.8rem;color:var(--muted)">{{ url[:80] }}</span></div>
            {% for k, v in meta.items() %}
            <span class="tag">{{ k }}: {{ v }}</span>
            {% endfor %}
        </div>
        {% endif %}
        {% endfor %}
        {% endif %}

        <!-- ========== ZQRYA MODULES ========== -->
        {% if result.zqrya %}
        <h2>Zqrya Module Results</h2>
        {% for name, mod in result.zqrya.items() %}
        {% if not name.startswith('_') %}
        <div class="dork-block">
            <div><strong>{{ name|upper }}</strong>
            {% if mod and mod.get('data') %}<span class="tag" style="color:var(--green)">OK</span>
            {% elif mod and mod.get('error') %}<span class="tag" style="color:var(--red)">Error</span>
            {% else %}<span class="tag" style="color:var(--muted)">None</span>{% endif %}
            </div>
            {% if mod and mod.get('data') %}
            <pre style="font-size:.78rem;color:var(--muted);white-space:pre-wrap;word-break:break-word;background:var(--card);padding:.6rem;border-radius:6px;margin:.3rem 0 0">{{ mod['data']|tojson_safe }}</pre>
            {% elif mod and mod.get('error') %}
            <div style="font-size:.85rem;color:var(--red)">{{ mod['error'] }}</div>
            {% endif %}
        </div>
        {% endif %}
        {% endfor %}
        {% endif %}

        <div class="footer">
            Generated by Zqrya OSINT (Zqrya + Stalker) &mdash; {{ result.timestamp[:19] }}
        </div>
    </div>
</body>
</html>"""


def save(result: Dict[str, Any], output_dir: Path, username: str, timestamp: str) -> Optional[Path]:
    """Save investigation results as HTML report."""
    try:
        filename = f"stalker_{username}_{timestamp}.html"
        filepath = output_dir / filename

        if HAS_JINJA:
            env = Environment()
            env.filters['tojson_safe'] = lambda v: json.dumps(v, indent=2, ensure_ascii=False, default=str)
            template = env.from_string(TEMPLATE)
            html = template.render(result=result)
        else:
            # FIX: Fallback aman untuk menggantikan logika replace() yang berantakan
            html = f"<html><body style='background:#0d1117;color:#c9d1d9;font-family:sans-serif;padding:2rem;text-align:center;'><h1>Stalker Report: {username}</h1><p><b>Error:</b> Modul Jinja2 tidak ditemukan.</p><p>Silakan jalankan <code>pip install jinja2</code> lalu ulangi pencarian untuk melihat laporan HTML yang lengkap.</p></body></html>"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        return filepath
    except Exception:
        return None
