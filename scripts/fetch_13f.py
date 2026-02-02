"""
SEC EDGAR 13F 数据抓取模块

Data flow:
1. Read config/gurus.json
2. For each guru, call Submissions API → find latest 13F-HR
3. Compare with local data to detect new filings
4. Download Information Table XML for new filings
5. Save to data/raw/{guru_id}/{period_ending}/infotable.xml

SEC API Rules:
- User-Agent header required (project name + email)
- Rate limit: ≤ 10 requests/second
- No API key needed
"""

import os
import re
import json
import logging
from typing import Optional, Dict, List

from scripts.utils import (
    fetch_with_retry,
    SEC_BASE_URL,
    SEC_ARCHIVES_URL,
    project_path,
    load_json,
    save_json,
)

logger = logging.getLogger("guru-tracker.fetch")

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def get_latest_13f_filings(cik: str, count: int = 2) -> List[Dict]:
    """
    Return the latest *count* 13F-HR filings for a CIK.

    Each item:
    {
        "accession_number": "0000950123-25-008343",
        "filing_date": "2025-08-14",
        "period_ending": "2025-06-30",
        "primary_doc": "primary_doc.xml"
    }
    """
    url = f"{SEC_BASE_URL}/submissions/CIK{cik}.json"
    try:
        response = fetch_with_retry(url)
    except Exception as exc:
        logger.error("Failed to fetch submissions for CIK %s: %s", cik, exc)
        return []

    try:
        data = response.json()
    except Exception as exc:
        logger.error("Invalid JSON from submissions for CIK %s: %s", cik, exc)
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])

    filings: List[Dict] = []
    for i, form in enumerate(forms):
        if form in ("13F-HR", "13F-HR/A"):
            filing = {
                "accession_number": recent["accessionNumber"][i],
                "filing_date": recent["filingDate"][i],
                "period_ending": recent.get("reportDate", [None] * (i + 1))[i],
                "primary_doc": recent["primaryDocument"][i],
                "form": form,
            }
            # Deduplicate by period_ending — keep the latest filing per period
            if not any(f["period_ending"] == filing["period_ending"] for f in filings):
                filings.append(filing)
            if len(filings) >= count:
                break

    return filings


def find_infotable_url(cik: str, accession: str) -> Optional[str]:
    """
    Locate the Information Table XML inside a filing's directory.

    The 13F filing contains two key XMLs:
    - primary_doc.xml — cover page (filer info, signature)
    - *.xml (other) — the actual holdings table

    We look for the XML that is NOT the primary doc.
    """
    accession_clean = accession.replace("-", "")
    cik_int = str(int(cik))  # strip leading zeros
    index_url = f"{SEC_ARCHIVES_URL}/{cik_int}/{accession_clean}/"

    try:
        response = fetch_with_retry(index_url)
    except Exception as exc:
        logger.error("Failed to fetch filing index %s: %s", index_url, exc)
        return None

    # Parse directory listing for XML files
    xml_files = re.findall(r'href="([^"]+\.xml)"', response.text)

    # Also check the filing index JSON for more reliable detection
    index_json_url = f"{SEC_ARCHIVES_URL}/{cik_int}/{accession_clean}/index.json"
    try:
        idx_response = fetch_with_retry(index_json_url)
        idx_data = idx_response.json()
        for item in idx_data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if name.endswith(".xml") and name != "primary_doc.xml":
                desc = item.get("description", "").upper()
                if "INFORMATION TABLE" in desc or "INFOTABLE" in desc or "13F" in desc:
                    return f"{SEC_ARCHIVES_URL}/{cik_int}/{accession_clean}/{name}"
    except Exception:
        pass  # Fall back to regex approach

    # Fallback: pick the first non-primary XML
    for xml_file in xml_files:
        filename = xml_file.split("/")[-1]
        if filename != "primary_doc.xml" and filename.endswith(".xml"):
            return f"{SEC_ARCHIVES_URL}/{cik_int}/{accession_clean}/{filename}"

    logger.warning("No information table XML found for accession %s", accession)
    return None


def download_infotable(guru_id: str, cik: str, filing_info: Dict) -> Optional[str]:
    """Download and save 13F Information Table XML. Returns local path or None."""
    infotable_url = find_infotable_url(cik, filing_info["accession_number"])
    if not infotable_url:
        logger.warning("Could not find infotable URL for %s", guru_id)
        return None

    try:
        response = fetch_with_retry(infotable_url)
    except Exception as exc:
        logger.error("Failed to download infotable for %s: %s", guru_id, exc)
        return None

    period = filing_info["period_ending"] or "unknown"
    save_dir = project_path("data", "raw", guru_id, period)
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, "infotable.xml")

    with open(save_path, "w", encoding="utf-8") as fh:
        fh.write(response.text)

    # Also save filing metadata
    meta_path = os.path.join(save_dir, "meta.json")
    meta = {**filing_info, "infotable_url": infotable_url}
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    logger.info("Saved infotable for %s period %s → %s", guru_id, period, save_path)
    return save_path


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def is_new_filing(guru_id: str, period_ending: str) -> bool:
    """Check if we already have data for this period."""
    raw_path = project_path("data", "raw", guru_id, period_ending, "infotable.xml")
    return not os.path.exists(raw_path)


def fetch_all_gurus() -> Dict[str, List[str]]:
    """
    Fetch latest 13F filings for all gurus.

    Returns: {"new_filings": [...], "errors": [...], "skipped": [...]}
    """
    config = load_json(project_path("config", "gurus.json"))
    results: Dict[str, List[str]] = {"new_filings": [], "errors": [], "skipped": []}

    for guru in config["gurus"]:
        guru_id = guru["id"]
        cik = guru["cik"]
        filing_type = guru.get("filing_type", "13F-HR")

        # Skip non-13F filers
        if filing_type not in ("13F-HR",):
            logger.info("Skipping %s (filing type: %s)", guru_id, filing_type)
            results["skipped"].append(guru_id)
            continue

        logger.info("Fetching filings for %s (CIK: %s)...", guru_id, cik)

        try:
            filings = get_latest_13f_filings(cik, count=2)
            if not filings:
                logger.warning("No 13F filings found for %s", guru_id)
                results["errors"].append(f"{guru_id}: no filings found")
                continue

            for filing in filings:
                period = filing.get("period_ending") or "unknown"
                if is_new_filing(guru_id, period):
                    logger.info("New filing for %s: %s (period %s)", guru_id, filing["accession_number"], period)
                    path = download_infotable(guru_id, cik, filing)
                    if path:
                        results["new_filings"].append(f"{guru_id}/{period}")
                    else:
                        results["errors"].append(f"{guru_id}/{period}: download failed")
                else:
                    logger.debug("Already have %s period %s", guru_id, period)

        except Exception as exc:
            logger.error("Error processing %s: %s", guru_id, exc)
            results["errors"].append(f"{guru_id}: {exc}")

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from scripts.utils import confirm_environment
    confirm_environment()
    results = fetch_all_gurus()

    print(f"\n{'='*60}")
    print(f"Fetch complete:")
    print(f"  New filings downloaded: {len(results['new_filings'])}")
    for f in results["new_filings"]:
        print(f"    ✅ {f}")
    print(f"  Errors: {len(results['errors'])}")
    for e in results["errors"]:
        print(f"    ❌ {e}")
    print(f"  Skipped (non-13F): {len(results['skipped'])}")
    for s in results["skipped"]:
        print(f"    ⏭️  {s}")
    print(f"{'='*60}")
