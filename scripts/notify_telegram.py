"""
Telegram 推送通知模块

Sends filing update notifications via Telegram Bot API.
"""

import os
import glob
import json
import logging
import requests
from typing import Optional

from scripts.utils import (
    project_path,
    load_json,
    format_value,
    format_change_pct,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
)

logger = logging.getLogger("guru-tracker.telegram")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send a Telegram message. Returns True on success."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set, skipping notification")
        return False

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                f"{TG_API}/sendMessage",
                json={
                    "chat_id": CHAT_ID,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=REQUEST_TIMEOUT,
            )
            if response.ok:
                logger.info("Telegram message sent successfully")
                return True
            else:
                logger.warning("Telegram API error: %s", response.text)
        except Exception as exc:
            logger.warning("Telegram send attempt %d failed: %s", attempt + 1, exc)

    logger.error("All Telegram send attempts exhausted")
    return False


def format_filing_notification(guru_config: dict, comparison: dict, site_url: str) -> str:
    """Format a filing update notification message."""
    summary = comparison.get("summary", {})
    changes = comparison.get("changes", {})

    guru_name = guru_config.get("display_name", guru_config.get("name", "Unknown"))
    current_period = comparison.get("current_period", "")

    total_current = summary.get("total_value_current", 0)
    pct_change = summary.get("total_value_change_pct", 0)

    lines = [
        f"🔔 <b>{guru_name}</b> 持仓更新！",
        "",
        f"📅 报告期：{current_period}",
        f"📊 总持仓：{format_value(total_current)} ({format_change_pct(pct_change)})",
        "",
    ]

    new_positions = changes.get("new", [])
    if new_positions:
        lines.append("🆕 <b>新建仓：</b>")
        for h in new_positions[:5]:
            lines.append(f"  • {h['issuer']} — {format_value(h['value'])} ({h.get('weight', 0):.1f}%)")
        if len(new_positions) > 5:
            lines.append(f"  ... 及其他 {len(new_positions) - 5} 只")

    sold_positions = changes.get("sold", [])
    if sold_positions:
        lines.append("❌ <b>清仓：</b>")
        for h in sold_positions[:5]:
            lines.append(f"  • {h['issuer']}")
        if len(sold_positions) > 5:
            lines.append(f"  ... 及其他 {len(sold_positions) - 5} 只")

    increased = changes.get("increased", [])
    decreased = changes.get("decreased", [])
    if increased:
        lines.append(f"⬆️ 加仓 {len(increased)} 只")
    if decreased:
        lines.append(f"⬇️ 减仓 {len(decreased)} 只")

    guru_id = comparison.get("guru_id", "")
    if site_url and guru_id:
        lines.append(f"\n🔗 <a href='{site_url}/guru/{guru_id}.html'>查看详情</a>")

    return "\n".join(lines)


def notify_new_filings() -> int:
    """
    Check for new comparison files and send notifications.

    Returns count of notifications sent.
    """
    site_url = os.environ.get("SITE_URL", "https://patrickdong16.github.io/guru-tracker")
    config = load_json(project_path("config", "gurus.json"))
    guru_map = {g["id"]: g for g in config["gurus"]}

    compared_dir = project_path("data", "compared")
    if not os.path.exists(compared_dir):
        logger.info("No compared data directory")
        return 0

    sent = 0
    for guru_dir in sorted(os.listdir(compared_dir)):
        guru_path = os.path.join(compared_dir, guru_dir)
        if not os.path.isdir(guru_path):
            continue

        files = sorted(glob.glob(os.path.join(guru_path, "*.json")))
        if not files:
            continue

        latest = files[-1]
        comparison = load_json(latest)

        # Check if this is interesting enough to notify
        summary = comparison.get("summary", {})
        total_changes = (
            summary.get("total_new", 0) +
            summary.get("total_sold", 0) +
            summary.get("total_increased", 0) +
            summary.get("total_decreased", 0)
        )

        if total_changes == 0:
            continue  # No changes, skip

        guru_config = guru_map.get(guru_dir, {"display_name": guru_dir})
        message = format_filing_notification(guru_config, comparison, site_url)

        if send_message(message):
            sent += 1

    return sent


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from scripts.utils import confirm_environment
    confirm_environment()
    count = notify_new_filings()
    print(f"Sent {count} Telegram notification(s)")
