#!/usr/bin/env python3
"""
Guru Tracker — 主入口

串联完整数据管道: fetch → parse → compare

Usage:
    python main.py                 # 全量运行
    python main.py --fetch-only    # 仅抓取
    python main.py --parse-only    # 仅解析
    python main.py --compare-only  # 仅对比
"""

import sys
import argparse
import logging

from scripts.utils import confirm_environment

logger = logging.getLogger("guru-tracker")


def run_fetch() -> dict:
    """Step 1: Fetch latest 13F filings from SEC EDGAR."""
    from scripts.fetch_13f import fetch_all_gurus
    logger.info("=" * 60)
    logger.info("STEP 1: Fetching 13F filings...")
    logger.info("=" * 60)
    results = fetch_all_gurus()
    logger.info(
        "Fetch done: %d new, %d errors, %d skipped",
        len(results["new_filings"]),
        len(results["errors"]),
        len(results["skipped"]),
    )
    return results


def run_parse() -> dict:
    """Step 2: Parse raw XML into structured JSON."""
    from scripts.parse_13f import parse_all_raw
    logger.info("=" * 60)
    logger.info("STEP 2: Parsing 13F XML files...")
    logger.info("=" * 60)
    stats = parse_all_raw()
    logger.info(
        "Parse done: %d parsed, %d errors, %d skipped",
        stats["parsed"], stats["errors"], stats["skipped"],
    )
    return stats


def run_compare() -> dict:
    """Step 3: Compare quarters."""
    from scripts.compare_quarters import compare_all_gurus
    logger.info("=" * 60)
    logger.info("STEP 3: Comparing quarters...")
    logger.info("=" * 60)
    stats = compare_all_gurus()
    logger.info(
        "Compare done: %d compared, %d errors, %d skipped",
        stats["compared"], stats["errors"], stats["skipped"],
    )
    return stats


def main():
    parser = argparse.ArgumentParser(description="Guru Tracker data pipeline")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch data")
    parser.add_argument("--parse-only", action="store_true", help="Only parse data")
    parser.add_argument("--compare-only", action="store_true", help="Only compare quarters")
    args = parser.parse_args()

    confirm_environment()

    if args.fetch_only:
        run_fetch()
    elif args.parse_only:
        run_parse()
    elif args.compare_only:
        run_compare()
    else:
        # Full pipeline
        fetch_results = run_fetch()
        parse_stats = run_parse()
        compare_stats = run_compare()

        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)
        logger.info("  Fetch: %d new filings", len(fetch_results["new_filings"]))
        logger.info("  Parse: %d files parsed", parse_stats["parsed"])
        logger.info("  Compare: %d comparisons", compare_stats["compared"])

        # Return non-zero if there were fetch errors
        if fetch_results["errors"]:
            logger.warning("There were %d fetch errors", len(fetch_results["errors"]))


if __name__ == "__main__":
    main()
