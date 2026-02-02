"""
ARK Invest 每日交易 CSV 抓取模块

Data source: https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_TRADE.csv

CSV columns: FUND, Date, Direction, Ticker, CUSIP, Name, Shares, % of ETF
"""

import os
import csv
import io
import logging
from datetime import datetime, date
from typing import List, Dict

from scripts.utils import fetch_with_retry, project_path, save_json

logger = logging.getLogger("guru-tracker.ark")

ARK_CSV_URL = "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_TRADE.csv"


def fetch_ark_trades() -> List[Dict]:
    """
    Download and parse ARK daily trade CSV.

    Returns list of trade dicts:
    {
        "fund": "ARKK",
        "date": "2025-07-18",
        "direction": "Buy",
        "ticker": "TSLA",
        "cusip": "88160R101",
        "name": "TESLA INC",
        "shares": 150000,
        "pct_of_etf": 1.25
    }
    """
    try:
        response = fetch_with_retry(ARK_CSV_URL)
    except Exception as exc:
        logger.error("Failed to fetch ARK trades: %s", exc)
        return []

    try:
        content = response.text
        reader = csv.DictReader(io.StringIO(content))

        trades: List[Dict] = []
        for row in reader:
            try:
                shares_raw = row.get("Shares", "0").replace(",", "").strip()
                pct_raw = row.get("% of ETF", "0").replace("%", "").strip()

                trade = {
                    "fund": row.get("FUND", "").strip(),
                    "date": row.get("Date", "").strip(),
                    "direction": row.get("Direction", "").strip(),
                    "ticker": row.get("Ticker", "").strip(),
                    "cusip": row.get("CUSIP", "").strip(),
                    "name": row.get("Name", "").strip(),
                    "shares": int(float(shares_raw)) if shares_raw else 0,
                    "pct_of_etf": float(pct_raw) if pct_raw else 0.0,
                }
                trades.append(trade)
            except Exception as exc:
                logger.warning("Error parsing ARK trade row: %s — %s", row, exc)
                continue

        logger.info("Parsed %d ARK trades", len(trades))
        return trades

    except Exception as exc:
        logger.error("Error parsing ARK CSV: %s", exc)
        return []


def save_ark_trades(trades: List[Dict]) -> str:
    """Save ARK trades grouped by date."""
    if not trades:
        return ""

    # Group by date
    by_date: Dict[str, List[Dict]] = {}
    for t in trades:
        d = t.get("date", "unknown")
        by_date.setdefault(d, []).append(t)

    saved_files: List[str] = []
    for trade_date, day_trades in by_date.items():
        # Normalize date format
        try:
            dt = datetime.strptime(trade_date, "%m/%d/%Y")
            date_str = dt.strftime("%Y-%m-%d")
        except ValueError:
            date_str = trade_date.replace("/", "-")

        path = project_path("data", "ark", f"{date_str}.json")
        if not os.path.exists(path):
            save_json(path, {
                "date": date_str,
                "trade_count": len(day_trades),
                "trades": day_trades,
            })
            saved_files.append(date_str)

    logger.info("Saved ARK trades for %d new dates", len(saved_files))
    return ", ".join(saved_files) if saved_files else "(no new dates)"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from scripts.utils import confirm_environment
    confirm_environment()
    trades = fetch_ark_trades()
    if trades:
        result = save_ark_trades(trades)
        print(f"ARK trades saved: {result}")
        print(f"Total trades fetched: {len(trades)}")
    else:
        print("No ARK trades fetched")
