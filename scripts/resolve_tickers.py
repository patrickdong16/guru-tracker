#!/usr/bin/env python3
"""
Guru Tracker — CUSIP-to-Ticker resolver via OpenFIGI API

Scans all parsed 13F data, collects unique CUSIPs, and resolves them
to ticker symbols using the OpenFIGI API.

Usage:
    python scripts/resolve_tickers.py          # resolve unmapped only
    python scripts/resolve_tickers.py --all    # re-resolve everything
"""

import os
import sys
import json
import glob
import time
import logging
import argparse
from typing import Dict, List, Optional, Set

import requests

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("resolve-tickers")

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
BATCH_SIZE = 10  # max per request (unauthenticated)
REQUEST_DELAY = 0.2  # seconds between requests; backs off on 429
MAPPING_PATH = os.path.join(PROJECT_ROOT, "config", "cusip_tickers.json")
TIMEOUT = 15


def collect_all_cusips() -> Set[str]:
    """Collect all unique CUSIPs from parsed data."""
    cusips = set()
    parsed_dir = os.path.join(PROJECT_ROOT, "data", "parsed")
    for filepath in glob.glob(os.path.join(parsed_dir, "*", "*.json")):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            for h in data.get("holdings", []):
                cusip = h.get("cusip", "").strip()
                if cusip:
                    cusips.add(cusip)
        except Exception as e:
            logger.warning("Failed to read %s: %s", filepath, e)
    return cusips


def load_existing_mapping() -> Dict[str, Optional[str]]:
    """Load existing CUSIP-to-ticker mapping."""
    if os.path.exists(MAPPING_PATH):
        try:
            with open(MAPPING_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load existing mapping: %s", e)
    return {}


def save_mapping(mapping: Dict[str, Optional[str]]):
    """Save CUSIP-to-ticker mapping to disk."""
    os.makedirs(os.path.dirname(MAPPING_PATH), exist_ok=True)
    with open(MAPPING_PATH, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)
    logger.info("Saved mapping with %d entries to %s", len(mapping), MAPPING_PATH)


def resolve_batch(cusips: List[str]) -> Dict[str, Optional[str]]:
    """Resolve a batch of CUSIPs (max 10) via OpenFIGI API.

    Returns dict of cusip -> ticker (or None if not resolved).
    """
    body = [{"idType": "ID_CUSIP", "idValue": c} for c in cusips]

    try:
        resp = requests.post(
            OPENFIGI_URL,
            json=body,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )

        if resp.status_code == 429:
            # Exponential backoff on rate limit
            for wait in (12, 20, 40, 60):
                logger.warning("Rate limited (429). Waiting %ds...", wait)
                time.sleep(wait)
                resp = requests.post(
                    OPENFIGI_URL,
                    json=body,
                    headers={"Content-Type": "application/json"},
                    timeout=TIMEOUT,
                )
                if resp.status_code != 429:
                    break
            else:
                logger.error("Still rate limited after backoff. Marking batch as null.")
                return {c: None for c in cusips}

        if resp.status_code != 200:
            logger.error("OpenFIGI returned %d: %s", resp.status_code, resp.text[:200])
            return {c: None for c in cusips}

        results = resp.json()
        mapping = {}
        for cusip, result in zip(cusips, results):
            if "data" in result and result["data"]:
                # Pick the first result with a ticker
                # Prefer US exchange tickers
                ticker = None
                for item in result["data"]:
                    t = item.get("ticker")
                    if t:
                        # Prefer items with exchCode that looks like US exchange
                        exch = item.get("exchCode", "")
                        if exch in ("US", "UW", "UN", "UA", "UP", "UR", "UQ"):
                            ticker = t
                            break
                        if ticker is None:
                            ticker = t
                mapping[cusip] = ticker
            else:
                mapping[cusip] = None

        return mapping

    except requests.exceptions.Timeout:
        logger.error("Request timed out for batch starting with %s", cusips[0])
        return {c: None for c in cusips}
    except Exception as e:
        logger.error("Request failed: %s", e)
        return {c: None for c in cusips}


def main():
    parser = argparse.ArgumentParser(description="Resolve CUSIPs to ticker symbols")
    parser.add_argument("--all", action="store_true", help="Re-resolve all CUSIPs")
    args = parser.parse_args()

    # Collect all CUSIPs
    all_cusips = collect_all_cusips()
    logger.info("Found %d unique CUSIPs in parsed data", len(all_cusips))

    # Load existing mapping
    existing = load_existing_mapping()
    logger.info("Existing mapping has %d entries", len(existing))

    # Determine which CUSIPs need resolving
    if args.all:
        to_resolve = sorted(all_cusips)
        logger.info("Re-resolving ALL %d CUSIPs (--all flag)", len(to_resolve))
    else:
        to_resolve = sorted(all_cusips - set(existing.keys()))
        logger.info("Need to resolve %d new CUSIPs", len(to_resolve))

    if not to_resolve:
        logger.info("Nothing to resolve. All CUSIPs already mapped.")
        # Still save to ensure file exists and is clean
        # Remove stale entries not in current data
        cleaned = {k: v for k, v in existing.items() if k in all_cusips}
        if len(cleaned) != len(existing):
            logger.info("Cleaned %d stale entries", len(existing) - len(cleaned))
            save_mapping(cleaned)
        return

    # Start with existing mapping
    mapping = dict(existing)

    # Process in batches
    total_batches = (len(to_resolve) + BATCH_SIZE - 1) // BATCH_SIZE
    resolved_count = 0
    null_count = 0

    for i in range(0, len(to_resolve), BATCH_SIZE):
        batch = to_resolve[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        logger.info(
            "Batch %d/%d: resolving %d CUSIPs (%s ...)",
            batch_num,
            total_batches,
            len(batch),
            batch[0],
        )

        result = resolve_batch(batch)
        mapping.update(result)

        for cusip, ticker in result.items():
            if ticker:
                resolved_count += 1
            else:
                null_count += 1

        # Save periodically (every 10 batches)
        if batch_num % 10 == 0:
            save_mapping(mapping)
            logger.info(
                "Progress: %d/%d resolved, %d null so far",
                resolved_count,
                resolved_count + null_count,
                null_count,
            )

        # Rate limit (skip delay on last batch)
        if i + BATCH_SIZE < len(to_resolve):
            time.sleep(REQUEST_DELAY)

    # Final save
    save_mapping(mapping)
    logger.info("=" * 50)
    logger.info("DONE: %d resolved, %d unresolvable, %d total in mapping",
                resolved_count, null_count, len(mapping))

    # Show some stats
    non_null = sum(1 for v in mapping.values() if v is not None)
    logger.info("Overall mapping: %d/%d have tickers (%.1f%%)",
                non_null, len(mapping), non_null / len(mapping) * 100 if mapping else 0)


if __name__ == "__main__":
    main()
