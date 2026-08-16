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
import os
import threading
import webbrowser
import time
import sys
import uuid
from pathlib import Path
from datetime import datetime
from stalker.config import Config

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
.type-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.tab{
  background:var(--bg3);border:1px solid var(--border);color:var(--text2);
  padding:6px 15px;border-radius:20px;cursor:pointer;font-size:.8rem;
  transition:all .15s;font-weight:600;
}
.tab:hover{border-color:var(--violet);color:var(--violet)}
.tab.act{background:var(--violet-soft);border-color:var(--violet);color:var(--violet)}
.tool-picker{
  display:flex;align-items:center;gap:10px;margin-bottom:16px;
  padding:10px 14px;border:1px dashed var(--border2);border-radius:12px;
  background:linear-gradient(135deg,var(--violet-soft),transparent 60%);
}
.tp-label{font-size:.72rem;font-weight:800;letter-spacing:.6px;color:var(--violet);white-space:nowrap}
.tp-select{
  flex:1;min-width:200px;background:var(--bg3);border:1px solid var(--border2);
  color:var(--text);padding:9px 12px;border-radius:10px;font-size:.82rem;outline:none;
  cursor:pointer;transition:border-color .15s;
}
.tp-select:hover,.tp-select:focus{border-color:var(--violet)}
.tp-select optgroup{background:var(--bg2);color:var(--text2);font-weight:700}
.tp-select option{background:var(--bg2);color:var(--text);font-weight:400}

/* ============ SETTINGS MODAL ============ */
.set-overlay{position:fixed;inset:0;background:rgba(5,8,13,.65);z-index:1000;
  display:flex;align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(3px)}
.set-modal{background:var(--bg2);border:1px solid var(--border2);border-radius:16px;
  width:min(560px,100%);max-height:82vh;display:flex;flex-direction:column;
  box-shadow:var(--shadow-lg);overflow:hidden}
.set-head{display:flex;align-items:center;justify-content:space-between;
  padding:15px 20px;border-bottom:1px solid var(--border)}
.set-title{font-size:.95rem;font-weight:800}
.set-body{padding:16px 20px;overflow-y:auto;flex:1}
.set-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:13px 20px;border-top:1px solid var(--border)}
.set-item{margin-bottom:14px}
.set-item label{display:block;font-size:.74rem;font-weight:700;color:var(--text2);margin-bottom:5px}
.set-item .set-desc{font-size:.66rem;color:var(--text3);margin-bottom:6px}
.set-item input{width:100%;background:var(--bg3);border:1px solid var(--border2);color:var(--text);
  padding:9px 12px;border-radius:9px;font-size:.8rem;outline:none;font-family:ui-monospace,Menlo,monospace}
.set-item input:focus{border-color:var(--violet)}
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
    <button class="sb-btn" onclick="setScanMode(this,'iplogger')" id="modeIPLogger">
      <span class="ic">🎯</span> IP Logger
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
      <button class="icon-btn" onclick="openSettings()" title="Settings (.env)">⚙️</button>
      <button class="icon-btn" id="themeToggle" onclick="toggleTheme()" title="Toggle theme">🌙</button>
      <button class="icon-btn" onclick="clearAllHistory()" title="Clear history">🗑️</button>
    </div>
  </div>

  <div class="search-card" id="searchCard">
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
    <div class="tool-picker">
      <label class="tp-label" for="toolSel">🛠️ OSINT TOOL</label>
      <select id="toolSel" class="tp-select" onchange="selTool(this)">
        <option value="">— Pilih tool OSINT —</option>
        <optgroup label="🪪 Identitas (Identity)">
          <option value="nik">🪪 NIK/KTP lookup</option>
          <option value="nkk">📇 NKK / Kartu Keluarga</option>
          <option value="name">👤 Name (real name)</option>
          <option value="social">📸 IG/TikTok deep</option>
          <option value="variants">🧬 Username variants</option>
          <option value="dork">🔍 Google Dork</option>
        </optgroup>
        <optgroup label="📱 Kontak (Contact)">
          <option value="ewallet">👛 E-wallet OSINT</option>
          <option value="online">🟢 Status online</option>
          <option value="hlr">📶 HLR lookup</option>
          <option value="revemail">↩️ Reverse email</option>
          <option value="leak">🧾 Password leak check</option>
        </optgroup>
        <optgroup label="🎮 Akun & Sosial (Accounts)">
          <option value="gaming">🎮 Gaming OSINT</option>
          <option value="monitor">🕵️ Monitor target</option>
        </optgroup>
        <optgroup label="🌐 Jaringan & Web (Network)">
          <option value="device">🖧 Exposed device</option>
          <option value="reverseip">↩️ Reverse IP</option>
          <option value="darkweb">🌑 Dark web / breach</option>
        </optgroup>
        <optgroup label="🖼️ File & Media">
          <option value="qr">🔳 QR/barcode decoder</option>
          <option value="geolocate">📍 Visual geolocation</option>
          <option value="exif">📷 EXIF metadata</option>
        </optgroup>
      </select>
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

  <div id="iploggerCard" style="display:none">
    <div class="search-card" style="border-top:3px solid var(--orange)">
      <div class="sc-title">🎯 IP Logger (tracking link)</div>
      <div class="sc-sub">Target buka link → IP + lokasi + device ke-log live di sini.</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
        <input id="ilRedirect" class="target-in" style="flex:2;min-width:220px"
          placeholder="URL redirect (kosong = page 'Loading…')">
        <input id="ilPort" class="target-in" style="flex:0 0 100px" value="8080"
          placeholder="Port">
        <label class="opt" style="padding:10px 0"><input type="checkbox" id="ilLive" checked> Live tracking (ping 15s)</label>
        <label class="opt" style="padding:10px 0"><input type="checkbox" id="ilPublic"> Public tunnel</label>
      </div>
      <div style="display:flex;gap:10px">
        <button class="scan-btn" id="ilStart" onclick="ilStart()">START LOGGER →</button>
        <button class="action-btn" id="ilStop" style="display:none;font-size:.9rem" onclick="ilStop()">⏹ Stop</button>
      </div>
      <div id="ilLinks" style="margin-top:12px;font-size:.8rem;display:none"></div>
      <div id="ilHits" style="margin-top:12px"></div>
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

<!-- ⚙️ Settings modal -->
<div id="settingsOverlay" class="set-overlay" style="display:none" onclick="if(event.target===this)closeSettings()">
  <div class="set-modal">
    <div class="set-head">
      <span class="set-title">⚙️ Settings <span style="color:var(--text3);font-size:.72rem;font-weight:400">(disimpan ke .env)</span></span>
      <button class="icon-btn" onclick="closeSettings()" title="Close">✕</button>
    </div>
    <div class="set-body" id="settingsBody">Memuat…</div>
    <div class="set-foot">
      <span style="font-size:.68rem;color:var(--text3)" id="setEnvFile"></span>
      <button class="scan-btn" onclick="saveSettings()" style="font-size:.8rem;padding:9px 18px">💾 SIMPAN</button>
    </div>
  </div>
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
  username: 'Username (e.g. PiuPiuu)',
  email: 'Email (e.g. user@gmail.com)',
  phone: 'Phone (e.g. 08123456789 or +12125551234)',
  domain: 'Domain (e.g. example.com)',
  ip: 'IP Address (e.g. 8.8.8.8 or 2606:4700::)',
  url: 'Website URL (e.g. https://example.com)',
  nik: 'NIK 16 digit (e.g. 3578021708900001)',
  nkk: 'NKK 16 digit (e.g. 3510080101010001)',
  qr: 'Path file / URL gambar QR atau barcode',
  ewallet: 'Nomor HP (e.g. 08123456789)',
  online: 'Username Telegram / nomor HP',
  hlr: 'Nomor HP (e.g. 08123456789)',
  revemail: 'Alamat email (e.g. user@gmail.com)',
  gaming: 'Username (Steam/Roblox/Minecraft)',
  name: 'Nama asli (e.g. Budi Santoso)',
  variants: 'Username (e.g. johndoe)',
  dork: 'Nama orang untuk Google Dork (e.g. Budi Santoso)',
  exif: 'Path file / URL gambar (JPG/PNG)',
  darkweb: 'Email / username / nomor HP',
  leak: 'Password atau teks untuk dicek bocor/tidak',
  reverseip: 'IP Address (e.g. 8.8.8.8)',
  monitor: 'Username / email / nomor HP untuk di-monitor',
  social: 'Username IG/TikTok',
  device: 'Alamat IP (e.g. 8.8.8.8)',
  geolocate: 'Path file / URL gambar',
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
  document.getElementById('toolSel').value = '';
  curType = el.dataset.t;
  document.getElementById('tin').placeholder = PLACEHOLDER[curType] || PLACEHOLDER.auto;
  document.getElementById('detected').textContent = '';
}

function selTool(el) {
  const v = el.value;
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('act'));
  curType = v || 'auto';
  if (!v) document.querySelector('.tab[data-t="auto"]').classList.add('act');
  document.getElementById('tin').placeholder = (v && PLACEHOLDER[v]) || PLACEHOLDER.auto;
  document.getElementById('detected').textContent = v ? `🛠️ Tool: ${v}` : '';
}

function setScanMode(el, m) {
  document.querySelectorAll('.sb-btn').forEach(b=>b.classList.remove('act'));
  el.classList.add('act');
  scanMode = m;
  const ilCard = document.getElementById('iploggerCard');
  if (m === 'iplogger') {
    document.getElementById('searchCard').style.display = 'none';
    ilCard.style.display = 'block';
    document.getElementById('statusBar').style.display = 'none';
    ilRefresh();
    return;
  }
  document.getElementById('searchCard').style.display = '';
  ilCard.style.display = 'none';
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
      const TOOLS = ['nik','nkk','qr','ewallet','online','hlr','revemail','gaming','social','device','geolocate','name','variants','dork','exif','darkweb','leak','reverseip','monitor'];
      if (TOOLS.includes(type)) {
        const res = await fetch('/api/osint', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({tool: type, target: targets[0]})
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        finishToolScan(data, targets[0], type);
      } else {
        const res = await fetch('/api/scan', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({target: targets[0], type, deep, report})
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        finishScan(data, targets[0]);
      }
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

function finishToolScan(data, target, tool) {
  const bar = document.getElementById('statusBar');
  const dot = document.getElementById('sdot');
  const stxt = document.getElementById('stxt');
  dot.className = 'sdot ok';
  stxt.textContent = `✅ Done — ${tool} — "${target}" — ${new Date().toLocaleTimeString()}`;
  const result = data.result || {};
  lastResults = {[tool]: {module:tool, target, data:result, sources:[]}};
  lastTarget = target;
  lastDtype = tool;
  lastUsedType = tool;
  renderToolResults(tool, result, target);
  addHistoryEntry({target, type:tool, deep:false, ts: Date.now()});
}

function renderToolResults(tool, data, target) {
  document.getElementById('statsRow').style.display = 'grid';
  document.getElementById('statsRow').innerHTML = `
    <div class="stat-card violet"><div class="stat-val">1</div><div class="stat-lbl">Modules Run</div></div>
    <div class="stat-card green"><div class="stat-val">${Object.keys(data).length}</div><div class="stat-lbl">Fields</div></div>
    <div class="stat-card cyan"><div class="stat-val">1</div><div class="stat-lbl">Targets Scanned</div></div>
    <div class="stat-card orange"><div class="stat-val">${new Date().toLocaleTimeString()}</div><div class="stat-lbl">Completed At</div></div>`;
  const icons = {nik:'🪪',nkk:'📇',qr:'🔳',ewallet:'👛',online:'🟢',hlr:'📶',revemail:'↩️',gaming:'🎮',social:'📸',device:'🖧',geolocate:'📍',name:'👤',variants:'🧬',dork:'🔍',exif:'📷',darkweb:'🌑',leak:'🧾',reverseip:'↩️',monitor:'🕵️'};
  const names = {nik:'NIK/KTP',nkk:'NKK / KARTU KELUARGA',qr:'QR/BARCODE',ewallet:'E-WALLET',online:'STATUS ONLINE',hlr:'HLR LOOKUP',revemail:'REVERSE EMAIL',gaming:'GAMING',social:'IG/TIKTOK DEEP',device:'EXPOSED DEVICE',geolocate:'VISUAL GEOLOCATION',name:'REAL NAME',variants:'USERNAME VARIANTS',dork:'GOOGLE DORK',exif:'EXIF METADATA',darkweb:'DARK WEB / BREACH',leak:'PASSWORD LEAK',reverseip:'REVERSE IP',monitor:'TARGET MONITOR'};
  const body = buildToolBody(tool, data);
  document.getElementById('results').innerHTML = `
    <div class="results-hdr">
      <div class="results-title">Results for <span class="tt">${esc(target)}</span> <span style="color:var(--text3);font-size:.75rem;margin-left:8px">[${tool}]</span></div>
      <div class="results-meta">${names[tool]||tool.toUpperCase()} · ${new Date().toLocaleTimeString()}</div>
      <div class="results-actions">
        <button class="action-btn" onclick="exportJSON()">📋 JSON</button>
        <button class="action-btn" onclick="exportMarkdown()">📝 Markdown</button>
      </div>
    </div>
    <div class="mod-grid">
      <div class="mod"><div class="mod-hdr"><span class="mod-ic">${icons[tool]||'🔍'}</span><span class="mod-name">${names[tool]||tool.toUpperCase()} OSINT</span><span class="mod-badge b-found">✓ DONE</span></div><div class="mod-body">${body}</div></div>
    </div>`;
}

function buildToolBody(tool, d) {
  if (d.error) return `<div style="color:var(--red);font-size:.8rem;padding:4px 0">${esc(d.error)}</div>`;
  if (tool === 'nik') return buildNik(d);
  if (tool === 'nkk') return buildNkk(d);
  if (tool === 'qr') return buildQr(d);
  if (tool === 'ewallet') return buildEwallet(d);
  if (tool === 'online') return buildOnline(d);
  if (tool === 'hlr') return buildHlr(d);
  if (tool === 'revemail') return buildRevemail(d);
  if (tool === 'gaming') return buildGaming(d);
  if (tool === 'social') return buildSocial(d);
  if (tool === 'device') return buildDevice(d);
  if (tool === 'geolocate') return buildGeolocate(d);
  if (tool === 'exif') return buildExif(d);
  if (tool === 'dork') return buildDork(d);
  if (tool === 'variants') return buildVariants(d);
  if (tool === 'darkweb') return buildDarkweb(d);
  if (tool === 'leak') return buildLeak(d);
  if (tool === 'reverseip') return buildReverseip(d);
  if (tool === 'name') return buildName(d);
  if (tool === 'monitor') return buildMonitor(d);
  return row('Data', JSON.stringify(d).slice(0,300));
}

function buildExif(d) {
  const meta = d.exif || {};
  if (d.error) return `<div style="color:var(--red);font-size:.8rem">${esc(d.error)}</div>`;
  if (!meta || !Object.keys(meta).length) return row('EXIF', 'Tidak ada metadata (atau file/URL tidak valid)');
  let html = '';
  const order = ['camera','make','model','date_taken','software','gps','width','height','author','copyright'];
  const seen = {};
  order.forEach(k => { if (meta[k]) { html += row(k.replace('_',' '), esc(String(meta[k]))); seen[k]=1; } });
  Object.entries(meta).forEach(([k,v]) => { if (!seen[k] && v) html += row(esc(k), esc(String(v))); });
  if (d.note) html += row('Note', esc(d.note));
  return html;
}

function buildDork(d) {
  const results = d.dork || {};
  if (d.error) return `<div style="color:var(--red);font-size:.8rem">${esc(d.error)}</div>`;
  if (!Object.keys(results).length) return row('Dork', 'Tidak ada hasil');
  let html = '';
  Object.entries(results).forEach(([cat, items]) => {
    html += `<div style="font-size:.78rem;font-weight:700;color:var(--cyan);margin:10px 0 4px">🔍 ${esc(cat)}</div>`;
    if (!items || !items.length) { html += `<div style="font-size:.72rem;color:var(--text3)">— tidak ada hasil</div>`; return; }
    (items.slice(0,8)).forEach(it => {
      html += `<div style="padding:3px 0;font-size:.76rem">`;
      if (it.url) html += `<a href="${esc(it.url)}" target="_blank" style="color:var(--green)">${esc(it.title||it.url)}</a>`;
      else html += `<span>${esc(it.title||'')}</span>`;
      if (it.snippet) html += `<div style="color:var(--text3);font-size:.7rem">${esc(String(it.snippet).slice(0,140))}</div>`;
      html += `</div>`;
    });
  });
  return html;
}

function buildVariants(d) {
  const list = d.variants || [];
  if (d.error) return `<div style="color:var(--red);font-size:.8rem">${esc(d.error)}</div>`;
  let html = row('Username', d.username) + row('Variants', list.length);
  html += '<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px">';
  list.slice(0,60).forEach(v => html += `<span class="tag tag-info">${esc(v)}</span>`);
  html += '</div>';
  if (list.length > 60) html += `<div style="font-size:.7rem;color:var(--text3);margin-top:6px">… dan ${list.length-60} lainnya</div>`;
  return html;
}

function buildDarkweb(d) {
  if (d.error) return `<div style="color:var(--red);font-size:.8rem">${esc(d.error)}</div>`;
  const entries = Object.entries(d);
  if (!entries.length) return row('Dark web', 'Tidak ada data');
  let html = '';
  entries.forEach(([src, r]) => {
    if (!r || typeof r !== 'object') return;
    const found = r.found;
    const badge = found ? '<span class="tag tag-danger">FOUND</span>' : '<span class="tag tag-success">CLEAN</span>';
    html += `<div style="padding:5px 0;border-bottom:1px solid var(--border);font-size:.78rem">
      <span style="font-weight:700;color:var(--violet)">${esc(src)}</span> ${badge}
      ${r.count ? `<span style="color:var(--orange)">${esc(String(r.count))} record</span>` : ''}
      ${r.error ? `<span style="color:var(--red);font-size:.7rem"> ${esc(r.error)}</span>` : ''}
      ${r.note ? `<div style="color:var(--text3);font-size:.7rem;margin-top:2px">${esc(r.note)}</div>` : ''}
    </div>`;
  });
  return html;
}

function buildLeak(d) {
  if (d.error) return `<div style="color:var(--red);font-size:.8rem">${esc(d.error)}</div>`;
  let html = '';
  if (d.found !== undefined) {
    if (d.found) html += row('Status', `<span class="bad">⚠ BOCOR — ${esc(String(d.count||0))}× di breach</span>`);
    else html += row('Status', '<span class="ok">✓ tidak ditemukan (aman)</span>');
  }
  if (d.details && d.details.length) {
    html += `<div style="font-size:.78rem;font-weight:700;color:var(--cyan);margin:8px 0 4px">Per-item:</div>`;
    d.details.forEach(x => {
      const st = x.found ? `<span class="bad">bocor ${esc(String(x.count||0))}×</span>`
               : x.error ? `<span style="color:var(--red)">gagal</span>`
               : '<span class="ok">aman</span>';
      html += `<div style="font-size:.76rem;padding:2px 0">${esc(x.password_hint||'?')} — ${st}</div>`;
    });
  }
  if (d.note) html += row('Note', esc(d.note));
  return html || row('Leak', 'Tidak ada data');
}

function buildReverseip(d) {
  if (d.error) return `<div style="color:var(--red);font-size:.8rem">${esc(d.error)}</div>`;
  let html = row('IP', d.ip) + row('Domains', d.count || (d.domains||[]).length);
  if (d.note) html += row('Note', esc(d.note));
  const list = d.domains || [];
  if (list.length) {
    html += '<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px">';
    list.slice(0,40).forEach(x => html += `<span class="tag tag-info">${esc(x)}</span>`);
    html += '</div>';
  }
  return html;
}

function buildName(d) {
  if (d.error) return `<div style="color:var(--red);font-size:.8rem">${esc(d.error)}</div>`;
  if (d.is_real_name === false) return row('Name', `'${esc(d.name||d.original_input||'')}' tidak terdeteksi sebagai nama asli`);
  const parts = d.name_parts || {};
  let html = row('Nama', d.original_input || d.name) ;
  if (parts.first && parts.first.length) html += row('First', esc(parts.first.join(', ')));
  if (parts.last && parts.last.length) html += row('Last', esc(parts.last.join(', ')));
  if (parts.middle && parts.middle.length) html += row('Middle', esc(parts.middle.join(', ')));
  const vars = d.search_variants || [];
  if (vars.length) {
    html += row('Variants', vars.length);
    html += '<div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px">';
    vars.slice(0,30).forEach(v => html += `<span class="tag tag-info">${esc(v)}</span>`);
    html += '</div>';
  }
  const q = d.queries || {};
  if (q.fullname && q.fullname.length) {
    html += `<div style="font-size:.78rem;font-weight:700;color:var(--cyan);margin:10px 0 4px">Google Dork queries:</div>`;
    q.fullname.slice(0,10).forEach(x => html += `<div style="font-size:.74rem;padding:1px 0">• ${esc(x)}</div>`);
  }
  if (q.variations && q.variations.length) {
    html += `<div style="font-size:.78rem;font-weight:700;color:var(--cyan);margin:10px 0 4px">Variasi username:</div>`;
    q.variations.slice(0,10).forEach(x => html += `<div style="font-size:.74rem;padding:1px 0">• ${esc(x)}</div>`);
  }
  return html;
}

function buildMonitor(d) {
  if (d.error) return `<div style="color:var(--red);font-size:.8rem">${esc(d.error)}</div>`;
  const results = d.results || [];
  let html = row('Target', d.target) + row('Type', d.type);
  if (d.note) html += row('Note', esc(d.note));
  if (!results.length) html += row('Aktivitas', 'Tidak ada aktivitas baru ditemukan (check pertama = baseline)');
  results.slice(0,15).forEach(r => {
    const src = r.source || r.platform || r.site || '?';  
    html += `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:.78rem">
      <span style="font-weight:700;color:var(--violet)">${esc(src)}</span>
      ${r.title ? ` — ${esc(String(r.title).slice(0,90))}` : ''}
      ${r.url ? `<div style="font-size:.7rem"><a href="${esc(r.url)}" target="_blank">${esc(r.url)}</a></div>` : ''}
      ${r.time ? `<div style="color:var(--text3);font-size:.68rem">${esc(String(r.time))}</div>` : ''}
    </div>`;
  });
  html += `<div style="margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
    <button class="scan-btn" id="monStart" style="font-size:.8rem;padding:8px 14px" onclick="monitorStart('${esc(d.target||'')}','${esc(d.type||'username')}')">🕵️ MONITOR TERUS →</button>
    <button class="action-btn" id="monStop" style="display:none;font-size:.8rem" onclick="monitorStop()">⏹ Stop</button>
    <span id="monStatus" style="font-size:.72rem;color:var(--text3)"></span>
  </div>
  <div id="monLive" style="margin-top:8px"></div>`;
  return html;
}

/* ── CONTINUOUS MONITOR (web loop mode) ── */
let monPoll = null;
async function monitorStart(target, type) {
  const btn = document.getElementById('monStart');
  btn.disabled = true; btn.textContent = 'STARTING…';
  try {
    const res = await fetch('/api/monitor/start', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({target, type, interval: 30})
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    btn.disabled = false; btn.textContent = 'RESTART MONITOR →';
    document.getElementById('monStop').style.display = '';
    const st = document.getElementById('monStatus');
    st.innerHTML = `<span style="color:var(--green)">🟢 monitoring "${esc(target)}" — cek tiap ${data.interval}s</span>`;
    document.getElementById('monLive').innerHTML = '<div style="font-size:.72rem;color:var(--text3)">Menunggu check pertama (baseline disimpan)...</div>';
    monPoll = setInterval(monitorRefresh, 4000);
    monitorRefresh();
    showToast('🕵️ Monitor started');
  } catch(e) {
    btn.disabled = false; btn.textContent = '🕵️ MONITOR TERUS →';
    showToast('❌ ' + e.message, true);
  }
}
async function monitorStop() {
  await fetch('/api/monitor/stop', {method: 'POST'});
  if (monPoll) { clearInterval(monPoll); monPoll = null; }
  document.getElementById('monStop').style.display = 'none';
  document.getElementById('monStatus').textContent = '';
  const b = document.getElementById('monStart');
  b.disabled = false; b.textContent = '🕵️ MONITOR TERUS →';
  document.getElementById('monLive').innerHTML = '';
  showToast('⏹ Monitor stopped');
}
async function monitorRefresh() {
  try {
    const res = await fetch('/api/monitor/status');
    const data = await res.json();
    const st = document.getElementById('monStatus');
    if (!data.running) {
      if (monPoll) { clearInterval(monPoll); monPoll = null; }
      document.getElementById('monStop').style.display = 'none';
      document.getElementById('monLive').innerHTML = '<div style="font-size:.72rem;color:var(--text3)">Monitor berhenti.</div>';
      if (st) st.textContent = '';
      return;
    }
    if (st) st.innerHTML = `<span style="color:var(--green)">🟢 monitoring — check #${data.checks}${data.last_check ? ' · ' + esc(String(data.last_check).slice(11,19)) : ''}</span>`;
    const alerts = data.alerts || [];
    const live = document.getElementById('monLive');
    if (!alerts.length) {
      live.innerHTML = '<div style="font-size:.72rem;color:var(--text3)">Belum ada aktivitas baru.</div>';
      return;
    }
    live.innerHTML = alerts.slice().reverse().map(a => {
      const src = a.platform || a.source || '?';  
      return `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:.78rem">
        <span style="color:var(--orange)">🔔</span> <span style="font-weight:700;color:var(--violet)">${esc(src)}</span>
        ${a.message ? ` — ${esc(String(a.message).slice(0,110))}` : ''}
        ${a.time ? `<div style="color:var(--text3);font-size:.68rem">${esc(String(a.time).slice(11,19))}</div>` : ''}
      </div>`;
    }).join('');
  } catch(e) {}
}

function buildNik(d) {
  let html = row('NIK', d.nik) + row('Valid', d.valid ? '<span class="ok">YES</span>' : '<span class="bad">NO</span>');
  html += row('Gender', d.gender) + row('Lahir', `${d.birth_date} (umur ${d.age})`);
  html += row('Provinsi', d.province) + row('Kab/Kota', d.kabupaten) + row('Kec kode', d.kec_code) + row('Serial', d.serial);
  if (d.status_active === true) html += row('Status', '<span class="ok">aktif</span>');
  else if (d.status_active === false) html += row('Status', '<span class="bad">tidak aktif</span>');
  if (d.errors && d.errors.length) html += row('Peringatan', d.errors.map(e=>`<span class="tag tag-warning">${esc(e)}</span>`).join(' '));
  const ld = d.localdb || {};
  const ldbCount = d.localdb_count != null ? d.localdb_count : 0;
  let foundNames = [];
  Object.entries(ld).forEach(([db, rows]) => {
    (rows||[]).slice(0,2).forEach(r => foundNames.push(`${r.name||'?'} [${db}]`));
  });
  html += row('Nama (DB lokal)', foundNames.length ? foundNames.join('<br>') : `- (dicek ${ldbCount} DB)`);
  return html;
}

function buildNkk(d) {
  let html = row('NKK', d.nkk) + row('Valid', d.valid ? '<span class="ok">YES</span>' : '<span class="bad">NO</span>');
  html += row('Terbit', d.issue_date || '—') + row('Provinsi', d.province || '—') + row('Kab/Kota', d.kabupaten || '—');
  html += row('Kec kode', d.kec_code || '—') + row('Serial', d.serial || '—');
  if (d.errors && d.errors.length) html += row('Peringatan', d.errors.map(e=>`<span class="tag tag-warning">${esc(e)}</span>`).join(' '));
  const fam = d.family || {};
  let members = [];
  Object.entries(fam).forEach(([db, rows]) => {
    (rows||[]).forEach(r => members.push(r));
  });
  if (members.length) {
    html += `<div style="margin-top:8px;font-size:.72rem;color:var(--text3)">Anggota keluarga (${members.length}):</div>`;
    members.slice(0,15).forEach(m => {
      html += `<div class="breach-detail"><strong>${esc(m.name||'?')}</strong> · NIK ${esc(m.nik||'?')} · ${esc(m.marital||'?')} · ${esc(m.gender||'?')}`;
      if (m.birth_date) html += `<br>Lahir: ${esc(m.birth_date)}${m.birth_place?' ('+esc(m.birth_place)+')':''}`;
      if (m.occupation) html += ` · ${esc(m.occupation)}`;
      html += '</div>';
    });
    if (members.length > 15) html += `<div style="font-size:.7rem;color:var(--text3)">+${members.length-15} lagi</div>`;
  } else {
    const cnt = d.localdb_count != null ? d.localdb_count : 0;
    html += row('Anggota', `- (dicek ${cnt} DB lokal — tidak ada data NKK)`);
  }
  if (d.status_active === true) html += row('Status', '<span class="ok">aktif (struktural)</span>');
  else if (d.status_active === false) html += row('Status', '<span class="bad">tidak valid</span>');
  html += row('Cek manual', `<a href="https://dukcapil.kemendagri.go.id" target="_blank">dukcapil.kemendagri.go.id</a>`);
  return html;
}

function buildQr(d) {
  let html = row('Method', d.method);
  if (d.error) return row('Error', esc(d.error));
  (d.decoded||[]).forEach(it => {
    html += row('Type', it.type);
    html += row('Data', esc(String(it.raw||'').slice(0,200)));
    if (it.ssid) html += row('WiFi', `SSID=${esc(it.ssid)} pass=${esc(it.password||'')}`);
    if (it.redirect && it.redirect.final) html += row('Final URL', `<a href="${esc(it.redirect.final)}" target="_blank">${esc(it.redirect.final)}</a>`);
  });
  if (!(d.decoded||[]).length) html += row('Hasil', '<span class="bad">tidak ada data terbaca</span>');
  return html;
}

function buildEwallet(d) {
  let html = row('Nomor', d.national) + row('Carrier', d.carrier);
  (d.ewallets||[]).forEach(w => {
    const ok = String(w.status).toLowerCase().includes('terdaftar') || String(w.status).toLowerCase().includes('ada');
    html += row(`[${esc(w.platform)}]`, `<span class="${ok?'ok':'warn'}">${esc(w.name||w.status)}</span>`);
  });
  if (d.verify_guide && d.verify_guide.length) {
    html += `<div style="margin-top:8px;font-size:.72rem;color:var(--text3)">Panduan verifikasi (transfer kecil → cek nama):</div><div style="margin-top:4px">`;
    d.verify_guide.forEach(s => html += `<div style="font-size:.74rem;padding:3px 0;color:var(--text2)">• ${esc(s)}</div>`);
    html += '</div>';
  }
  return html;
}

function buildOnline(d) {
  const exists = d.exists ?? d.account_exists;
  let html = row('Ada', exists ? '<span class="ok">Ya</span>' : '<span class="bad">Tidak</span>');
  html += row('Status', d.status || '—');
  if (d.display_name) html += row('Nama', esc(d.display_name));
  if (d.username) html += row('Username', esc(d.username));
  if (d.wa_link) html += row('WA link', `<a href="${esc(d.wa_link)}" target="_blank">${esc(d.wa_link)}</a>`);
  if (d.url) html += row('Profile', `<a href="${esc(d.url)}" target="_blank">buka</a>`);
  if (d.note) html += row('Catatan', esc(d.note));
  return html;
}

function buildHlr(d) {
  let html = row('Valid', d.valid ? '<span class="ok">Yes</span>' : '<span class="bad">No</span>');
  html += row('Carrier', d.carrier) + row('Line type', d.line_type) + row('Country', d.country);
  html += row('Location', d.location || '—') + row('Live', d.live_status);
  return html;
}

function buildRevemail(d) {
  const rep = d.reputation || {};
  let html = row('Reputasi', rep.reputation || '—');
  const susp = rep.suspicious;
  html += row('Suspicious', susp === true ? '<span class="bad">⚠ ya</span>' : (susp === false ? '<span class="ok">tidak</span>' : '—'));
  html += row('Nama', d.found_name || '—') + row('Telepon', (d.found_phones||[]).join(', ') || '—');
  const wm = d.web_mentions || {};
  if (wm.mentions !== undefined) html += row('Sebutan web', `${wm.mentions} (${wm.engine||'search'})`);
  if (d.reputation_error) html += `<div style="margin-top:6px;font-size:.72rem;color:var(--orange)">⚠ ${esc(d.reputation_error)}</div>`;
  if (d.manual_links && d.manual_links.length) {
    html += `<div style="margin-top:8px;font-size:.72rem;color:var(--text3)">Link cek manual:</div><div style="margin-top:4px">`;
    d.manual_links.forEach(l => html += `<div style="font-size:.74rem;padding:2px 0"><a href="${esc(l.url)}" target="_blank">${esc(l.platform)}</a></div>`);
    html += '</div>';
  }
  return html;
}

function buildGaming(d) {
  const plats = d.platforms || {};
  let html = '';
  Object.entries(plats).forEach(([k, v]) => {
    const label = k.toUpperCase();
    if (v.found) {
      html += row(label, `<span class="ok">${esc(v.display_name || v.current_name || v.username || 'found')}</span>`);
      ['steamID64','user_id','uuid','friends_count','member_since','location'].forEach(f => {
        if (v[f]) html += row('  '+f, esc(String(v[f])));
      });
    } else {
      html += row(label, `<span class="warn">not found${v.error ? ' ('+esc(v.error)+')' : ''}</span>`);
    }
  });
  return html || row('Hasil', '—');
}

function buildSocial(d) {
  let html = '';
  Object.entries(d).forEach(([k, v]) => {
    if (k === 'username' || !v || typeof v !== 'object') return;
    const label = k.toUpperCase();
    if (v.found) {
      html += row(label, `<span class="ok">${esc(v.nickname || v.title || 'found')}</span>`);
      ['followers','following','likes','videos','verified','bio'].forEach(f => {
        if (v[f] !== undefined && v[f] !== null) html += row('  '+f, esc(String(v[f])));
      });
    } else {
      html += row(label, `<span class="warn">${esc(v.error || 'not found')}</span>`);
    }
  });
  return html || row('Hasil', '—');
}

function buildDevice(d) {
  let html = row('Device', d.device_type || '—');
  html += row('Ports', (d.open_ports||[]).join(', ') || '—');
  if (d.services && d.services.length) html += row('Services', d.services.slice(0,10).join(', '));
  if (d.vulns && d.vulns.length) html += row('CVEs', d.vulns.slice(0,5).map(v=>`<span class="tag tag-danger">${esc(v)}</span>`).join(' '));
  if (d.hints && d.hints.length) html += row('Hint', d.hints.slice(0,5).join(', '));
  if (d.links) {
    Object.entries(d.links).forEach(([k,u]) => html += row(k, `<a href="${esc(u)}" target="_blank">${esc(u)}</a>`));
  }
  return html;
}

function buildGeolocate(d) {
  const gps = d.gps || {};
  let html = '';
  if (gps.found) {
    html += row('GPS', `${gps.lat}, ${gps.lon}`);
    if (gps.map_url) html += row('Map', `<a href="${esc(gps.map_url)}" target="_blank">buka peta</a>`);
  } else {
    html += row('GPS', gps.error || 'tidak ada');
  }
  if (d.reverse_search_links && d.reverse_search_links.length) {
    html += `<div style="margin-top:8px;font-size:.72rem;color:var(--text3)">Reverse image search:</div><div style="margin-top:4px">`;
    d.reverse_search_links.forEach(l => html += `<div style="font-size:.74rem;padding:2px 0"><a href="${esc(l.url)}" target="_blank">${esc(l.engine)}</a></div>`);
    html += '</div>';
  }
  if (d.note) html += row('Note', esc(d.note));
  html += row('Tip', esc(d.manual_tip || '—'));
  return html;
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
  // Error bisa di top-level (error_result) ATAU di dalam data.error
  // (create_result dengan data sebagian gagal) — tangani keduanya.
  const dataErr = result?.error || data?.error;
  const hasData = result && !dataErr && Object.keys(data).length > 0;
  const badge = hasData ? '<span class="mod-badge b-found">✓ FOUND</span>' : '<span class="mod-badge b-none">✗ NONE</span>';
  let body = '';
  if (!hasData) body = `<div style="color:var(--red);font-size:.8rem;padding:4px 0">${esc(dataErr||'No data')}</div>`;
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
  if (d.possible_emails?.length) html += row('Email kandidat (tebakan)', d.possible_emails.slice(0,3).join('<br>'));
  if (d.verified_emails?.length) html += row('Email terverifikasi (ada Gravatar)', d.verified_emails.map(e=>`<a href="${esc(e.gravatar)}" target="_blank">${esc(e.email)}</a>`).join('<br>'));
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
  if (d.wayback?.total_archived) html += row('Wayback', `${d.wayback.total_archived} platform punya arsip lama`);
  if (d.note) html += row('Catatan', esc(d.note));
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

  const bi = d.breach_info || {};
  if (bi.has_breaches) {
    html += `<div class="breach-alert" style="margin-top:10px">
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
        <span class="tag tag-danger">${esc((bi.risk_level||'RISK').toUpperCase())}</span>
        <span class="tag tag-warning">Risk Score: ${bi.risk_score||0}/100</span>
        ${bi.sources_found?.length ? `<span class="tag tag-info">${bi.sources_found.length} sumber breach</span>` : ''}
        ${bi.hudson_rock_infections ? `<span class="tag tag-danger">${bi.hudson_rock_infections} infostealer</span>` : ''}
      </div>
      <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${bi.risk_score||0}%"></div></div>
      <p style="margin:6px 0;font-size:.75rem">${esc(bi.message||'Ditemukan dalam breach')}</p>`;
    if (bi.sources_found?.length) {
      html += `<div style="font-size:.72rem;color:var(--text2)">Sumber terverifikasi: ${bi.sources_found.map(s=>`<span class="tag tag-warning">${esc(s)}</span>`).join(' ')}</div>`;
    }
    if (bi.hudson_rock?.length) {
      html += `<details style="margin-top:6px"><summary style="cursor:pointer;color:var(--violet);font-size:.7rem;font-weight:600">📋 ${bi.hudson_rock.length} infeksi infostealer (Hudson Rock)</summary><div style="margin-top:6px">`;
      bi.hudson_rock.forEach(inf => {
        html += `<div class="breach-detail"><strong>${esc(inf.stealer_family||'?')}</strong> — ${esc(inf.date_compromised||'?')}<br>OS: ${esc(inf.os||'?')}${inf.computer_name?' · PC: '+esc(inf.computer_name):''}</div>`;
      });
      html += `</div></details>`;
    }
    if (bi.recommendation) html += `<div class="recommendation-box"><strong>🔒 Rekomendasi:</strong><br>${esc(bi.recommendation)}</div>`;
    if (bi.note) html += `<div style="font-size:.68rem;color:var(--text3);margin-top:6px">ℹ️ ${esc(bi.note)}</div>`;
    html += `</div>`;
  } else {
    html += row('Breach', '<span class="ok">✓ Tidak ditemukan (sumber publik)</span>');
  }
  const dc = bi.domain_context || {};
  if (dc.has_known_breaches) {
    html += `<div style="margin-top:8px;font-size:.72rem;color:var(--text3)">Riwayat breach DOMAIN (${dc.total_breaches||0}) — <em>bukan khusus alamat email ini</em>:</div>`;
    html += `<details style="margin-top:4px"><summary style="cursor:pointer;color:var(--violet);font-size:.7rem;font-weight:600">📋 Lihat riwayat domain</summary><div style="margin-top:6px">`;
    (dc.breaches||[]).forEach(b => {
      html += `<div class="breach-detail"><strong>${esc(b.name)}</strong> (${b.year}) · ${(b.records||0).toLocaleString()} records · ${esc(b.data_types?.join(', ')||'N/A')}</div>`;
    });
    html += `</div></details>`;
  }

  const att = d.attribution || {};
  if (att.display_name || att.real_name || att.github?.profile?.name || att.github?.commits?.length || att.keybase?.full_name || att.platforms_registered?.length || att.gravatar_accounts?.length) {
    html += `<div class="breach-alert" style="margin-top:10px">
      <div style="font-size:.75rem;font-weight:600;color:var(--violet)">👤 ATRIBUSI (kemungkinan pemilik)</div>`;
    if (att.display_name) html += `<div style="font-size:1rem;font-weight:700;margin:4px 0">${esc(att.display_name)} <span style="font-weight:400;font-size:.68rem;color:var(--text3)">(profil Gravatar)</span></div>`;
    if (att.real_name) html += `<div style="font-size:1.05rem;font-weight:700;margin:2px 0;color:var(--green)">${esc(att.real_name)} <span style="font-weight:400;font-size:.68rem;color:var(--text3)">(${esc(att.real_name_source||'sumber publik')})</span></div>`;
    const ghp = att.github?.profile || {};
    if (ghp.name || att.github?.commits?.length) {
      const gb = [];
      if (ghp.name) gb.push(`profil: ${ghp.name}`);
      if (att.github?.commits?.length) gb.push(`${att.github.commits.length} commit atas email ini`);
      html += `<div style="font-size:.72rem">GitHub: <span class="tag tag-info">${esc(gb.join('; '))}</span></div>`;
    }
    if (att.keybase?.full_name) {
      const kb = att.keybase;
      const pr = kb.proofs || [];
      const kbb = [kb.full_name];
      if (pr.length) kbb.push(`${pr.length} proof: ${pr.slice(0,4).map(p=>p.type).join(', ')}`);
      html += `<div style="font-size:.72rem">Keybase: <span class="tag tag-info">${esc(kbb.join(' · '))}</span></div>`;
    }
    if (att.preferred_username) html += `<div style="font-size:.72rem">Username: <span class="tag tag-info">${esc(att.preferred_username)}</span></div>`;
    if (att.location) html += `<div style="font-size:.72rem">📍 ${esc(att.location)}</div>`;
    if (att.about) html += `<div style="font-size:.72rem;color:var(--text2)">💬 ${esc(String(att.about).slice(0,300))}</div>`;
    if (att.gravatar_accounts?.length) {
      html += `<div style="margin-top:6px;font-size:.72rem;font-weight:600">Akun terhubung (Gravatar):</div><div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">`;
      att.gravatar_accounts.slice(0,12).forEach(a => { html += `<a class="pill" href="${esc(a.url)}" target="_blank">${esc(a.domain||'')}/${esc(a.shortname||'')}</a>`; });
      html += `</div>`;
    }
    if (att.platforms_registered?.length) {
      html += `<div style="margin-top:6px;font-size:.72rem;font-weight:600">Email terdaftar di ${att.platforms_registered.length} platform:</div><div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">`;
      att.platforms_registered.slice(0,20).forEach(p => { html += `<span class="tag tag-success">${esc(p)}</span>`; });
      if (att.platforms_registered.length > 20) html += `<span class="tag">+${att.platforms_registered.length-20} more</span>`;
      html += `</div>`;
    }
    if (att.confidence && att.confidence !== 'none') {
      const cc = att.confidence === 'high' ? 'tag-danger' : (att.confidence === 'medium' ? 'tag-warning' : 'tag-info');
      const ev = (att.evidence||[]).length;
      html += `<div style="margin-top:6px"><span class="tag ${cc}">Keyakinan: ${esc(att.confidence)}</span> <span style="font-size:.66rem;color:var(--text3)">(${ev} sinyal terverifikasi)</span></div>`;
    }
    if (att.note) html += `<div style="font-size:.68rem;color:var(--text3);margin-top:6px">⚠️ ${esc(att.note)}</div>`;
    html += `</div>`;
  }
  const reg = d.domain_registrant || {};
  if (reg.has_registrant) {
    const first = (reg.entities||[])[0] || {};
    html += row('Registrant (RDAP)', (first.name||first.org||'—') + (first.email ? ` · ${esc(first.email)}` : ''));
  }
  return html;
}

function buildPhone(d) {
  let html = row('Input', d.input) + row('E.164', d.e164) + row('International', d.international) + row('National', d.national);
  html += row('Country', `${d.country||'?'} (${d.country_iso||'?'})`);
  const provSrc = d.provider_source === 'carrier' ? ' (data carrier)' : d.provider_source === 'prefix' ? ' (perkiraan prefix)' : '';
  html += row('Provider', (d.provider||'Unknown') + provSrc) + row('Type', d.line_type||'Unknown') + row('Location', (d.location||'—') + ' (perkiraan area)');
  html += row('Timezone', (d.timezones||[]).slice(0,2).join(', ')||'—');
  html += row('Mobile', d.is_mobile ? '<span class="ok">Yes</span>' : 'No');
  if (d.whatsapp_link) html += row('WhatsApp', `<a href="${esc(d.whatsapp_link)}" target="_blank">Open chat</a>`);
  if (d.telegram_link) html += row('Telegram', `<a href="${esc(d.telegram_link)}" target="_blank">Open chat</a>`);
  if (d.possible_handles?.length) html += row('Handle kandidat (tebakan)', d.possible_handles.join(', '));
  if (d.verified_handles?.length) html += row('Handle terverifikasi (ada profil ≠ milik nomor)', d.verified_handles.map(h=>`${esc(h.handle)} (${esc(h.platform)})`).join(', '));
  if (d.provider_note) html += row('Catatan', d.provider_note);
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
  if (d.geo_confidence) {
    const gcol = d.geo_confidence === 'high' ? 'ok' : d.geo_confidence === 'medium' ? 'warn' : 'bad';
    html += row('Geo confidence', `<span class="${gcol}">${esc(d.geo_confidence)}</span> (${(d.geo_sources||[]).length} sumber)${d.geo_disagreement ? ' <span class="bad">⚠ sumber beda pendapat</span>' : ''}`);
  }
  if (d.geo_note) html += row('Geo note', esc(d.geo_note));
  html += row('ISP', d.isp||'—') + row('Org', d.org||'—') + row('ASN', d.asn ? `${d.asn} ${d.asn_name||''}` : '—');
  if (d.isp_registered?.name) {
    const ir = d.isp_registered;
    const loc = [ir.city, ir.region].filter(Boolean).join(', ');
    html += row('Kantor ISP', `${esc(ir.name)} — ${esc(loc)} (RDAP ${esc(ir.asn||'')}) <span class="dim">(bukan lokasi IP)</span>`);
  }
  html += row('Reverse DNS', d.reverse_dns||'—');
  if (d.risk_factors?.length) html += row('Indikator risiko', d.risk_factors.slice(0,6).join(', '));
  if (d.risk_note) html += row('Catatan', d.risk_note);
  if (d.shodan?.open_ports?.length) html += row('Port (Shodan)', d.shodan.open_ports.slice(0,10).join(', '));
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
  html += row('Title', esc((d.title||'—').slice(0,200)));
  if (d.description) html += row('Description', esc(d.description.slice(0,300)));
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

/* ── IP LOGGER (web) ── */
let ilPoll = null;
async function ilStart() {
  const redirect = document.getElementById('ilRedirect').value.trim() || null;
  let port = 8080;
  try { port = parseInt(document.getElementById('ilPort').value, 10) || 8080; } catch(e) {}
  const live = document.getElementById('ilLive').checked;
  const pub = document.getElementById('ilPublic').checked;
  const btn = document.getElementById('ilStart');
  btn.disabled = true; btn.textContent = 'STARTING…';
  try {
    const res = await fetch('/api/iplogger/start', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({port, redirect_url: redirect, live, public: pub})
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    const links = data.links || {};
    let lh = `<div style="font-size:.85rem;color:var(--green);font-weight:600">✅ Logger running</div>`;
    if (links.local) lh += `<div style="margin-top:6px">🔗 <b>Lokal:</b> <a href="${esc(links.local)}" target="_blank">${esc(links.local)}</a></div>`;
    if (links.short) {
      lh += `<div style="margin-top:6px;padding:8px 10px;background:var(--violet-soft);border:1px solid var(--violet);border-radius:10px">🔗 <b>Link pendek (kirim ini):</b> <a href="${esc(links.short)}" target="_blank" style="color:var(--green);font-weight:700">${esc(links.short)}</a></div>`;
    }
    if (links.public) lh += `<div style="margin-top:4px">🌐 <b>Publik:</b> <a href="${esc(links.public)}" target="_blank">${esc(links.public)}</a></div>`;
    document.getElementById('ilLinks').innerHTML = lh;
    document.getElementById('ilLinks').style.display = 'block';
    document.getElementById('ilStop').style.display = '';
    btn.disabled = false; btn.textContent = 'RESTART LOGGER →';
    ilPoll = setInterval(ilRefresh, 2000);
    ilRefresh();
    showToast('🎯 IP Logger started');
  } catch(e) {
    btn.disabled = false; btn.textContent = 'START LOGGER →';
    showToast('❌ ' + e.message, true);
  }
}
async function ilStop() {
  await fetch('/api/iplogger/stop', {method: 'POST'});
  if (ilPoll) { clearInterval(ilPoll); ilPoll = null; }
  document.getElementById('ilStop').style.display = 'none';
  document.getElementById('ilLinks').style.display = 'none';
  const b = document.getElementById('ilStart');
  b.disabled = false; b.textContent = 'START LOGGER →';
  document.getElementById('ilHits').innerHTML = '<div style="font-size:.75rem;color:var(--text3)">Logger stopped.</div>';
  showToast('⏹ Logger stopped');
}
async function ilRefresh() {
  try {
    const res = await fetch('/api/iplogger/status');
    const data = await res.json();
    const caps = data.captures || [];
    const visitors = data.visitors || [];
    const vMap = {}; visitors.forEach(v => vMap[v.visitor_id] = v);
    const humans = caps.filter(c => !c.is_bot).length;
    const bots = caps.length - humans;
    if (!caps.length) { document.getElementById('ilHits').innerHTML = '<div style="font-size:.75rem;color:var(--text3)">Belum ada hit — kirim link, tunggu target buka.</div>'; return; }
    const rows = caps.slice().reverse().map(c => {
      const g = c.geo || {};
      const loc = [g.city, g.region, g.country].filter(Boolean).join(' · ') || '—';
      const isp = g.isp ? g.isp : (g.org || g.as_name || '');
      const flags = [];
      if (g.is_proxy) flags.push('VPN/Proxy');
      if (g.is_hosting) flags.push('hosting/datacenter');
      if (g.is_mobile) flags.push('mobile');
      const tag = c.is_bot ? `<span class="tag tag-danger">BOT</span>` : `<span class="tag tag-success">HUMAN</span>`;
      const ts = String(c.timestamp||'').slice(11,19);
      // Movement events for this visitor (after this capture's timestamp)
      const vis = vMap[c.visitor_id];
      const mvs = (vis && vis.movements || []).map(m =>
        `<div style="font-size:.68rem;color:var(--orange);margin-top:2px">📍 Target berpindah — ${esc(m.from||'?')} → ${esc(m.to||'?')} (${esc(String(m.ts||'').slice(11,19))})</div>`
      ).join('');
      const left = (vis && vis.left) ? `<div style="font-size:.68rem;color:var(--text3);margin-top:2px">⏹ menutup halaman</div>` : '';
      const lang = c.accept_language ? `<div style="font-size:.68rem;color:var(--text3)">🌐 language: ${esc(c.accept_language.slice(0,80))}</div>` : '';
      const flagLine = flags.length ? `<div style="font-size:.68rem;color:var(--yellow)">⚠ ${esc(flags.join(' · '))}</div>` : '';
      const mapEmbed = (g.lat && g.lon) ?
        `<div style="margin-top:6px"><iframe loading="lazy" width="100%" height="150" style="border:1px solid var(--border);border-radius:8px" src="https://maps.google.com/maps?q=${g.lat},${g.lon}&z=12&output=embed"></iframe>
         <div style="font-size:.65rem;color:var(--text3);margin-top:2px"><a href="${esc(g.map_url||'')}" target="_blank">buka di Google Maps ↗</a></div></div>` : '';
      return `<div class="breach-detail" style="border-left-color:${c.is_bot?'var(--red)':'var(--green)'}">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <b style="color:var(--green);font-size:.95rem">${esc(c.ip)}</b> ${tag} <span style="font-size:.68rem;color:var(--text3)">${ts}</span>
        </div>
        <div style="font-size:.72rem;color:var(--text2)">🖥️ ${esc(c.device)} · ${esc(c.os)} · ${esc(c.browser)}${c.bot_name?' · 🤖 '+esc(c.bot_name):''}</div>
        <div style="font-size:.72rem">📍 ${esc(loc)}${isp?(' · ISP '+esc(isp)):''}</div>
        ${flagLine}
        ${c.referrer ? `<div style="font-size:.68rem;color:var(--text3)">🔗 referer: ${esc(c.referrer.slice(0,100))}</div>` : ''}
        ${lang}
        ${mvs}${left}
        ${mapEmbed}
      </div>`;
    }).join('');
    const vInfo = visitors.length ? `<div style="font-size:.68rem;color:var(--text3)">${visitors.length} visitor · ${caps.length} hit (${humans} human · ${bots} bot)</div>` : '';
    document.getElementById('ilHits').innerHTML = `<div style="font-size:.72rem;color:var(--text3);margin-bottom:6px">${vInfo || (caps.length+' hit')} · ${new Date().toLocaleTimeString()}</div>${rows}`;
  } catch(e) {}
}

/* ── SETTINGS (.env) ── */
let settingsData = null;
async function openSettings() {
  document.getElementById('settingsOverlay').style.display = 'flex';
  document.getElementById('settingsBody').innerHTML = 'Memuat…';
  try {
    const res = await fetch('/api/settings/get');
    const data = await res.json();
    settingsData = data.keys || {};
    document.getElementById('setEnvFile').textContent = data.env_file || '';
    let html = '';
    Object.entries(settingsData).forEach(([k, meta]) => {
      const val = meta.value ?? '';
      html += `<div class="set-item">
        <label>${esc(k)}</label>
        <div class="set-desc">${esc(meta.desc || '')}</div>
        <input id="set_${esc(k)}" value="${esc(String(val))}" spellcheck="false">
      </div>`;
    });
    document.getElementById('settingsBody').innerHTML = html;
  } catch(e) {
    document.getElementById('settingsBody').innerHTML = `<div style="color:var(--red);font-size:.8rem">Gagal load: ${esc(e.message)}</div>`;
  }
}
function closeSettings() { document.getElementById('settingsOverlay').style.display = 'none'; }
async function saveSettings() {
  const payload = {};
  Object.keys(settingsData || {}).forEach(k => {
    const el = document.getElementById('set_' + k);
    if (el) payload[k] = el.value.trim();
  });
  try {
    const res = await fetch('/api/settings/save', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    showToast('💾 Settings disimpan ke .env');
    closeSettings();
  } catch(e) {
    showToast('❌ ' + e.message, true);
  }
}

document.addEventListener('keydown', function(e){ if (e.key === 'Escape') closeSettings(); });

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


# ─────────────────────────────────────────────────────────────────────────────
#  SETTINGS (.env editor) — dipakai panel ⚙️ di UI
# ─────────────────────────────────────────────────────────────────────────────
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Keys yang boleh diubah dari UI (jangan semua — hanya yang aman & berguna).
_EDITABLE_KEYS = {
    "DORK_PROXY_LIST": "Proxy list Google Dork (pisah koma: http://user:pass@host:8080,http://h2:3128)",
    "DORK_SLEEP": "Jeda antar query dork (detik, 0 = tanpa jeda)",
    "DORK_MAX_RESULTS": "Maks hasil per kategori dork",
    "STEALTH_RANDOM_UA": "Random User-Agent (true/false)",
    "REQUEST_DELAY": "Jeda antar request global (detik)",
}


def _load_env() -> dict:
    """Baca .env sekarang (termasuk yang belum di-load ke Config)."""
    data = {}
    try:
        if _ENV_PATH.exists():
            for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                data[k.strip()] = v.strip()
    except Exception:
        pass
    return data


def _save_env(pairs: dict) -> bool:
    """Update .env: ubah nilai yang ada, tambahkan yang belum. Preserve komentar."""
    try:
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines() if _ENV_PATH.exists() else []
        keys = set(pairs.keys())
        out = []
        written = set()
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in keys:
                    out.append(f"{k}={pairs[k]}")
                    written.add(k)
                    continue
            out.append(line)
        for k in keys - written:
            out.append(f"{k}={pairs[k]}")
        _ENV_PATH.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


@app.route('/api/settings/get')
def api_settings_get():
    env = _load_env()
    current = {}
    for k, desc in _EDITABLE_KEYS.items():
        # nilai live dari Config (lebih baru daripada .env kalau diubah saat runtime)
        val = getattr(Config, k, env.get(k, ""))
        if isinstance(val, (list, tuple)):
            val = ",".join(str(x) for x in val)
        current[k] = {"value": val, "desc": desc}
    return jsonify({"keys": current, "env_file": str(_ENV_PATH)})


@app.route('/api/settings/save', methods=['POST'])
def api_settings_save():
    try:
        body = request.get_json(force=True) or {}
        pairs = {}
        for k, v in body.items():
            if k in _EDITABLE_KEYS:
                pairs[k] = str(v).strip()
        if not pairs:
            return jsonify({'error': 'no editable keys'}), 400
        if not _save_env(pairs):
            return jsonify({'error': 'gagal menulis .env'}), 500
        # Terapkan ke Config runtime supaya langsung aktif tanpa restart.
        # Parse tipe sesuai definisi Config (int/float/bool/str).
        for k, v in pairs.items():
            os.environ[k] = v
            old = getattr(Config, k, None)
            if isinstance(old, bool):
                setattr(Config, k, v.lower() in ("true", "1", "yes"))
            elif isinstance(old, float):
                try:
                    setattr(Config, k, float(v))
                except ValueError:
                    setattr(Config, k, old)
            elif isinstance(old, int):
                try:
                    setattr(Config, k, int(v))
                except ValueError:
                    setattr(Config, k, old)
            elif isinstance(old, list):
                setattr(Config, k, [p.strip() for p in v.split(",") if p.strip()])
            else:
                setattr(Config, k, v)
        return jsonify({'status': 'saved', 'updated': list(pairs.keys())})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health')
def api_health():
    return jsonify({'status': 'ok', 'version': VERSION, 'tool': 'Zqrya', 'timestamp': datetime.now().isoformat()})


# ─────────────────────────────────────────────────────────────────────────────
#  NEW OSINT TOOLS API (10 tools: nik, qr, ewallet, online, hlr, revemail,
#  gaming, social, device, geolocate) + IP Logger (background thread)
# ─────────────────────────────────────────────────────────────────────────────
_IPLOGGER_CTRL = {}

# Continuous target monitor (background thread). Polls monitor_once every
# `interval` seconds; only NEW activity is appended to `alerts` (the monitor
# module keeps its own state file, so repeat checks report no changes).
_MONITOR_CTRL = {"thread": None, "target": None, "type": None,
                 "alerts": [], "last_check": None, "running": False,
                 "error": None, "stop": False, "checks": 0}


@app.route('/api/monitor/start', methods=['POST'])
def api_monitor_start():
    try:
        body = request.get_json(force=True) or {}
        target = (body.get('target') or '').strip()
        if not target:
            return jsonify({'error': 'target required'}), 400
        mtype = (body.get('type') or 'username').strip()
        interval = max(10, int(body.get('interval', 30)))
        if _MONITOR_CTRL.get('running'):
            return jsonify({'error': 'Monitor sudah berjalan untuk ' + str(_MONITOR_CTRL.get('target'))}), 409

        ctrl = _MONITOR_CTRL
        ctrl.update({'target': target, 'type': mtype, 'alerts': [], 'last_check': None,
                     'error': None, 'stop': False, 'running': True, 'checks': 0,
                     'interval': interval})

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                while not ctrl.get('stop'):
                    try:
                        from stalker.modules.realtime_monitor import monitor_once
                        alerts = loop.run_until_complete(monitor_once(target, mtype))
                        for a in (alerts or []):
                            if isinstance(a, dict):
                                a['time'] = datetime.now().isoformat()
                                ctrl['alerts'].append(a)
                    except Exception as e:
                        ctrl['error'] = str(e)
                    ctrl['checks'] += 1
                    ctrl['last_check'] = datetime.now().isoformat()
                    for _ in range(int(interval * 2)):
                        if ctrl.get('stop'):
                            break
                        time.sleep(0.5)
            finally:
                ctrl['running'] = False
                try:
                    loop.close()
                except Exception:
                    pass

        ctrl['thread'] = threading.Thread(target=_run, daemon=True)
        ctrl['thread'].start()
        return jsonify({'status': 'started', 'target': target, 'type': mtype,
                        'interval': interval})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitor/status')
def api_monitor_status():
    ctrl = _MONITOR_CTRL
    return jsonify({
        'running': bool(ctrl.get('running')),
        'target': ctrl.get('target'),
        'type': ctrl.get('type'),
        'interval': ctrl.get('interval'),
        'checks': ctrl.get('checks', 0),
        'last_check': ctrl.get('last_check'),
        'error': ctrl.get('error'),
        'alerts': make_serializable(ctrl.get('alerts', [])),
    })


@app.route('/api/monitor/stop', methods=['POST'])
def api_monitor_stop():
    _MONITOR_CTRL['stop'] = True
    return jsonify({'status': 'stopped'})


async def _run_osint_tool(tool: str, target: str) -> dict:
    """Run one of the new stalker OSINT tools and return its result dict."""
    if tool == 'nik':
        from stalker.modules.nik_lookup import parse_nik, check_active
        r = parse_nik(target)
        try:
            act = await check_active(target)
            r['status_active'] = bool(act.get('likely_active'))
        except Exception:
            r['status_active'] = None
        try:
            from stalker.modules.localdb import search_by_nik, db_count
            hits = search_by_nik(target)
            r['localdb'] = hits
            r['localdb_count'] = db_count()
        except Exception:
            r['localdb'] = {}
        return r
    if tool == 'nkk':
        from stalker.modules.nkk_lookup import parse_nkk, check_active, search_family
        r = parse_nkk(target)
        try:
            act = await check_active(target)
            r['status_active'] = bool(act.get('likely_active'))
        except Exception:
            r['status_active'] = None
        try:
            from stalker.modules.localdb import db_count
            r['family'] = search_family(target)
            r['localdb_count'] = db_count()
        except Exception:
            r['family'] = {}
        return r
    if tool == 'qr':
        from stalker.modules.qr_decoder import decode_and_expand
        return await decode_and_expand(target)
    if tool == 'ewallet':
        from stalker.modules.ewallet_osint import check_ewallets, manual_verify_guide
        r = await check_ewallets(target)
        r['verify_guide'] = manual_verify_guide()
        return r
    if tool == 'online':
        from stalker.modules.status_online import check_status
        return await check_status(target, 'auto')
    if tool == 'hlr':
        from stalker.modules.phone_hlr import hlr_lookup
        return await hlr_lookup(target)
    if tool == 'revemail':
        from stalker.modules.reverse_email import reverse_email_full
        return await reverse_email_full(target)
    if tool == 'gaming':
        from stalker.modules.gaming_osint import gaming_osint
        return await gaming_osint(target)
    if tool == 'social':
        from stalker.modules.social_deep import social_deep
        return await social_deep(target)
    if tool == 'device':
        from stalker.modules.exposed_device import scan_device
        return await scan_device(target)
    if tool == 'geolocate':
        from stalker.modules.visual_geolocation import geolocate_image
        return await geolocate_image(target)
    if tool == 'exif':
        from stalker.pipeline import run_exif_only
        return await run_exif_only(target)
    if tool == 'dork':
        from stalker.pipeline import run_dork_only
        return await run_dork_only(target)
    if tool == 'variants':
        from stalker.modules.username_variants import generate_variants
        return {'username': target, 'variants': generate_variants(target, max_variants=150)}
    if tool == 'darkweb':
        from stalker.modules.dark_web_checker import full_darkweb_check
        qtype = 'email' if ('@' in target and '.' in target.split('@')[-1]) else \
                ('phone' if target.replace('+', '').replace('-', '').replace(' ', '').isdigit() else 'username')
        return await full_darkweb_check(target, qtype)
    if tool == 'leak':
        from stalker.modules.password_leak import check_password_leak, check_from_text
        if ' ' in target or len(target) > 40:
            return await check_from_text(target)
        return await check_password_leak(target)
    if tool == 'reverseip':
        from stalker.modules.ip_intel import reverse_ip_lookup
        return await reverse_ip_lookup(target)
    if tool == 'name':
        from stalker.modules.real_name_detector import (
            process_real_name_input, generate_name_search_queries)
        res = await process_real_name_input(target)
        if not res.get('is_real_name'):
            return {'name': target, 'is_real_name': False}
        queries = await generate_name_search_queries(target)
        res['queries'] = queries
        return res
    if tool == 'monitor':
        from stalker.modules.realtime_monitor import monitor_once
        qtype = 'email' if ('@' in target and '.' in target.split('@')[-1]) else \
                ('phone' if target.replace(' ', '').replace('-', '').replace('+', '').isdigit() else 'username')
        results = await monitor_once(target, qtype)
        return {'target': target, 'type': qtype, 'results': results,
                'note': 'Monitor sekali jalan (web). Mode loop/interval tersedia di CLI: stalker monitor --loop'}
    return {'error': f'Unknown tool: {tool}'}


@app.route('/api/osint', methods=['POST'])
def api_osint():
    try:
        body = request.get_json(force=True)
        tool = (body.get('tool') or '').strip()
        target = (body.get('target') or '').strip()
        if not tool or not target:
            return jsonify({'error': 'tool & target required'}), 400
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_run_osint_tool(tool, target))
        finally:
            loop.close()
        return jsonify({'tool': tool, 'target': target,
                        'result': make_serializable(result),
                        'timestamp': datetime.now().isoformat()})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/iplogger/start', methods=['POST'])
def api_iplogger_start():
    try:
        body = request.get_json(force=True) or {}
        if _IPLOGGER_CTRL.get('logger') and not _IPLOGGER_CTRL.get('stop'):
            return jsonify({'error': 'IP Logger already running'}), 409
        from stalker.modules.ip_logger import start_iplogger_server
        port = int(body.get('port', 8080))
        redirect_url = (body.get('redirect_url') or '').strip() or None
        live = bool(body.get('live', True))
        public = bool(body.get('public', False))
        shorten = bool(body.get('shorten', True))
        ctrl = start_iplogger_server(port=port, redirect_url=redirect_url,
                                     live=live, public_tunnel=public, shorten=shorten)
        # wait until ready (max ~20s for tunnel attempts)
        for _ in range(200):
            if ctrl.get('ready') or ctrl.get('error'):
                break
            time.sleep(0.1)
        _IPLOGGER_CTRL.clear()
        _IPLOGGER_CTRL.update(ctrl)
        if ctrl.get('error'):
            return jsonify({'error': ctrl['error']}), 500
        return jsonify({'status': 'started', 'links': ctrl.get('links') or {}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/iplogger/status')
def api_iplogger_status():
    ctrl = _IPLOGGER_CTRL
    logger = ctrl.get('logger')
    caps = []
    visitors = []
    if logger is not None:
        caps = [dict(c) for c in getattr(logger, 'captures', [])]
        vd = getattr(logger, '_visitors', {})
        for vid, v in vd.items():
            visitors.append({
                'visitor_id': vid,
                'hits': v.get('hits', 0),
                'last_ip': v.get('last_ip'),
                'left': bool(v.get('left')),
                'movements': v.get('movements', []),
                'last_loc': v.get('last_loc'),
            })
    return jsonify({
        'running': bool(logger is not None and not ctrl.get('stop')),
        'links': ctrl.get('links') or {},
        'error': ctrl.get('error'),
        'captures': make_serializable(caps),
        'visitors': make_serializable(visitors),
    })


@app.route('/api/iplogger/stop', methods=['POST'])
def api_iplogger_stop():
    if _IPLOGGER_CTRL.get('logger') is not None:
        _IPLOGGER_CTRL['stop'] = True
    _IPLOGGER_CTRL.clear()
    return jsonify({'status': 'stopped'})


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
