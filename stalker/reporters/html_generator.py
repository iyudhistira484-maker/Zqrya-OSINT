"""Professional HTML Report Generator for Stalker - Intelligence Gathering System.

Generates modern, elegant HTML reports with dark theme + cyan/blue accents.
Design is custom and professional-looking, optimized for Telegram sharing.
Includes real name identification with photos and age detection.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from datetime import datetime
from jinja2 import Template

# Icon: Simple elegant Stalker logo in SVG
STALKER_ICON = """
<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="20" cy="20" r="18" stroke="#00d4ff" stroke-width="2" fill="none"/>
  <circle cx="20" cy="20" r="14" stroke="#00d4ff" stroke-width="1" fill="none" opacity="0.5"/>
  <circle cx="20" cy="20" r="3" fill="#00d4ff"/>
  <path d="M20 5 L26 15 L20 18 L14 15 Z" fill="#00d4ff" opacity="0.8"/>
  <text x="20" y="32" font-family="Arial, sans-serif" font-size="6" font-weight="bold" fill="#00d4ff" text-anchor="middle">STALKER</text>
</svg>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stalker Intelligence Report - {{ target }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary: #00d4ff;
            --primary-dark: #0099cc;
            --bg-main: #0a0e27;
            --bg-card: #1a1f3a;
            --bg-input: #151b2e;
            --text-primary: #e8eef7;
            --text-secondary: #a0a8c0;
            --text-success: #10b981;
            --text-warning: #f59e0b;
            --text-danger: #ef4444;
            --border: #2d3748;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
            background: var(--bg-main);
            color: var(--text-primary);
            line-height: 1.6;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        /* HEADER */
        header {
            background: linear-gradient(135deg, rgba(0,212,255,0.1) 0%, rgba(0,212,255,0.05) 100%);
            border: 1px solid var(--primary);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .header-icon {
            width: 60px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .header-content h1 {
            font-size: 28px;
            margin-bottom: 8px;
            color: var(--primary);
        }

        .header-content p {
            color: var(--text-secondary);
            font-size: 14px;
        }

        .timestamp {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 8px;
        }

        /* SUMMARY GRID */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .summary-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            transition: all 0.3s ease;
        }

        .summary-card:hover {
            border-color: var(--primary);
            box-shadow: 0 0 15px rgba(0,212,255,0.1);
            transform: translateY(-2px);
        }

        .summary-card-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }

        .summary-card-value {
            font-size: 24px;
            font-weight: bold;
            color: var(--primary);
        }

        .summary-card-meta {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 12px;
        }

        /* SECTION */
        .section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 25px;
        }

        .section-title {
            font-size: 18px;
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 2px solid rgba(0,212,255,0.2);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .section-title::before {
            content: '';
            display: inline-block;
            width: 4px;
            height: 20px;
            background: var(--primary);
            border-radius: 2px;
        }

        /* FINDINGS */
        .findings-list {
            list-style: none;
        }

        .finding-item {
            background: var(--bg-input);
            border-left: 3px solid var(--primary);
            padding: 15px;
            margin-bottom: 12px;
            border-radius: 4px;
            transition: all 0.2s ease;
        }

        .finding-item:hover {
            box-shadow: 0 4px 12px rgba(0,212,255,0.1);
        }

        .finding-platform {
            font-weight: 600;
            color: var(--primary);
            font-size: 14px;
        }

        .finding-url {
            font-size: 12px;
            color: var(--text-secondary);
            word-break: break-all;
            margin-top: 6px;
            font-family: 'Courier New', monospace;
        }

        .finding-meta {
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 8px;
        }

        /* BADGE */
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            margin-right: 8px;
            margin-bottom: 8px;
        }

        .badge-found {
            background: rgba(16,185,129,0.2);
            color: var(--text-success);
            border: 1px solid rgba(16,185,129,0.3);
        }

        .badge-warning {
            background: rgba(245,158,11,0.2);
            color: var(--text-warning);
            border: 1px solid rgba(245,158,11,0.3);
        }

        .badge-danger {
            background: rgba(239,68,68,0.2);
            color: var(--text-danger);
            border: 1px solid rgba(239,68,68,0.3);
        }

        /* STAT TABLE */
        .stat-table {
            width: 100%;
            border-collapse: collapse;
        }

        .stat-table tr {
            border-bottom: 1px solid var(--border);
        }

        .stat-table tr:last-child {
            border-bottom: none;
        }

        .stat-table td {
            padding: 12px;
            font-size: 14px;
        }

        .stat-table td:first-child {
            color: var(--text-secondary);
            font-weight: 500;
        }

        .stat-table td:last-child {
            color: var(--primary);
            font-weight: 600;
            text-align: right;
        }

        /* AVATAR GRID WITH NAME */
        .avatar-gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }

        .avatar-card {
            background: var(--bg-input);
            border: 2px solid var(--border);
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            transition: all 0.2s ease;
        }

        .avatar-card:hover {
            border-color: var(--primary);
            box-shadow: 0 0 12px rgba(0,212,255,0.2);
            transform: translateY(-2px);
        }

        .avatar-image {
            width: 100%;
            height: 100px;
            object-fit: cover;
            border-radius: 6px;
            margin-bottom: 8px;
        }

        .avatar-name {
            font-size: 12px;
            color: var(--text-primary);
            font-weight: 600;
            margin-bottom: 4px;
            word-break: break-word;
        }

        .avatar-meta {
            font-size: 10px;
            color: var(--text-secondary);
        }

        /* EMPTY STATE */
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-secondary);
        }

        .empty-state svg {
            width: 60px;
            height: 60px;
            margin-bottom: 20px;
            opacity: 0.5;
        }

        /* FOOTER */
        footer {
            text-align: center;
            padding: 20px;
            border-top: 1px solid var(--border);
            margin-top: 40px;
            color: var(--text-secondary);
            font-size: 12px;
        }

        .footer-logo {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-bottom: 10px;
        }

        /* RESPONSIVE */
        @media (max-width: 768px) {
            .container {
                padding: 12px;
            }

            header {
                flex-direction: column;
                text-align: center;
            }

            .summary-grid {
                grid-template-columns: 1fr;
            }

            .section {
                padding: 15px;
            }

            .avatar-gallery {
                grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
            }
        }

        /* PRINT STYLE */
        @media print {
            body {
                background: white;
                color: black;
            }

            .summary-card {
                page-break-inside: avoid;
            }

            .section {
                page-break-inside: avoid;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER -->
        <header>
            <div class="header-icon">
                {{ stalker_icon | safe }}
            </div>
            <div class="header-content">
                <h1>Stalker Intelligence Report</h1>
                <p>Target: <code>{{ target }}</code></p>
                {% if identified_names %}
                <p style="color: var(--text-success);">📋 Identified As: <strong>{{ identified_names | join(', ') }}</strong></p>
                {% endif %}
                <p class="timestamp">Generated: {{ timestamp }}</p>
            </div>
        </header>

        <!-- SUMMARY CARDS -->
        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-card-label">Profiles Found</div>
                <div class="summary-card-value">{{ profiles_found }}</div>
                <div class="summary-card-meta">of {{ sites_checked }} sites checked</div>
            </div>

            <div class="summary-card">
                <div class="summary-card-label">Platforms</div>
                <div class="summary-card-value">{{ platforms | length }}</div>
                <div class="summary-card-meta">active accounts identified</div>
            </div>

            {% if breach_count > 0 %}
            <div class="summary-card">
                <div class="summary-card-label">⚠ Breaches Detected</div>
                <div class="summary-card-value" style="color: var(--text-danger);">{{ breach_count }}</div>
                <div class="summary-card-meta">security issues found</div>
            </div>
            {% endif %}

            <div class="summary-card">
                <div class="summary-card-label">Duration</div>
                <div class="summary-card-value">{{ duration }}</div>
                <div class="summary-card-meta">investigation time</div>
            </div>
        </div>

        <!-- FOUND PROFILES -->
        {% if found_sites %}
        <div class="section">
            <h2 class="section-title">Found Profiles</h2>
            {% if found_sites %}
                <ul class="findings-list">
                {% for site in found_sites %}
                    <li class="finding-item">
                        <div class="finding-platform">{{ site.name | default('Unknown Platform') }}</div>
                        {% if site.url %}
                        <div class="finding-url">🔗 <a href="{{ site.url }}" target="_blank" style="color: var(--primary); text-decoration: none;">{{ site.url }}</a></div>
                        {% endif %}
                        {% if site.username %}
                        <div class="finding-meta">Username: <code>{{ site.username }}</code></div>
                        {% endif %}
                    </li>
                {% endfor %}
                </ul>
            {% else %}
                <div class="empty-state">
                    <p>No profiles found on this platform</p>
                </div>
            {% endif %}
        </div>
        {% endif %}

        <!-- AVATARS WITH NAMES -->
        {% if avatars_with_names %}
        <div class="section">
            <h2 class="section-title">Profile Pictures & Identification</h2>
            <div class="avatar-gallery">
            {% for avatar_data in avatars_with_names %}
                <div class="avatar-card">
                    <img src="{{ avatar_data.url }}" alt="Avatar" class="avatar-image" onerror="this.style.display='none'">
                    <div class="avatar-name">{{ avatar_data.name | default('Unknown') }}</div>
                    {% if avatar_data.platform %}
                    <div class="avatar-meta">{{ avatar_data.platform }}</div>
                    {% endif %}
                    {% if avatar_data.age %}
                    <div class="avatar-meta">Age: {{ avatar_data.age }}</div>
                    {% endif %}
                </div>
            {% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- REAL NAMES -->
        {% if identified_names %}
        <div class="section">
            <h2 class="section-title">Identified Names</h2>
            {% for name in identified_names %}
                <span class="badge badge-found">{{ name }}</span>
            {% endfor %}
        </div>
        {% endif %}

        <!-- BREACH INFO -->
        {% if breach_info %}
        <div class="section">
            <h2 class="section-title">⚠ Breach Information</h2>
            <table class="stat-table">
                <tr>
                    <td>Total Infections</td>
                    <td>{{ breach_info.total_infections | default(0) }}</td>
                </tr>
                <tr>
                    <td>Compromise Date</td>
                    <td>{{ breach_info.compromise_date | default('N/A') }}</td>
                </tr>
                <tr>
                    <td>Status</td>
                    <td><span class="badge badge-warning">{{ breach_info.status | default('Unknown') }}</span></td>
                </tr>
            </table>
        </div>
        {% endif %}

        <!-- TEXT ENTITIES -->
        {% if text_entities %}
        <div class="section">
            <h2 class="section-title">Extracted Information</h2>
            {% if text_entities.emails %}
                <div style="margin-bottom: 15px;">
                    <strong style="color: var(--primary);">Emails:</strong><br>
                    {% for email in text_entities.emails %}
                        <code style="background: var(--bg-input); padding: 4px 8px; border-radius: 4px; margin: 4px;">{{ email }}</code>
                    {% endfor %}
                </div>
            {% endif %}
            {% if text_entities.phones %}
                <div style="margin-bottom: 15px;">
                    <strong style="color: var(--primary);">Phones:</strong><br>
                    {% for phone in text_entities.phones %}
                        <code style="background: var(--bg-input); padding: 4px 8px; border-radius: 4px; margin: 4px;">{{ phone }}</code>
                    {% endfor %}
                </div>
            {% endif %}
        </div>
        {% endif %}

        <!-- IP INFORMATION -->
        {% if ip_info %}
        <div class="section">
            <h2 class="section-title">🌍 IP Location Information</h2>
            <table class="stat-table">
                {% if ip_info.ip %}
                <tr>
                    <td>IP Address</td>
                    <td><code>{{ ip_info.ip }}</code></td>
                </tr>
                {% endif %}
                {% if ip_info.country %}
                <tr>
                    <td>Country</td>
                    <td>{{ ip_info.country }} ({{ ip_info.country_code | default('?') }})</td>
                </tr>
                {% endif %}
                {% if ip_info.city %}
                <tr>
                    <td>City</td>
                    <td>{{ ip_info.city }}, {{ ip_info.region | default('') }}</td>
                </tr>
                {% endif %}
                {% if ip_info.isp %}
                <tr>
                    <td>ISP</td>
                    <td>{{ ip_info.isp }}</td>
                </tr>
                {% endif %}
                {% if ip_info.asn %}
                <tr>
                    <td>ASN</td>
                    <td>{{ ip_info.asn }}</td>
                </tr>
                {% endif %}
                {% if ip_info.is_proxy %}
                <tr>
                    <td>⚠ Proxy/VPN</td>
                    <td style="color: var(--text-warning);">Detected</td>
                </tr>
                {% endif %}
            </table>
        </div>
        {% endif %}

        <!-- FOOTER -->
        <footer>
            <div class="footer-logo">
                <strong>Stalker</strong> Intelligence Gathering System v2.0
            </div>
            <p>Professional OSINT Investigation Report</p>
            <p style="margin-top: 10px; font-size: 11px; opacity: 0.7;">For lawful purposes only. Comply with all applicable laws.</p>
        </footer>
    </div>
</body>
</html>
"""


def _safe_get_value(obj: Any, key: str, default: Any = None) -> Any:
    """Safely get value from dict or list, handling both types."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    elif isinstance(obj, (list, tuple)) and isinstance(key, int):
        try:
            return obj[key]
        except (IndexError, TypeError):
            return default
    return default


def generate_html_report(result: Dict[str, Any], output_path: Optional[Path] = None) -> str:
    """Generate professional HTML report from investigation result.
    
    Fixes:
    - Handle both dict and list types safely
    - Display real names extracted from profiles
    - Show avatars with associated names
    - Include IP location information
    """
    
    # Extract summary data
    summary = result.get("summary", {})
    maigret_data = result.get("maigret", {})
    breach_data = result.get("breach", {})
    text_profile = result.get("text_profile", {})
    ip_info = result.get("ip_info", {})
    
    # Prepare template variables
    found_sites = []
    if isinstance(maigret_data, dict):
        for site in maigret_data.get("found_sites", []):
            if isinstance(site, dict):
                found_sites.append({
                    "name": site.get("name", "Unknown"),
                    "url": site.get("url"),
                    "username": site.get("username"),
                })
    
    # Get avatars with names - handle both list and dict formats
    avatars_with_names = []
    if isinstance(maigret_data, dict):
        profiles = maigret_data.get("found_sites", [])
        if isinstance(profiles, list):
            for profile in profiles:
                if isinstance(profile, dict) and profile.get("avatar"):
                    avatars_with_names.append({
                        "url": profile.get("avatar"),
                        "name": profile.get("username", "Unknown"),
                        "platform": profile.get("name", ""),
                    })
    
    # Get real names identified
    identified_names = []
    if isinstance(summary, dict):
        real_names = summary.get("real_names_found", [])
        if isinstance(real_names, list):
            identified_names = real_names
    
    # Breach info
    breach_info = None
    if isinstance(breach_data, dict):
        breach_email = breach_data.get("email", {})
        if isinstance(breach_email, dict) and breach_email.get("total_infections", 0) > 0:
            breach_info = {
                "total_infections": breach_email.get("total_infections", 0),
                "compromise_date": breach_email.get("compromise_date"),
                "status": breach_email.get("status", "compromised"),
            }
    
    # Text entities
    text_entities = {}
    if isinstance(text_profile, dict):
        text_entities = {
            "emails": text_profile.get("emails", []) if isinstance(text_profile.get("emails"), list) else [],
            "phones": text_profile.get("phones", []) if isinstance(text_profile.get("phones"), list) else [],
        }
    
    # IP info
    ip_info_dict = {}
    if isinstance(ip_info, dict):
        ip_info_dict = {
            "ip": ip_info.get("ip"),
            "country": ip_info.get("country"),
            "country_code": ip_info.get("country_code"),
            "city": ip_info.get("city"),
            "region": ip_info.get("region"),
            "isp": ip_info.get("isp"),
            "asn": ip_info.get("asn"),
            "is_proxy": ip_info.get("is_proxy"),
        }
    
    # Get platforms as list
    platforms = []
    if isinstance(summary, dict):
        plat = summary.get("platforms", [])
        if isinstance(plat, list):
            platforms = plat
    
    # Prepare context
    context = {
        "stalker_icon": STALKER_ICON,
        "target": result.get("username", "Unknown"),
        "identified_names": identified_names,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "profiles_found": summary.get("profiles_found", 0) if isinstance(summary, dict) else 0,
        "sites_checked": summary.get("sites_checked", 0) if isinstance(summary, dict) else 0,
        "platforms": platforms,
        "breach_count": summary.get("breach_hudson_rock", 0) if isinstance(summary, dict) else 0,
        "duration": summary.get("duration", "0s") if isinstance(summary, dict) else "0s",
        "found_sites": found_sites,
        "avatars_with_names": avatars_with_names,
        "identified_names": identified_names,
        "breach_info": breach_info,
        "text_entities": text_entities if (text_entities.get("emails") or text_entities.get("phones")) else None,
        "ip_info": ip_info_dict if ip_info_dict.get("ip") else None,
    }
    
    # Render template
    template = Template(HTML_TEMPLATE)
    html_content = template.render(context)
    
    # Save if output_path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
    
    return html_content
