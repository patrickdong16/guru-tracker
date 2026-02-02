#!/usr/bin/env python3
"""
Guru Tracker — Stale filing detector

Checks all active gurus for filings older than 1 year.
If found, marks them inactive in gurus.json and reports.

Usage:
    python scripts/check_stale.py              # Check and report only
    python scripts/check_stale.py --auto-remove  # Also remove stale gurus
"""

import os
import sys
import json
import glob
import argparse
import logging
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger("guru-tracker.stale")

STALE_THRESHOLD_DAYS = 365


def check_stale_gurus(auto_remove: bool = False) -> dict:
    """
    Check all active gurus for stale filings (>1 year old).
    
    Returns:
        dict with 'stale' (list of stale guru info) and 'active' count
    """
    config_path = os.path.join(PROJECT_ROOT, "config", "gurus.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    cutoff = datetime.now() - timedelta(days=STALE_THRESHOLD_DAYS)
    stale_gurus = []
    active_count = 0

    for guru in config["gurus"]:
        if not guru.get("active", True):
            continue
        active_count += 1

        gid = guru["id"]
        parsed_dir = os.path.join(PROJECT_ROOT, "data", "parsed", gid)

        # No data at all
        if not os.path.isdir(parsed_dir):
            stale_gurus.append({
                "id": gid,
                "display_name": guru["display_name"],
                "reason": "no_data",
                "latest_period": None,
            })
            continue

        # Find latest period
        files = sorted(glob.glob(os.path.join(parsed_dir, "*.json")))
        if not files:
            stale_gurus.append({
                "id": gid,
                "display_name": guru["display_name"],
                "reason": "no_data",
                "latest_period": None,
            })
            continue

        latest_file = os.path.basename(files[-1]).replace(".json", "")
        try:
            latest_date = datetime.strptime(latest_file, "%Y-%m-%d")
        except ValueError:
            continue

        if latest_date < cutoff:
            stale_gurus.append({
                "id": gid,
                "display_name": guru["display_name"],
                "reason": "stale",
                "latest_period": latest_file,
                "days_old": (datetime.now() - latest_date).days,
            })

    # Auto-remove if requested
    removed = []
    if auto_remove and stale_gurus:
        stale_ids = {s["id"] for s in stale_gurus}
        config["gurus"] = [g for g in config["gurus"] if g["id"] not in stale_ids]
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        removed = list(stale_ids)
        logger.info("Removed %d stale gurus: %s", len(removed), ", ".join(removed))

    # Report
    if stale_gurus:
        print(f"\n⚠️  STALE GURUS DETECTED ({len(stale_gurus)}):")
        for s in stale_gurus:
            if s["reason"] == "no_data":
                print(f"  ❌ {s['display_name']} — no data files")
            else:
                print(f"  ⚠️  {s['display_name']} — latest: {s['latest_period']} ({s['days_old']} days old)")
        if removed:
            print(f"\n🗑️  Auto-removed: {', '.join(removed)}")
    else:
        print(f"\n✅ All {active_count} active gurus have recent filings (< {STALE_THRESHOLD_DAYS} days)")

    return {
        "stale": stale_gurus,
        "removed": removed,
        "active_count": active_count,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Check for stale guru filings")
    parser.add_argument("--auto-remove", action="store_true",
                        help="Automatically remove stale gurus from config")
    args = parser.parse_args()
    result = check_stale_gurus(auto_remove=args.auto_remove)
    
    # Exit with code 1 if stale gurus found (useful for CI)
    if result["stale"]:
        sys.exit(1)
