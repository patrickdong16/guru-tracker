"""
季度对比分析模块

Comparison logic (by CUSIP):
- NEW:       current has it, previous doesn't
- INCREASED: both have it, shares increased
- DECREASED: both have it, shares decreased
- UNCHANGED: both have it, shares identical
- SOLD:      previous has it, current doesn't
"""

import os
import glob
import logging
from typing import List, Dict

from scripts.utils import project_path, load_json, save_json

logger = logging.getLogger("guru-tracker.compare")


def compare_quarters(current: List[Dict], previous: List[Dict]) -> Dict:
    """
    Compare two quarters' holdings and generate a change report.

    Returns:
    {
        "new": [...],
        "increased": [...],
        "decreased": [...],
        "unchanged": [...],
        "sold": [...],
        "summary": { counts + totals }
    }
    """
    current_map = {h["cusip"]: h for h in current}
    previous_map = {h["cusip"]: h for h in previous}

    result: Dict[str, list] = {
        "new": [],
        "increased": [],
        "decreased": [],
        "unchanged": [],
        "sold": [],
    }

    # Walk current holdings
    for cusip, curr in current_map.items():
        if cusip not in previous_map:
            result["new"].append({
                **curr,
                "change_type": "NEW",
            })
        else:
            prev = previous_map[cusip]
            share_change = curr["shares"] - prev["shares"]

            if share_change > 0:
                result["increased"].append({
                    **curr,
                    "change_type": "INCREASED",
                    "prev_shares": prev["shares"],
                    "prev_value": prev["value"],
                    "share_change": share_change,
                    "share_change_pct": round(
                        share_change / prev["shares"] * 100, 1
                    ) if prev["shares"] > 0 else 0,
                })
            elif share_change < 0:
                result["decreased"].append({
                    **curr,
                    "change_type": "DECREASED",
                    "prev_shares": prev["shares"],
                    "prev_value": prev["value"],
                    "share_change": share_change,
                    "share_change_pct": round(
                        share_change / prev["shares"] * 100, 1
                    ) if prev["shares"] > 0 else 0,
                })
            else:
                result["unchanged"].append({
                    **curr,
                    "change_type": "UNCHANGED",
                })

    # Find sold positions
    for cusip, prev in previous_map.items():
        if cusip not in current_map:
            result["sold"].append({
                **prev,
                "change_type": "SOLD",
            })

    # Summary
    total_current = sum(h["value"] for h in current)
    total_previous = sum(h["value"] for h in previous)

    result["summary"] = {
        "total_new": len(result["new"]),
        "total_increased": len(result["increased"]),
        "total_decreased": len(result["decreased"]),
        "total_unchanged": len(result["unchanged"]),
        "total_sold": len(result["sold"]),
        "total_value_current": total_current,
        "total_value_previous": total_previous,
        "total_value_change_pct": round(
            (total_current - total_previous) / total_previous * 100, 1
        ) if total_previous > 0 else 0,
    }

    return result


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def compare_all_gurus() -> Dict[str, int]:
    """
    For each guru, compare the two most recent parsed quarters.

    Returns {"compared": n, "errors": n, "skipped": n}
    """
    parsed_dir = project_path("data", "parsed")
    stats = {"compared": 0, "errors": 0, "skipped": 0}

    if not os.path.exists(parsed_dir):
        logger.warning("No parsed data directory: %s", parsed_dir)
        return stats

    for guru_dir in sorted(os.listdir(parsed_dir)):
        guru_path = os.path.join(parsed_dir, guru_dir)
        if not os.path.isdir(guru_path):
            continue

        # Find all period JSON files, sorted by date
        period_files = sorted(glob.glob(os.path.join(guru_path, "*.json")))
        if len(period_files) < 2:
            logger.info("Not enough periods to compare for %s (%d files)", guru_dir, len(period_files))
            stats["skipped"] += 1
            continue

        # Compare the latest two
        current_file = period_files[-1]
        previous_file = period_files[-2]

        current_period = os.path.basename(current_file).replace(".json", "")
        previous_period = os.path.basename(previous_file).replace(".json", "")

        compared_path = project_path(
            "data", "compared", guru_dir,
            f"{current_period}_vs_{previous_period}.json",
        )

        if os.path.exists(compared_path):
            stats["skipped"] += 1
            continue

        try:
            current_data = load_json(current_file)
            previous_data = load_json(previous_file)

            comparison = compare_quarters(
                current_data.get("holdings", []),
                previous_data.get("holdings", []),
            )

            output = {
                "guru_id": guru_dir,
                "current_period": current_period,
                "previous_period": previous_period,
                "current_filing_date": current_data.get("filing_date", ""),
                "previous_filing_date": previous_data.get("filing_date", ""),
                "summary": comparison["summary"],
                "changes": {
                    "new": comparison["new"],
                    "increased": comparison["increased"],
                    "decreased": comparison["decreased"],
                    "unchanged": comparison["unchanged"],
                    "sold": comparison["sold"],
                },
            }

            save_json(compared_path, output)
            stats["compared"] += 1

            logger.info(
                "Compared %s: %s vs %s → new=%d, increased=%d, decreased=%d, sold=%d",
                guru_dir, current_period, previous_period,
                comparison["summary"]["total_new"],
                comparison["summary"]["total_increased"],
                comparison["summary"]["total_decreased"],
                comparison["summary"]["total_sold"],
            )

        except Exception as exc:
            logger.error("Error comparing %s: %s", guru_dir, exc)
            stats["errors"] += 1

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from scripts.utils import confirm_environment
    confirm_environment()
    stats = compare_all_gurus()
    print(f"\nCompare complete:")
    print(f"  Compared: {stats['compared']}")
    print(f"  Errors:   {stats['errors']}")
    print(f"  Skipped:  {stats['skipped']}")
