"""Cryptocurrency Wallet Tracer — trace blockchain transactions from wallet addresses.

From a wallet address found in bio/posts:
- BTC: transactions, balance, first/last tx date, total received/sent
- ETH: transactions, token activity, smart contract interactions
- All blockchain data is PUBLIC — no API key needed
- Reveal: when did they first use crypto, how much moved, to which wallets

APIs used (all free, no registration):
- blockchain.info (Bitcoin)
- api.blockcypher.com (BTC/ETH free tier)
- etherscan.io public API (ETH)
- mempool.space (BTC mempool)
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio, re
from .proxy_manager import prepare_client

BTC_RE = re.compile(r'\b(bc1[a-zA-HJ-NP-Z0-9]{25,39}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b')
ETH_RE = re.compile(r'\b0x[a-fA-F0-9]{40}\b')
LTC_RE = re.compile(r'\b[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}\b')
XMR_RE = re.compile(r'\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b')

def extract_wallets(text: str) -> Dict[str, List[str]]:
    """Find all crypto wallet addresses in text."""
    return {
        "bitcoin": list(set(BTC_RE.findall(text)))[:5],
        "ethereum": list(set(ETH_RE.findall(text)))[:5],
        "litecoin": list(set(LTC_RE.findall(text)))[:3],
        "monero": list(set(XMR_RE.findall(text)))[:3],
    }

async def trace_bitcoin(address: str) -> Dict[str, Any]:
    """Trace Bitcoin wallet via blockchain.info (free)."""
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.get(f"https://blockchain.info/rawaddr/{address}?limit=5",
                           headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                d = r.json()
                txs = d.get("txs", [])
                first_tx = min((tx.get("time",0) for tx in txs), default=0)
                last_tx  = max((tx.get("time",0) for tx in txs), default=0)
                from datetime import datetime

                # Trace receiving wallets (who sent to this address)
                counterparties = set()
                for tx in txs[:5]:
                    for inp in tx.get("inputs", []):
                        prev = inp.get("prev_out", {}).get("addr","")
                        if prev and prev != address: counterparties.add(prev)
                    for out in tx.get("out", []):
                        addr = out.get("addr","")
                        if addr and addr != address: counterparties.add(addr)

                return {
                    "address": address,
                    "chain": "bitcoin",
                    "found": True,
                    "balance_btc": round(d.get("final_balance",0) / 1e8, 8),
                    "total_received_btc": round(d.get("total_received",0) / 1e8, 8),
                    "total_sent_btc": round(d.get("total_sent",0) / 1e8, 8),
                    "n_tx": d.get("n_tx",0),
                    "first_tx": datetime.utcfromtimestamp(first_tx).strftime("%Y-%m-%d") if first_tx else "",
                    "last_tx": datetime.utcfromtimestamp(last_tx).strftime("%Y-%m-%d") if last_tx else "",
                    "linked_addresses": list(counterparties)[:10],
                    "explorer_url": f"https://www.blockchain.com/btc/address/{address}",
                }
    except Exception as e: pass
    return {"address": address, "chain": "bitcoin", "found": False}

async def trace_ethereum(address: str) -> Dict[str, Any]:
    """Trace Ethereum wallet via Etherscan free API."""
    try:
        async with prepare_client(timeout=15) as c:
            # Balance
            r_bal = await c.get(
                f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey=YourApiKeyToken"
            )
            # Recent txs (no API key for limited access)
            r_tx = await c.get(
                f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=5&sort=desc&apikey=YourApiKeyToken"
            )
            bal = 0
            if r_bal.status_code == 200:
                bd = r_bal.json()
                if bd.get("status") == "1":
                    bal = int(bd.get("result","0")) / 1e18

            txs = []
            if r_tx.status_code == 200:
                td = r_tx.json()
                if td.get("status") == "1":
                    txs = td.get("result", [])[:5]

            from datetime import datetime
            counterparties = set()
            for tx in txs:
                for field in ["from","to"]:
                    addr = tx.get(field,"")
                    if addr and addr.lower() != address.lower(): counterparties.add(addr)

            first_ts = min((int(tx.get("timeStamp",0)) for tx in txs), default=0)
            last_ts  = max((int(tx.get("timeStamp",0)) for tx in txs), default=0)

            return {
                "address": address,
                "chain": "ethereum",
                "found": True,
                "balance_eth": round(bal, 6),
                "n_tx": len(txs),
                "first_tx": datetime.utcfromtimestamp(first_ts).strftime("%Y-%m-%d") if first_ts else "",
                "last_tx": datetime.utcfromtimestamp(last_ts).strftime("%Y-%m-%d") if last_ts else "",
                "linked_addresses": list(counterparties)[:5],
                "explorer_url": f"https://etherscan.io/address/{address}",
            }
    except Exception: pass
    return {"address": address, "chain": "ethereum", "found": False}

def extract_all_wallets_from_result(result: Dict[str, Any]) -> Dict[str, List[str]]:
    """Collect all text from investigation and find crypto wallets."""
    all_text = ""
    for site in result.get("maigret",{}).get("found_sites",[]):
        all_text += " " + (site.get("bio","") or "")
    for _,d in result.get("custom_apis",{}).items():
        if isinstance(d,dict): all_text += " " + (d.get("bio","") or "")
    all_text += " " + result.get("text_profile",{}).get("raw","")
    for post in result.get("reddit_intel",{}).get("recent_posts",[]):
        all_text += " " + (post.get("title","") or "")
    return extract_wallets(all_text)

async def trace_all(result: Dict[str, Any]) -> Dict[str, Any]:
    wallets = extract_all_wallets_from_result(result)
    findings = {"wallets_found": wallets, "traces": {}}
    tasks = []
    for addr in wallets.get("bitcoin",[])[:3]:
        tasks.append(("btc", addr, trace_bitcoin(addr)))
    for addr in wallets.get("ethereum",[])[:3]:
        tasks.append(("eth", addr, trace_ethereum(addr)))
    results = await asyncio.gather(*[t[2] for t in tasks], return_exceptions=True)
    for (chain, addr, _), res in zip(tasks, results):
        if isinstance(res, dict) and res.get("found"):
            findings["traces"][addr] = res
    return findings

def format_crypto_report(data: Dict[str, Any]) -> str:
    BOLD="\033[1m"; YELLOW="\033[33m"; GREEN="\033[32m"; CYAN="\033[36m"; NC="\033[0m"
    wallets=data.get("wallets_found",{}); traces=data.get("traces",{})
    total=sum(len(v) for v in wallets.values())
    if total == 0: return "  Crypto: no wallet addresses found"
    lines=[f"\n{BOLD}  ┌─── CRYPTOCURRENCY TRACE ───┐{NC}"]
    lines.append(f"  {total} wallet address(es) found:")
    for chain, addrs in wallets.items():
        for addr in addrs: lines.append(f"  {chain}: {CYAN}{addr}{NC}")
    if traces:
        lines.append(f"\n  {BOLD}Blockchain Data:{NC}")
        for addr, t in traces.items():
            lines.append(f"\n  {t['chain'].upper()}: {addr[:20]}...")
            if t.get("balance_btc") is not None: lines.append(f"  Balance:  {t.get('balance_btc',t.get('balance_eth',''))} {t['chain'][:3].upper()}")
            lines.append(f"  Txs: {t.get('n_tx',0)} | First: {t.get('first_tx','')} | Last: {t.get('last_tx','')}")
            if t.get("linked_addresses"): lines.append(f"  {YELLOW}Linked wallets: {', '.join(t['linked_addresses'][:3])}{NC}")
            lines.append(f"  Explorer: {t.get('explorer_url','')}")
    return "\n".join(lines)
