#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zqrya v3.0 - Web Server (Professional Dashboard)
Flask localhost interface — python zqrya.py -web
Features: dark/light theme, export JSON/Markdown, server-side history,
batch scan, URL footprint module
"""

import asyncio
import json
import threading
import webbrowser
import time
import sys
import uuid
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engine import ZqryaEngine
from core.detector import detector
from core.banner import console

app = Flask(__name__)
CORS(app)

VERSION = "3.0.0"
HISTORY_FILE = Path(__file__).parent / "history.json"


# ─────────────────────────────────────────────────────────────────────────────
#  HISTORY (server-side persistence)
# ─────────────────────────────────────────────────────────────────────────────
def load_history() -> list:
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return []


def save_history_item(entry: dict):
    history = load_history()
    history.insert(0, entry)
    history = history[:100]  # keep max 100
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def delete_history_item(entry_id: str) -> bool:
    history = load_history()
    filtered = [h for h in history if h.get('id') != entry_id]
    if len(filtered) == len(history):
        return False
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(filtered, f, indent=2)
    except Exception:
        pass
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  FULL WEB UI  (single HTML page, zero CDN, works offline)
# ─────────────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Zqrya v3.0 — OSINT Intelligence Suite</title>
<style>
/* ============ DESIGN TOKENS ============ */
:root{
  --bg:#f5f7fb; --bg2:#ffffff; --bg3:#eef1f7; --bg4:#e2e7f0;
  --border:#dfe4ee; --border2:#c9d2e2;
  --violet:#7c3aed; --violet2:#6d28d9; --violet-soft:rgba(124,58,237,.1);
  --cyan:#0891b2; --cyan2:#06b6d4;
  --green:#16a34a; --green2:#22c55e;
  --yellow:#d97706; --red:#dc2626; --orange:#ea580c;
  --text:#0f172a; --text2:#475569; --text3:#94a3b8;
  --shadow:0 1px 3px rgba(15,23,42,.06),0 8px 24px rgba(15,23,42,.06);
  --shadow-lg:0 4px 12px rgba(15,23,42,.1),0 16px 40px rgba(15,23,42,.12);
  --radius:14px; --radius-sm:9px;
  --grad:linear-gradient(135deg,#7c3aed 0%,#4f46e5 55%,#0891b2 100%);
}
html[data-theme="dark"]{
  --bg:#0b0f1a; --bg2:#111827; --bg3:#1a2233; --bg4:#232d42;
  --border:#283248; --border2:#3b4763;
  --violet:#a78bfa; --violet2:#8b5cf6; --violet-soft:rgba(167,139,250,.12);
  --cyan:#22d3ee; --cyan2:#06b6d4;
  --green:#4ade80; --green2:#22c55e;
  --yellow:#fbbf24; --red:#f87171; --orange:#fb923c;
  --text:#e6edf7; --text2:#94a3b8; --text3:#64748b;
  --shadow:0 1px 3px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.4);
  --shadow-lg:0 4px 12px rgba(0,0,0,.4),0 16px 40px rgba(0,0,0,.5);
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Inter',system-ui,sans-serif;
  transition:background .3s,color .3s;
}

/* ============ SCROLLBAR ============ */
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:6px}
::-webkit-scrollbar-thumb:hover{background:var(--violet)}

/* ============ APP LAYOUT ============ */
.app{display:flex;min-height:100vh}

/* ============ SIDEBAR ============ */
.sidebar{
  width:250px;min-width:250px;background:var(--bg2);
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;position:sticky;top:0;height:100vh;
}
.sb-brand{
  padding:22px 20px 18px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:12px;
}
.sb-logo{
  width:38px;height:38px;border-radius:11px;background:var(--grad);
  display:flex;align-items:center;justify-content:center;
  color:#fff;font-weight:800;font-size:1.15rem;box-shadow:0 4px 12px rgba(124,58,237,.35);
}
.sb-name{font-weight:800;font-size:1.05rem;letter-spacing:.5px}
.sb-name span{color:var(--violet)}
.sb-ver{font-size:.62rem;color:var(--text3);background:var(--violet-soft);color:var(--violet);
  padding:2px 8px;border-radius:10px;margin-left:auto;font-weight:600}
.sb-nav{flex:1;overflow-y:auto;padding:14px 12px}
.sb-label{font-size:.6rem;letter-spacing:1.6px;text-transform:uppercase;color:var(--text3);
  padding:10px 8px 6px;font-weight:700}
.sb-btn{
  width:100%;text-align:left;background:none;border:none;color:var(--text2);
  padding:9px 11px;border-radius:9px;cursor:pointer;font-size:.85rem;
  display:flex;align-items:center;gap:10px;transition:all .15s;font-weight:500;
}
.sb-btn:hover{background:var(--bg3);color:var(--text)}
.sb-btn.act{background:var(--violet-soft);color:var(--violet);font-weight:700}
.sb-btn .ic{font-size:1rem;width:20px;text-align:center}
.hist-item{
  padding:8px 11px;cursor:pointer;font-size:.78rem;color:var(--text2);
  display:flex;align-items:center;gap:8px;border-radius:8px;transition:all .15s;
  border:1px solid transparent;margin-bottom:3px;
}
.hist-item:hover{background:var(--bg3);color:var(--text)}
.hist-type{
  font-size:.6rem;background:var(--bg3);border:1px solid var(--border);
  border-radius:5px;padding:1px 6px;color:var(--violet);flex-shrink:0;font-weight:700;
}
.hist-target{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.hist-del{opacity:0;background:none;border:none;color:var(--text3);cursor:pointer;
  font-size:.9rem;padding:0 2px;transition:opacity .15s;flex-shrink:0}
.hist-item:hover .hist-del{opacity:1}
.hist-del:hover{color:var(--red)}
.sb-empty{font-size:.75rem;color:var(--text3);padding:8px;text-align:center}

/* ============ MAIN ============ */
.main{flex:1;padding:28px 34px;max-width:1200px;min-width:0}
.topbar{display:flex;align-items:center;gap:14px;margin-bottom:26px}
.topbar h1{font-size:1.35rem;font-weight:800;letter-spacing:-.3px}
.topbar h1 span{color:var(--violet)}
.topbar-sub{font-size:.8rem;color:var(--text3);margin-top:2px}
.top-actions{margin-left:auto;display:flex;gap:9px;align-items:center}
.icon-btn{
  background:var(--bg2);border:1px solid var(--border);color:var(--text2);
  width:38px;height:38px;border-radius:10px;cursor:pointer;font-size:1rem;
  display:flex;align-items:center;justify-content:center;transition:all .15s;
}
.icon-btn:hover{border-color:var(--violet);color:var(--violet);transform:translateY(-1px)}
.theme-btn.active{background:var(--violet);border-color:var(--violet);color:#fff}

/* ============ SEARCH CARD ============ */
.search-card{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);
  padding:26px;box-shadow:var(--shadow);margin-bottom:22px;
}
.sc-title{font-size:1.05rem;font-weight:800;margin-bottom:4px}
.sc-sub{font-size:.8rem;color:var(--text2);margin-bottom:18px}
.type-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
.tab{
  background:var(--bg3);border:1px solid var(--border);color:var(--text2);
  padding:6px 15px;border-radius:20px;cursor:pointer;font-size:.8rem;
  transition:all .15s;font-weight:600;
}
.tab:hover{border-color:var(--violet);color:var(--violet)}
.tab.act{background:var(--violet-soft);border-color:var(--violet);color:var(--violet)}
.input-row{display:flex;gap:10px}
.target-in{
  flex:1;background:var(--bg3);border:1px solid var(--border);color:var(--text);
  padding:13px 16px;border-radius:11px;font-size:.95rem;outline:none;
  font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;
  transition:border-color .2s,box-shadow .2s;
}
.target-in:focus{border-color:var(--violet);box-shadow:0 0 0 3px var(--violet-soft)}
.target-in::placeholder{color:var(--text3)}
.scan-btn{
  background:var(--grad);color:#fff;border:none;padding:13px 28px;
  border-radius:11px;cursor:pointer;font-weight:800;font-size:.9rem;
  letter-spacing:.5px;transition:all .15s;white-space:nowrap;box-shadow:0 4px 14px rgba(124,58,237,.3);
}
.scan-btn:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 6px 18px rgba(124,58,237,.4)}
.scan-btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.opts-row{margin-top:12px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.opt{display:flex;align-items:center;gap:6px;cursor:pointer;font-size:.8rem;color:var(--text2);font-weight:500}
.opt input{accent-color:var(--violet)}
#detected{font-size:.75rem;color:var(--green);margin-left:auto;font-weight:600}

/* ============ BATCH TEXTAREA ============ */
.batch-area{display:none;margin-top:12px}
.batch-area.show{display:block}
.batch-area textarea{
  width:100%;min-height:110px;background:var(--bg3);border:1px solid var(--border);
  color:var(--text);border-radius:11px;padding:13px 16px;font-size:.85rem;outline:none;
  font-family:'SFMono-Regular',Consolas,Menlo,monospace;resize:vertical;
}
.batch-area textarea:focus{border-color:var(--violet);box-shadow:0 0 0 3px var(--violet-soft)}
.batch-hint{font-size:.72rem;color:var(--text3);margin-top:6px}

/* ============ STATUS BAR ============ */
#statusBar{
  background:var(--bg2);border:1px solid var(--border);border-radius:11px;
  padding:13px 16px;font-family:'SFMono-Regular',Consolas,Menlo,monospace;font-size:.82rem;
  color:var(--violet);margin-bottom:20px;align-items:center;gap:10px;display:none;box-shadow:var(--shadow);
}
#statusBar.show{display:flex}
.sdot{width:8px;height:8px;border-radius:50%;background:var(--violet);animation:blink 1s infinite;flex-shrink:0}
.sdot.ok{background:var(--green);animation:none}
.sdot.err{background:var(--red);animation:none}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}

/* ============ STATS OVERVIEW ============ */
.stats-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:13px;margin-bottom:22px}
.stat-card{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);
  padding:16px 18px;box-shadow:var(--shadow);position:relative;overflow:hidden;
}
.stat-card::after{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--grad)}
.stat-val{font-size:1.55rem;font-weight:800;letter-spacing:-.5px}
.stat-lbl{font-size:.7rem;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-top:3px;font-weight:600}
.stat-card.green .stat-val{color:var(--green)}
.stat-card.violet .stat-val{color:var(--violet)}
.stat-card.cyan .stat-val{color:var(--cyan)}
.stat-card.orange .stat-val{color:var(--orange)}

/* ============ RESULTS HEADER ============ */
.results-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.results-title{font-size:1rem;font-weight:800}
.results-title .tt{color:var(--violet)}
.results-meta{font-size:.75rem;color:var(--text3)}
.results-actions{display:flex;gap:7px}
.action-btn{
  background:var(--bg2);border:1px solid var(--border);color:var(--text2);
  padding:7px 14px;border-radius:8px;cursor:pointer;font-size:.76rem;font-weight:600;
  display:flex;align-items:center;gap:6px;transition:all .15s;
}
.action-btn:hover{border-color:var(--violet);color:var(--violet)}

/* ============ MODULE GRID ============ */
.mod-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px}

/* ============ MODULE CARD ============ */
.mod{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);
  overflow:hidden;transition:border-color .2s,box-shadow .2s;box-shadow:var(--shadow);
  display:flex;flex-direction:column;
}
.mod:hover{border-color:var(--border2);box-shadow:var(--shadow-lg)}
.mod.username{border-top:3px solid var(--violet)}
.mod.email   {border-top:3px solid var(--cyan)}
.mod.phone   {border-top:3px solid var(--green)}
.mod.domain  {border-top:3px solid var(--yellow)}
.mod.ip      {border-top:3px solid var(--orange)}
.mod.url     {border-top:3px solid var(--cyan2)}
.mod-hdr{padding:14px 16px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--border)}
.mod-ic{font-size:1.15rem;width:26px;text-align:center}
.mod-name{font-weight:700;font-size:.87rem;letter-spacing:.3px}
.mod-badge{margin-left:auto;font-size:.62rem;padding:3px 9px;border-radius:12px;font-weight:700;letter-spacing:.5px}
.b-found{background:rgba(22,163,74,.12);color:var(--green)}
.b-none {background:rgba(220,38,38,.1);color:var(--red)}
.mod-body{padding:14px 16px;flex:1}
.row{display:flex;justify-content:space-between;align-items:flex-start;padding:5px 0;
  border-bottom:1px solid var(--border);font-size:.8rem;gap:12px}
.row:last-child{border-bottom:none}
.rk{color:var(--text2);flex-shrink:0;font-weight:500}
.rv{color:var(--text);text-align:right;font-family:'SFMono-Regular',Consolas,Menlo,monospace;
  font-size:.77rem;word-break:break-all;max-width:210px}
.rv a{color:var(--violet);text-decoration:none}
.rv a:hover{text-decoration:underline}
.rv.ok{color:var(--green)} .rv.warn{color:var(--yellow)} .rv.bad{color:var(--red)}

/* ============ BREACH ALERT ============ */
.breach-alert{background:linear-gradient(135deg,rgba(220,38,38,.08),rgba(217,119,6,.04));
  border-left:4px solid var(--red);margin-bottom:10px;padding:12px;border-radius:8px}
.breach-detail{background:var(--bg3);padding:9px;border-radius:7px;margin-bottom:6px;border-left:2px solid var(--yellow);font-size:.75rem}
.recommendation-box{background:rgba(124,58,237,.08);padding:9px;border-radius:7px;margin-top:8px;border-left:2px solid var(--violet);font-size:.78rem}

/* ============ PLATFORM PILLS ============ */
.plat-list{display:flex;flex-wrap:wrap;gap:5px;margin-top:9px}
.pill{
  background:var(--violet-soft);border:1px solid rgba(124,58,237,.22);
  color:var(--violet);font-size:.68rem;padding:3px 9px;border-radius:12px;
  text-decoration:none;transition:all .15s;font-weight:600;
}
.pill:hover{background:var(--violet);color:#fff}
.pill.plain{background:var(--bg3);border-color:var(--border);color:var(--text2);cursor:default}
.category-header{margin-top:9px;margin-bottom:4px;font-size:.7rem;color:var(--text2);font-weight:700;text-transform:uppercase;letter-spacing:.6px}
.category-header:first-child{margin-top:0}

/* ============ TAGS / PROGRESS ============ */
.progress-bar-bg{background:var(--bg3);border-radius:10px;height:7px;overflow:hidden;margin:8px 0}
.progress-bar-fill{background:linear-gradient(90deg,var(--red),var(--yellow));height:100%;border-radius:10px;transition:width .3s}
.tag{display:inline-block;padding:3px 9px;border-radius:12px;font-size:.66rem;margin:2px;font-weight:700}
.tag-danger{background:rgba(220,38,38,.14);color:var(--red);border:1px solid var(--red)}
.tag-warning{background:rgba(217,119,6,.14);color:var(--yellow);border:1px solid var(--yellow)}
.tag-success{background:rgba(22,163,74,.14);color:var(--green);border:1px solid var(--green)}
.tag-info{background:rgba(8,145,178,.14);color:var(--cyan);border:1px solid var(--cyan)}

/* ============ EMPTY / ERROR / SKELETON ============ */
.empty{text-align:center;padding:60px 20px;color:var(--text3)}
.empty-ic{font-size:3rem;margin-bottom:14px;opacity:.4}
.empty-t{font-size:.9rem;font-weight:600}
.empty-s{font-size:.75rem;margin-top:6px}
.skel{background:linear-gradient(90deg,var(--bg3) 25%,var(--bg4) 50%,var(--bg3) 75%);
  background-size:200% 100%;animation:shimmer 1.4s infinite;border-radius:6px}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* ============ TOAST ============ */
#toast{
  position:fixed;bottom:22px;right:22px;background:var(--bg2);z-index:999;
  border:1px solid var(--border2);color:var(--text);padding:12px 18px;border-radius:11px;
  font-size:.82rem;opacity:0;transform:translateY(10px);transition:all .25s;
  pointer-events:none;box-shadow:var(--shadow-lg);max-width:340px;
}
#toast.show{opacity:1;transform:translateY(0)}
#toast.err{border-left:4px solid var(--red)}
#toast.ok{border-left:4px solid var(--green)}

/* ============ FOOTER ============ */
.footer{margin-top:30px;padding:18px 0;border-top:1px solid var(--border);
  font-size:.72rem;color:var(--text3);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
.footer a{color:var(--violet);text-decoration:none}

/* ============ ASCII BANNER ============ */
.ascii-banner{display:flex;justify-content:center;margin:2px 0 14px;overflow-x:auto}
.ascii-banner pre{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;font-size:11px;line-height:1.18;color:var(--violet);white-space:pre}
.ascii-banner pre .z-accent{color:var(--cyan)}

/* ============ SCAN COMPLETE BANNER ============ */
.done-banner{display:flex;flex-direction:column;align-items:center;gap:5px;margin-bottom:14px;padding:18px 14px 12px;background:linear-gradient(135deg,var(--violet-soft),transparent 55%),var(--bg2);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);overflow-x:auto}
.done-banner .done-badge{font-weight:800;letter-spacing:1.2px;color:var(--green);font-size:.85rem;text-transform:uppercase}
.done-banner .done-sub{color:var(--text2);font-size:.78rem;margin-bottom:4px}
.done-banner pre{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;font-size:10.5px;line-height:1.18;color:var(--violet);white-space:pre}

/* ============ RESPONSIVE ============ */
@media(max-width:860px){
  .sidebar{display:none}
  .main{padding:18px 14px}
  .mod-grid{grid-template-columns:1fr}
  .top-actions{margin-left:0}
  .topbar{flex-wrap:wrap}
  .ascii-banner{display:none}
}
</style>
</head>
<body>

<div class="app">
<aside class="sidebar">
  <div class="sb-brand">
    <div class="sb-logo">Z</div>
    <div class="sb-name">Zqrya<span>.</span></div>
    <span class="sb-ver">v3.0</span>
  </div>
  <div class="sb-nav">
    <div class="sb-label">Scan Mode</div>
    <button class="sb-btn act" onclick="setScanMode(this,'quick')" id="modeQuick">
      <span class="ic">⚡</span> Quick Scan
    </button>
    <button class="sb-btn" onclick="setScanMode(this,'deep')" id="modeDeep">
      <span class="ic">🔬</span> Deep Scan
    </button>
    <button class="sb-btn" onclick="setScanMode(this,'batch')" id="modeBatch">
      <span class="ic">📦</span> Batch Scan
    </button>
    <div class="sb-label">History</div>
    <div id="histList"><div class="sb-empty">No history yet</div></div>
  </div>
</aside>

<main class="main">
  <div class="ascii-banner">
<pre>       ▄██████▓  ▒█████     ▒█████     ██   ██      ▄██▄
      ██  ▒██▒   ▒██▒  ██▒  ▒██▒  ██▒  ▓██  ██▒    ██  ██▒
      ░ ▓██▄ ▒   ▒██░  ██░  ▒██▀▀██░   ▒██  ██░    ██  ██░
       ▒██▒  ▒   ▒██   ██░  ░▓█ ░██    ░▓████░     ██▀▀██░
      ▒██████▒▒  ░ ████▓▒░  ░▓█▒░██▓    ░ ▒██▒░    ██  ██░
      ▒ ▒▓▒ ▒ ░  ░ ▒░▒░▒░   ▒ ░░▒ ▒     ░ ▒██▒     ██  ██░
      ░ ░▒  ░      ░ ▒ ▒░   ▒ ░░▒ ▒     ░ ▒██▒     ░░  ░░
      ░  ░  ░    ░ ░ ░ ▒ ▒  ░  ░░ ░     ░  ░░      ░    ░
            ░        ░ ░ ░  ░  ░  ░     ░  ░</pre>
  </div>
  <div class="topbar">
    <div>
      <h1>OSINT <span>Intelligence Suite</span></h1>
      <div class="topbar-sub">Username · Email · Phone · Domain · IP · Website — 100% public sources</div>
    </div>
    <div class="top-actions">
      <button class="icon-btn" id="themeToggle" onclick="toggleTheme()" title="Toggle theme">🌙</button>
      <button class="icon-btn" onclick="clearAllHistory()" title="Clear history">🗑️</button>
    </div>
  </div>

  <div class="search-card">
    <div class="sc-title">🔍 New Investigation</div>
    <div class="sc-sub">Paste any target — Zqrya auto-detects the type. No API keys required.</div>
    <div class="type-tabs">
      <div class="tab act" data-t="auto" onclick="selType(this)">🤖 Auto</div>
      <div class="tab" data-t="username" onclick="selType(this)">👤 Username</div>
      <div class="tab" data-t="email" onclick="selType(this)">📧 Email</div>
      <div class="tab" data-t="phone" onclick="selType(this)">📱 Phone</div>
      <div class="tab" data-t="domain" onclick="selType(this)">🌐 Domain</div>
      <div class="tab" data-t="ip" onclick="selType(this)">🌍 IP</div>
      <div class="tab" data-t="url" onclick="selType(this)">🕸️ URL</div>
    </div>
    <div class="input-row">
      <input id="tin" class="target-in" type="text"
        placeholder="Target: username / email / +628xx / domain.com / 8.8.8.8 / https://example.com"
        onkeydown="if(event.key==='Enter')doScan()" oninput="detectLive(this.value)" autofocus>
      <button class="scan-btn" id="scanBtn" onclick="doScan()">SCAN →</button>
    </div>
    <div class="batch-area" id="batchArea">
      <textarea id="batchInput" placeholder="Paste multiple targets here, one per line:&#10;user1&#10;user2@gmail.com&#10;08123456789&#10;example.com"></textarea>
      <div class="batch-hint">Each line is scanned sequentially. Deep mode applies to every target.</div>
    </div>
    <div class="opts-row">
      <label class="opt"><input type="checkbox" id="deepCk"> Deep (all modules)</label>
      <label class="opt"><input type="checkbox" id="reportCk" checked> Save report</label>
      <label class="opt"><input type="checkbox" id="bannerCk" checked> Show banner on complete</label>
      <span id="detected"></span>
    </div>
  </div>

  <div id="statusBar">
    <span class="sdot" id="sdot"></span>
    <span id="stxt">Ready</span>
  </div>

  <div id="statsRow" style="display:none"></div>

  <div id="results">
    <div class="empty">
      <div class="empty-ic">🕸️</div>
      <div class="empty-t">Enter a target to start investigating</div>
      <div class="empty-s">Zqrya uses public sources only — for education & authorized research</div>
    </div>
  </div>

  <div class="footer">
    <span>◤ Zqrya v3.0 — OSINT Intelligence Suite · Localhost</span>
    <span>⚠️ For ethical & educational use only</span>
  </div>
</main>
</div>
<div id="toast"></div>

<script>
let curType = 'auto';
let scanMode = 'quick';
let lastResults = null;
let lastTarget = '';
let lastDtype = '';
let lastUsedType = '';

const PLACEHOLDER = {
  auto: 'Target: username / email / +628xx / domain.com / 8.8.8.8 / https://...',
  username: 'Username (e.g. ruyynn)',
  email: 'Email (e.g. user@gmail.com)',
  phone: 'Phone (e.g. 08123456789 or +12125551234)',
  domain: 'Domain (e.g. example.com)',
  ip: 'IP Address (e.g. 8.8.8.8 or 2606:4700::)',
  url: 'Website URL (e.g. https://example.com)',
};

/* ── THEME ── */
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'light';
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('zqrya_theme', next);
  document.getElementById('themeToggle').textContent = next === 'dark' ? '☀️' : '🌙';
  document.getElementById('themeToggle').classList.toggle('active', next === 'dark');
}
(function initTheme() {
  const saved = localStorage.getItem('zqrya_theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  document.getElementById('themeToggle').textContent = saved === 'dark' ? '☀️' : '🌙';
  if (saved === 'dark') document.getElementById('themeToggle').classList.add('active');
})();

/* ── TYPE SELECTION ── */
function selType(el) {
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('act'));
  el.classList.add('act');
  curType = el.dataset.t;
  document.getElementById('tin').placeholder = PLACEHOLDER[curType] || PLACEHOLDER.auto;
  document.getElementById('detected').textContent = '';
}

function setScanMode(el, m) {
  document.querySelectorAll('.sb-btn').forEach(b=>b.classList.remove('act'));
  el.classList.add('act');
  scanMode = m;
  document.getElementById('deepCk').checked = m === 'deep';
  document.getElementById('batchArea').classList.toggle('show', m === 'batch');
  document.getElementById('tin').style.display = m === 'batch' ? 'none' : '';
  if (m === 'batch') {
    document.getElementById('detected').textContent = '📦 Batch mode';
  } else {
    document.getElementById('detected').textContent = '';
    detectLive(document.getElementById('tin').value);
  }
}

function detectLive(val) {
  if (!val || curType !== 'auto') { document.getElementById('detected').textContent=''; return; }
  const d = document.getElementById('detected');
  if (/^https?:\/\//i.test(val)) d.textContent='🕸️ Detected: website URL';
  else if (/^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$/i.test(val)) d.textContent='📧 Detected: email';
  else if (/(\+?\d[\d\s\-]{7,14})/.test(val) && val.replace(/\D/g,'').length >= 8) d.textContent='📱 Detected: phone';
  else if (/^(\d{1,3}\.){3}\d{1,3}$/.test(val) || /^[0-9a-f:]+$/i.test(val)) d.textContent='🌍 Detected: IP';
  else if (/^[a-z0-9\-]+(\.[a-z]{2,})+$/i.test(val)) d.textContent='🌐 Detected: domain';
  else if (val.length >= 2) d.textContent='👤 Detected: username';
  else d.textContent='';
}

/* ── SCAN ── */
async function doScan() {
  const btn = document.getElementById('scanBtn');
  const bar = document.getElementById('statusBar');
  const dot = document.getElementById('sdot');
  const stxt = document.getElementById('stxt');

  let targets, type = curType;
  if (scanMode === 'batch') {
    targets = document.getElementById('batchInput').value.split('\n')
      .map(s=>s.trim()).filter(s=>s && !s.startsWith('#'));
    if (!targets.length) { showToast('⚠️ Enter at least one target', true); return; }
  } else {
    const target = document.getElementById('tin').value.trim();
    if (!target) { showToast('⚠️ Enter a target first', true); return; }
    targets = [target];
  }

  const deep = document.getElementById('deepCk').checked;
  const report = document.getElementById('reportCk').checked;
  btn.disabled = true; btn.textContent = 'SCANNING…';
  bar.classList.add('show'); dot.className = 'sdot';
  stxt.textContent = `Scanning ${targets.length} target(s) — please wait...`;
  showSkeleton(targets.length > 1 ? targets.length : 3);

  try {
    if (targets.length === 1) {
      const res = await fetch('/api/scan', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({target: targets[0], type, deep, report})
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      finishScan(data, targets[0]);
    } else {
      // Batch: scan sequentially
      const allResults = {};
      let allReport = null;
      for (let i = 0; i < targets.length; i++) {
        stxt.textContent = `[${i+1}/${targets.length}] Scanning "${targets[i]}"...`;
        const res = await fetch('/api/scan', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({target: targets[i], type:'auto', deep, report:false})
        });
        const data = await res.json();
        if (!data.error && data.results) {
          allResults[targets[i]] = data.results;
        }
      }
      const combined = combineResults(allResults, targets);
      dot.className = 'sdot ok';
      stxt.textContent = `✅ Done — ${targets.length} target(s) scanned — ${new Date().toLocaleTimeString()}`;
      renderStats(combined, targets.length);
      renderResults(combined, targets.join(', '), 'batch');
      showCompleteBanner(targets.join(', '), Object.keys(combined).length);
      addHistoryEntry({targets, type:'batch', deep, ts: Date.now()});
      showToast(`✅ ${targets.length} targets scanned`);
    }
  } catch(e) {
    dot.className = 'sdot err';
    stxt.textContent = '❌ ' + e.message;
    showError(e.message);
  }
  btn.disabled = false; btn.textContent = 'SCAN →';
}

function finishScan(data, target) {
  const bar = document.getElementById('statusBar');
  const dot = document.getElementById('sdot');
  const stxt = document.getElementById('stxt');
  const mods = Object.keys(data.results||{}).filter(k=>!k.startsWith('_'));
  dot.className = 'sdot ok';
  stxt.textContent = `✅ Done — ${mods.length} module(s) — "${target}" — ${new Date().toLocaleTimeString()}`;
  lastResults = data.results;
  lastTarget = data.target || target;
  lastDtype = data.detected_type || curType;
  lastUsedType = data.used_type || curType;
  renderStats(data.results, 1);
  renderResults(data.results, target, data.detected_type || curType);
  showCompleteBanner(target, mods.length);
  addHistoryEntry({target, type:data.detected_type||curType, deep:false, ts: Date.now()});
  if (data.report_file) showToast('📄 Report saved: ' + data.report_file.split('/').pop());
}

function combineResults(map, targets) {
  const combined = {};
  Object.values(map).forEach(moduleSet => {
    Object.entries(moduleSet).forEach(([k,v]) => {
      if (k.startsWith('_')) return;
      if (!combined[k]) combined[k] = {module:k, target:targets.join(', '), data:{}, sources:[]};
      if (v && v.data) Object.assign(combined[k].data, v.data);
    });
  });
  return combined;
}

/* ── SCAN COMPLETE BANNER ── */
function completeBannerHTML(target, modCount) {
  return `<div class="done-banner">
    <div class="done-badge">✅ Scan Complete</div>
    <div class="done-sub">${esc(target)} · ${modCount} module(s) · ${new Date().toLocaleTimeString()}</div>
<pre>       ▄██████▓  ▒█████     ▒█████     ██   ██      ▄██▄
      ██  ▒██▒   ▒██▒  ██▒  ▒██▒  ██▒  ▓██  ██▒    ██  ██▒
      ░ ▓██▄ ▒   ▒██░  ██░  ▒██▀▀██░   ▒██  ██░    ██  ██░
       ▒██▒  ▒   ▒██   ██░  ░▓█ ░██    ░▓████░     ██▀▀██░
      ▒██████▒▒  ░ ████▓▒░  ░▓█▒░██▓    ░ ▒██▒░    ██  ██░
      ▒ ▒▓▒ ▒ ░  ░ ▒░▒░▒░   ▒ ░░▒ ▒     ░ ▒██▒     ██  ██░
      ░ ░▒  ░      ░ ▒ ▒░   ▒ ░░▒ ▒     ░ ▒██▒     ░░  ░░
      ░  ░  ░    ░ ░ ░ ▒ ▒  ░  ░░ ░     ░  ░░      ░    ░
            ░        ░ ░ ░  ░  ░  ░     ░  ░</pre>
  </div>`;
}

function showCompleteBanner(target, modCount) {
  const ck = document.getElementById('bannerCk');
  if (!ck || !ck.checked) return;
  const res = document.getElementById('results');
  if (!res || !res.innerHTML) return;
  res.innerHTML = completeBannerHTML(target, modCount) + res.innerHTML;
}

/* ── STATS ── */
function renderStats(results, targetCount) {
  const mods = Object.entries(results||{}).filter(([k])=>!k.startsWith('_'));
  const totalFound = mods.reduce((acc,[,r])=>{
    const d = r?.data||{};
    if (d.total_found) return acc + d.total_found;
    if (d.social_links) return acc + d.social_links.length;
    if (d.emails) return acc + d.emails.length;
    return acc + (Object.keys(d).length ? 1 : 0);
  }, 0);
  const el = document.getElementById('statsRow');
  el.style.display = 'grid';
  el.innerHTML = `
    <div class="stat-card violet"><div class="stat-val">${mods.length}</div><div class="stat-lbl">Modules Run</div></div>
    <div class="stat-card green"><div class="stat-val">${totalFound}</div><div class="stat-lbl">Total Findings</div></div>
    <div class="stat-card cyan"><div class="stat-val">${targetCount}</div><div class="stat-lbl">Targets Scanned</div></div>
    <div class="stat-card orange"><div class="stat-val">${new Date().toLocaleTimeString()}</div><div class="stat-lbl">Completed At</div></div>`;
}

/* ── RESULTS RENDERING ── */
function renderResults(results, target, dtype) {
  if (!results) { showError('No results'); return; }
  const mods = Object.entries(results).filter(([k])=>!k.startsWith('_'));
  if (!mods.length) { showError('No results found for: '+target); return; }
  const nameMap = {username:'👤 Username', email:'📧 Email', phone:'📱 Phone', domain:'🌐 Domain', ip:'🌍 IP', url:'🕸️ Website', maigret:'🧠 Maigret', darkweb:'🌑 Dark Web'};
  const typeChip = dtype ? `<span style="color:var(--text3);font-size:.75rem;margin-left:8px">[${dtype}]</span>` : '';
  let html = `<div class="results-hdr">
      <div class="results-title">Results for <span class="tt">${esc(target)}</span>${typeChip}</div>
      <div class="results-meta">${mods.length} module(s) · ${new Date().toLocaleTimeString()}</div>
      <div class="results-actions">
        <button class="action-btn" onclick="exportJSON()">📋 JSON</button>
        <button class="action-btn" onclick="exportMarkdown()">📝 Markdown</button>
        <button class="action-btn" onclick="window.print()">🖨️ Print</button>
      </div>
    </div><div class="mod-grid">`;
  mods.forEach(([name,result]) => { html += buildModCard(name, result); });
  html += '</div>';
  document.getElementById('results').innerHTML = html;
}

function buildModCard(name, result) {
  const icons = {username:'👤',email:'📧',phone:'📱',domain:'🌐',ip:'🌍',url:'🕸️'};
  const names = {username:'USERNAME',email:'EMAIL',phone:'PHONE',domain:'DOMAIN',ip:'IP',url:'WEBSITE'};
  const icon = icons[name]||'🔍';
  const data = result?.data || {};
  const hasData = result && !result.error;
  const badge = hasData ? '<span class="mod-badge b-found">✓ FOUND</span>' : '<span class="mod-badge b-none">✗ NONE</span>';
  let body = '';
  if (!hasData) body = `<div style="color:var(--red);font-size:.8rem;padding:4px 0">${esc(result?.error||'No data')}</div>`;
  else if (name === 'username') body = buildUsername(data);
  else if (name === 'email') body = buildEmail(data);
  else if (name === 'phone') body = buildPhone(data);
  else if (name === 'domain') body = buildDomain(data);
  else if (name === 'ip') body = buildIP(data);
  else if (name === 'url') body = buildURL(data);
  else if (name === 'maigret') body = buildMaigret(data);
  else if (name === 'darkweb') body = buildDarkWeb(data);
  else body = row('Data', JSON.stringify(data).slice(0,200));
  return `<div class="mod ${name}"><div class="mod-hdr"><span class="mod-ic">${icon}</span><span class="mod-name">${names[name]||name.toUpperCase()} OSINT</span>${badge}</div><div class="mod-body">${body}</div></div>`;
}

function buildUsername(d) {
  const found = d.found || [];
  const total = d.total_found || 0;
  let html = row('Username', d.username) + row('Checked', `${d.total_checked||0} platforms`) + row('Found', `<span class="${total>0?'ok':'bad'}">${total} platforms</span>`);
  if (d.categories?.length) html += row('Categories', d.categories.join(', '));
  if (d.possible_emails?.length) html += row('Email hints', d.possible_emails.slice(0,3).join('<br>'));
  if (found.length) {
    const byCat = groupByCategory(found);
    html += `<div style="margin-top:10px">`;
    Object.entries(byCat).forEach(([cat, items]) => {
      html += `<div class="category-header">${esc(cat)} (${items.length})</div><div class="plat-list">`;
      items.slice(0,15).forEach(p => { html += `<a class="pill" href="${esc(p.url)}" target="_blank">${esc(p.platform)}</a>`; });
      if (items.length > 15) html += `<span class="pill plain">+${items.length-15} more</span>`;
      html += '</div>';
    });
    html += '</div>';
  }
  return html;
}

function groupByCategory(found) {
  const map = {};
  found.forEach(p => { const c = p.category||'other'; (map[c]=map[c]||[]).push(p); });
  return map;
}

function buildEmail(d) {
  let html = row('Email', d.email) + row('Domain', d.domain) + row('MX Records', d.mx_records?.length ? d.mx_records.map(m=>m.exchange||m).join('<br>') : '<span class="bad">None</span>');
  html += row('SPF', d.spf ? '<span class="ok">✓ Present</span>' : '<span class="bad">✗ Missing</span>');
  html += row('DMARC', d.dmarc ? '<span class="ok">✓ Present</span>' : '<span class="warn">✗ Missing</span>');
  html += row('DKIM', d.dkim_hint ? '<span class="ok">✓ Detected</span>' : '<span class="warn">Not detected</span>');
  html += row('Disposable', d.disposable ? '<span class="bad">Yes ⚠</span>' : '<span class="ok">No</span>');
  html += row('Free provider', d.free_provider ? '<span class="warn">Yes</span>' : 'No');
  html += row('Gravatar', d.gravatar ? `<a href="${esc(d.gravatar_profile||d.gravatar)}" target="_blank">✓ Has profile</a>` : 'Not found');
  html += row('Website', d.has_website ? `<a href="${esc(d.website_url)}" target="_blank">✓ ${esc(d.website_url)}</a>` : '<span class="bad">No website</span>');

  if (d.breach_info && d.breach_info.has_breaches) {
    const bi = d.breach_info;
    html += `<div class="breach-alert" style="margin-top:10px">
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
        <span class="tag tag-danger">${esc(bi.risk_level?.toUpperCase()||'RISK')}</span>
        <span class="tag tag-warning">Risk Score: ${bi.risk_score||0}/100</span>
        <span class="tag tag-info">${bi.total_breaches||0} Breaches</span>
      </div>
      <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${bi.risk_score||0}%"></div></div>
      <p style="margin:6px 0;font-size:.75rem">${esc(bi.message||'Known breaches detected')}</p>`;
    if (bi.username_may_be_affected) html += `<div class="tag tag-warning">⚠️ Username/Email may be affected</div>`;
    if (bi.breaches?.length) {
      html += `<details style="margin-top:6px"><summary style="cursor:pointer;color:var(--violet);font-size:.7rem;font-weight:600">📋 View ${bi.breaches.length} breach(es)</summary><div style="margin-top:6px">`;
      bi.breaches.forEach(b => {
        html += `<div class="breach-detail"><strong>${esc(b.name)}</strong> (${b.year}) <span class="tag tag-${b.risk==='critical'?'danger':(b.risk==='high'?'warning':'info')}" style="float:right">${esc(b.risk?.toUpperCase()||'UNKNOWN')}</span><br>📊 ${(b.records||0).toLocaleString()} records<br>📁 ${esc(b.data_types?.join(', ')||'N/A')}<br><small>${esc((b.description||'').slice(0,120))}</small></div>`;
      });
      html += `</div></details>`;
    }
    if (bi.recommendation) html += `<div class="recommendation-box"><strong>🔒 Recommendation:</strong><br>${esc(bi.recommendation)}</div>`;
    html += `</div>`;
  }
  return html;
}

function buildPhone(d) {
  let html = row('Input', d.input) + row('E.164', d.e164) + row('International', d.international) + row('National', d.national);
  html += row('Country', `${d.country||'?'} (${d.country_iso||'?'})`);
  html += row('Provider', d.provider||'Unknown') + row('Type', d.line_type||'Unknown') + row('Location', d.location||'—');
  html += row('Timezone', (d.timezones||[]).slice(0,2).join(', ')||'—');
  html += row('Mobile', d.is_mobile ? '<span class="ok">Yes</span>' : 'No');
  if (d.whatsapp_link) html += row('WhatsApp', `<a href="${esc(d.whatsapp_link)}" target="_blank">Open chat</a>`);
  if (d.telegram_link) html += row('Telegram', `<a href="${esc(d.telegram_link)}" target="_blank">Open chat</a>`);
  if (d.possible_handles?.length) html += row('Handles', d.possible_handles.join(', '));
  return html;
}

function buildDomain(d) {
  let html = row('Domain', d.domain) + row('IPv4', (d.ip_addresses||[]).join(', ')||'<span class="bad">None</span>');
  html += row('IPv6', (d.ipv6_addresses||[]).slice(0,2).join(', ')||'—') + row('Nameservers', (d.nameservers||[]).join('<br>')||'—');
  html += row('MX', (d.mx_records||[]).map(m=>m.exchange||m).join('<br>')||'<span class="bad">None</span>');
  html += row('HTTP', d.http_status ? `<span class="${d.http_status===200?'ok':'warn'}">${d.http_status}</span>` : '—');
  html += row('HTTPS', d.https_status ? `<span class="${d.https_status===200?'ok':'warn'}">${d.https_status}</span>` : '—');
  html += row('Server', esc(d.server_header||'—')) + row('Title', esc((d.title||'—').slice(0,60)));
  if (d.whois) {
    const w = d.whois;
    html += row('Registrar', esc(w.registrar||'—'));
    html += row('Created', esc(w.creation_date||'—'));
    html += row('Expires', esc(w.expiration_date||'—'));
  }
  if (d.technologies?.length) html += row('Tech stack', d.technologies.join(', '));
  if (d.security_headers) {
    const sh = d.security_headers;
    const flags = [sh.hsts?'<span class="ok">HSTS</span>':'<span class="bad">No HSTS</span>', sh.csp?'<span class="ok">CSP</span>':'<span class="bad">No CSP</span>', sh.xframe?'<span class="ok">X-Frame</span>':''].filter(Boolean).join(' ');
    if (flags) html += row('Security', flags);
  }
  return html;
}

function buildIP(d) {
  let html = row('IP', d.ip) + row('Version', `IPv${d.version}`) + row('Country', d.country ? `${d.country} (${d.country_code})` : '—');
  html += row('Region', d.region||'—') + row('City', d.city||'—') + row('ZIP', d.zip||'—');
  html += row('Coords', d.lat ? `${d.lat}, ${d.lon}` : '—') + row('Timezone', d.timezone||'—');
  html += row('ISP', d.isp||'—') + row('Org', d.org||'—') + row('ASN', d.asn ? `${d.asn} ${d.asn_name||''}` : '—');
  html += row('Reverse DNS', d.reverse_dns||'—');
  html += row('Risk Score', d.risk_score != null ? `<span class="${d.risk_score>70?'bad':d.risk_score>40?'warn':'ok'}">${d.risk_score}/100</span>` : '—');
  html += row('Proxy/VPN', d.is_proxy ? '<span class="bad">⚠ Detected</span>' : '<span class="ok">No</span>');
  html += row('Hosting', d.is_hosting ? '<span class="warn">Yes (datacenter)</span>' : 'No');
  html += row('Mobile', d.is_mobile ? '<span class="ok">Yes</span>' : 'No');
  if (d.rdap?.organization) html += row('RIR Org', esc(d.rdap.organization));
  if (d.rdap?.registered) html += row('Registered', d.rdap.registered);
  if (d.abuse_contact) html += row('Abuse', `<a href="mailto:${esc(d.abuse_contact)}">${esc(d.abuse_contact)}</a>`);
  return html;
}

function buildURL(d) {
  let html = row('URL', `<a href="${esc(d.url)}" target="_blank">${esc(d.url)}</a>`);
  html += row('Final URL', d.final_url && d.final_url !== d.url ? `<a href="${esc(d.final_url)}" target="_blank">${esc(d.final_url)}</a>` : '—');
  html += row('Status', d.status ? `<span class="${d.status===200?'ok':'warn'}">${d.status}</span>` : '—');
  html += row('Title', esc((d.title||'—').slice(0,70)));
  if (d.description) html += row('Description', esc(d.description.slice(0,100)));
  html += row('Language', d.language||'—');
  if (d.author) html += row('Author', esc(d.author));
  html += row('Server', esc(d.server_header||'—'));
  if (d.technologies?.length) html += row('Tech stack', d.technologies.join(', '));
  if (d.emails?.length) html += row('Emails', d.emails.map(e=>`<a href="mailto:${esc(e)}">${esc(e)}</a>`).join('<br>'));
  if (d.phone_numbers?.length) html += row('Phones', d.phone_numbers.join('<br>'));
  if (d.social_links?.length) {
    html += `<div style="margin-top:8px;font-size:.72rem;color:var(--text3)">Social profiles found (${d.social_links.length}):</div><div class="plat-list">`;
    d.social_links.slice(0,24).forEach(s => { html += `<a class="pill" href="${esc(s.url)}" target="_blank">${esc(s.platform)}</a>`; });
    if (d.social_links.length > 24) html += `<span class="pill plain">+${d.social_links.length-24} more</span>`;
    html += '</div>';
  }
  return html;
}

function buildMaigret(d) {
  const found = d.found || [];
  let html = row('Username', d.username) + row('Engine', d.engine || 'maigret') + row('Checked', `${d.total_checked||0} sites`) + row('Found', `<span class="${found.length>0?'ok':'bad'}">${found.length} profiles</span>`);
  if (d.real_names?.length) html += row('Real names', d.real_names.join(', '));
  if (found.length) {
    html += `<div style="margin-top:8px;font-size:.72rem;color:var(--text3)">Profiles (Maigret 600+):</div><div class="plat-list">`;
    found.slice(0,40).forEach(p => {
      const nm = p.real_name ? ` (${esc(p.real_name)})` : '';
      html += `<a class="pill" href="${esc(p.url)}" target="_blank" title="${esc(p.bio||'')}">${esc(p.platform)}${nm}</a>`;
    });
    if (found.length > 40) html += `<span class="pill plain">+${found.length-40} more</span>`;
    html += '</div>';
  }
  return html;
}

function buildDarkWeb(d) {
  let html = row('Query', d.query) + row('Type', d.query_type) + row('Sources', `${d.sources_found} found / ${d.sources_checked} checked`);
  html += row('Records', d.total_records != null ? `<span class="${d.total_records>0?'bad':'ok'}">${d.total_records}</span>` : '—');
  if (d.breach_count) html += row('Hudson Rock', `<span class="bad">⚠ ${d.breach_count} infection(s)</span>`);
  if (d.found_in?.length) html += row('Found in', d.found_in.map(s=>`<span class="tag tag-danger">${esc(s)}</span>`).join(' '));
  const hr = d.hudson_rock || {};
  const hrEmail = hr.email || hr.username || {};
  if (hrEmail.infections?.length) {
    html += `<div style="margin-top:8px;font-size:.72rem;color:var(--text3)">Infostealer infections (${hrEmail.infections.length}):</div>`;
    hrEmail.infections.slice(0,5).forEach(inf => {
      html += `<div class="breach-detail"><strong>${esc(inf.stealer_family||'?')}</strong> — ${esc(inf.date_compromised||'?')}<br>OS: ${esc(inf.os||'?')}${inf.computer_name?' · PC: '+esc(inf.computer_name):''}</div>`;
    });
  }
  if (!d.found_in?.length && !d.breach_count) html += row('Status', '<span class="ok">✓ Clean</span>');
  return html;
}

function row(k, v) { return `<div class="row"><span class="rk">${k}</span><span class="rv">${v}</span></div>`; }
function esc(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

/* ── EXPORT ── */
function exportJSON() {
  if (!lastResults) { showToast('⚠️ No results to export', true); return; }
  const data = {target:lastTarget, type:lastDtype, generated:new Date().toISOString(), tool:'Zqrya', results:lastResults};
  downloadFile(JSON.stringify(data, null, 2), 'application/json', `zqrya-${lastTarget}-${Date.now()}.json`);
  showToast('✅ JSON exported');
}
function exportMarkdown() {
  if (!lastResults) { showToast('⚠️ No results to export', true); return; }
  let md = `# ◤ Zqrya Report — ${lastTarget}\n\n- **Generated:** ${new Date().toISOString()}\n- **Type:** ${lastDtype}\n\n---\n\n`;
  Object.entries(lastResults).filter(([k])=>!k.startsWith('_')).forEach(([name, r]) => {
    const d = r?.data || {};
    md += `## ${name.toUpperCase()} MODULE\n\n`;
    Object.entries(d).filter(([k])=>!k.startsWith('_') && k !== 'timestamp').forEach(([k,v]) => {
      md += `- **${k.replace(/_/g,' ').replace(/\b\w/g, c=>c.toUpperCase())}:** ${typeof v === 'object' ? JSON.stringify(v) : v}\n`;
    });
    md += '\n';
  });
  downloadFile(md, 'text/markdown', `zqrya-${lastTarget}-${Date.now()}.md`);
  showToast('✅ Markdown exported');
}
function downloadFile(content, mime, filename) {
  const blob = new Blob([content], {type:mime});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

/* ── HISTORY (server-side) ── */
async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    const data = await res.json();
    renderHistory(data.history || []);
  } catch(e) { /* history unavailable */ }
}
function renderHistory(history) {
  const el = document.getElementById('histList');
  if (!history.length) { el.innerHTML = '<div class="sb-empty">No history yet</div>'; return; }
  el.innerHTML = history.slice(0,25).map(h => {
    const label = h.type === 'batch' ? (h.targets ? h.targets.join(', ') : 'batch') : h.target;
    return `<div class="hist-item" onclick="loadHistoryItem('${esc(String(h.target).replace(/'/g,"\\'"))}','${esc(h.type||'auto')}')">
      <span class="hist-type">${esc(h.type||'?')}</span>
      <span class="hist-target" title="${esc(label)}">${esc(label)}</span>
      <button class="hist-del" onclick="event.stopPropagation();delHistoryItem('${esc(h.id)}')" title="Delete">✕</button>
    </div>`;
  }).join('');
}
async function addHistoryEntry(entry) {
  try {
    await fetch('/api/history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(entry)});
    loadHistory();
  } catch(e) {}
}
async function delHistoryItem(id) {
  await fetch('/api/history/'+id, {method:'DELETE'});
  loadHistory();
}
async function clearAllHistory() {
  if (!confirm('Clear all scan history?')) return;
  await fetch('/api/history', {method:'DELETE'});
  loadHistory();
  showToast('🗑️ History cleared');
}
function loadHistoryItem(target, type) {
  if (type === 'batch') return;
  document.getElementById('tin').value = target;
  document.querySelectorAll('.tab').forEach(t=>{ t.classList.remove('act'); if(t.dataset.t===type) t.classList.add('act'); });
  curType = type;
  doScan();
}

/* ── UTILITIES ── */
function showSkeleton(count) {
  document.getElementById('statsRow').style.display = 'none';
  document.getElementById('results').innerHTML = `<div class="results-hdr"><div class="results-title" style="color:var(--text3)">Scanning…</div></div>
    <div class="mod-grid">${Array.from({length:count}).map(()=>`<div class="mod" style="padding:18px"><div class="skel" style="width:40%;height:12px;margin-bottom:12px"></div><div class="skel" style="width:92%;height:10px;margin-bottom:8px"></div><div class="skel" style="width:70%;height:10px;margin-bottom:8px"></div><div class="skel" style="width:82%;height:10px"></div></div>`).join('')}</div>`;
}
function showError(msg) { document.getElementById('results').innerHTML = `<div class="empty"><div class="empty-ic">⚠️</div><div class="empty-t" style="color:var(--red)">${esc(msg)}</div></div>`; }
function showToast(msg, isErr) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = isErr ? 'err show' : 'ok show';
  setTimeout(()=>t.classList.remove('show'), 3200);
}

/* ── INIT ── */
loadHistory();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  FLASK ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return HTML


@app.route('/api/scan', methods=['POST'])
def api_scan():
    try:
        body = request.get_json(force=True)
        target = (body.get('target') or '').strip()
        scan_type = body.get('type', 'auto')
        deep = bool(body.get('deep', False))
        save_report = bool(body.get('report', False))

        if not target:
            return jsonify({'error': 'No target provided'}), 400

        from core.detector import detector as det
        entity = det.detect(target)
        detected_type = entity.type
        norm_target = entity.normalized

        use_type = scan_type if scan_type != 'auto' else detected_type

        results = run_async_scan(norm_target, use_type, deep)

        report_file = None
        if save_report and results:
            from reports.generator import ReportGenerator
            rg = ReportGenerator(output_dir='output')
            loop = asyncio.new_event_loop()
            try:
                fp = loop.run_until_complete(rg.save_html(results))
                report_file = str(fp)
            finally:
                loop.close()

        return jsonify({
            'target': norm_target,
            'detected_type': detected_type,
            'used_type': use_type,
            'results': make_serializable(results),
            'report_file': report_file,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/history', methods=['GET', 'POST', 'DELETE'])
def api_history():
    if request.method == 'GET':
        return jsonify({'history': load_history()})

    if request.method == 'DELETE':
        try:
            HISTORY_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return jsonify({'status': 'cleared'})

    # POST
    body = request.get_json(force=True)
    entry = {
        'id': str(uuid.uuid4())[:8],
        'target': body.get('target', ''),
        'targets': body.get('targets'),
        'type': body.get('type', 'auto'),
        'deep': bool(body.get('deep', False)),
        'ts': int(time.time() * 1000)
    }
    save_history_item(entry)
    return jsonify({'status': 'saved', 'id': entry['id']})


@app.route('/api/history/<entry_id>', methods=['DELETE'])
def api_history_delete(entry_id):
    ok = delete_history_item(entry_id)
    return jsonify({'status': 'deleted' if ok else 'not_found'})


@app.route('/api/detect', methods=['POST'])
def api_detect():
    body = request.get_json(force=True)
    target = (body.get('target') or '').strip()
    if not target:
        return jsonify({'error': 'No target'}), 400
    entity = detector.detect(target)
    return jsonify({'type': entity.type, 'normalized': entity.normalized, 'confidence': entity.confidence})


@app.route('/api/health')
def api_health():
    return jsonify({'status': 'ok', 'version': VERSION, 'tool': 'Zqrya', 'timestamp': datetime.now().isoformat()})


# ─────────────────────────────────────────────────────────────────────────────
#  ASYNC RUNNER
# ─────────────────────────────────────────────────────────────────────────────
def run_async_scan(target: str, target_type: str, deep: bool) -> dict:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_do_scan(target, target_type, deep))
    finally:
        loop.close()


async def _do_scan(target: str, target_type: str, deep: bool) -> dict:
    engine = ZqryaEngine(timeout=12, max_concurrent=25)
    async with engine:
        if deep:
            return await engine.investigate_all(target, target_type)
        else:
            result = await engine.investigate(target, target_type)
            if result and not result.get('error'):
                return {target_type: result}
            return {}


def make_serializable(obj):
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_serializable(i) for i in obj]
    elif isinstance(obj, set):
        return sorted(list(obj))
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def start_web_server(port: int = 7331, open_browser: bool = True):
    console.print(f"\n[bold violet]◤ Zqrya Web UI starting...[/bold violet]")
    console.print(f"[green]  → URL  : [bold]http://localhost:{port}[/bold][/green]")
    console.print(f"[dim]  → Press Ctrl+C to stop[/dim]\n")

    if open_browser:
        def _open():
            time.sleep(1.2)
            webbrowser.open(f'http://localhost:{port}')
        threading.Thread(target=_open, daemon=True).start()

    try:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except OSError as e:
        console.print(f"[red]❌ Port {port} in use. Try: python zqrya.py -web --port 8080[/red]")
        sys.exit(1)


if __name__ == '__main__':
    start_web_server()
