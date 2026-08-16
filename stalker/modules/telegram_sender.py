"""Telegram Bot sender — sends investigation reports via Telegram Bot API."""

from __future__ import annotations
from pathlib import Path
from typing import List
import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


async def send_report_files(
    files: List[Path],
    bot_token: str,
    chat_id: str,
    caption: str = "",
) -> List[str]:
    """Send files via Telegram Bot API using sendDocument.

    Returns list of file_descriptor strings for confirmation display.
    """
    base = TELEGRAM_API.format(token=bot_token, method="sendDocument")
    sent = []

    async with httpx.AsyncClient(timeout=60) as client:
        for filepath in files:
            if not filepath.exists():
                continue
            try:
                with open(filepath, "rb") as f:
                    data = {"chat_id": chat_id}
                    if caption:
                        data["caption"] = caption
                    resp = await client.post(
                        base,
                        data=data,
                        files={"document": (filepath.name, f)},
                    )
                    resp.raise_for_status()
                    sent.append(filepath.name)
            except Exception as e:
                print(f"  [WARN] Telegram send failed for {filepath.name}: {e}")

    return sent


async def send_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Send a text message via Telegram Bot API."""
    url = TELEGRAM_API.format(token=bot_token, method="sendMessage")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            resp.raise_for_status()
            return True
    except Exception as e:
        print(f"  [WARN] Telegram message failed: {e}")
        return False
