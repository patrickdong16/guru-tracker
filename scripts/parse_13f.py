"""
13F Information Table XML 解析模块

Handles:
- Namespace detection (X0201 old vs X0202 new)
- Value unit detection (千美元 vs 美元)
- CUSIP aggregation (multiple managers reporting same stock)
- Weight calculation

XML namespace: http://www.sec.gov/edgar/document/thirteenf/informationtable
"""

import os
import glob
import json
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional

from scripts.utils import project_path, load_json, save_json

logger = logging.getLogger("guru-tracker.parse")

# Known namespaces
NS_VARIANTS = [
    {"ns": "http://www.sec.gov/edgar/document/thirteenf/informationtable"},
]

# ---------------------------------------------------------------------------
# XML Parsing
# ---------------------------------------------------------------------------


def _detect_namespace(root: ET.Element) -> Optional[Dict[str, str]]:
    """Detect the XML namespace from the root element."""
    tag = root.tag
    if "{" in tag:
        ns_uri = tag.split("}")[0].lstrip("{")
        return {"ns": ns_uri}
    # Try known namespaces
    for ns in NS_VARIANTS:
        if root.findall("ns:infoTable", ns):
            return ns
    return None


def _detect_value_multiplier(xml_path: str) -> int:
    """
    Detect whether value is in dollars or thousands of dollars.

    X0202 (2023+): value in dollars (multiplier = 1)
    X0201 (pre-2023): value in thousands (multiplier = 1000)

    Strategy: check meta.json for schema_version, or check filing date.
    """
    meta_path = os.path.join(os.path.dirname(xml_path), "meta.json")
    if os.path.exists(meta_path):
        try:
            meta = load_json(meta_path)
            filing_date = meta.get("filing_date", "")
            # Filings from 2023-10 onwards typically use X0202 (value in dollars)
            if filing_date >= "2023-10":
                return 1
            elif filing_date >= "2023-01":
                # Transitional period — check XML content for hints
                return _detect_from_xml_content(xml_path)
            else:
                return 1000
        except Exception:
            pass

    return _detect_from_xml_content(xml_path)


def _detect_from_xml_content(xml_path: str) -> int:
    """
    Heuristic: if any single holding has value > 10,000,000,000 (10B),
    it's likely already in dollars. If max value < 1,000,000, it's likely
    in thousands.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = _detect_namespace(root)
        if not ns:
            return 1

        values = []
        for entry in root.findall("ns:infoTable", ns):
            val_text = entry.findtext("ns:value", "0", ns)
            try:
                values.append(int(val_text))
            except ValueError:
                continue

        if not values:
            return 1

        max_val = max(values)
        total = sum(values)

        # If total > 1 billion, likely already in dollars
        if total > 1_000_000_000:
            return 1
        # If total < 10 million, likely in thousands
        if total < 10_000_000:
            return 1000

        return 1  # Default to dollars for recent filings
    except Exception:
        return 1


def parse_infotable(xml_path: str) -> List[Dict]:
    """
    Parse 13F Information Table XML, return list of holdings.

    Each holding dict:
    {
        "issuer": "APPLE INC",
        "title": "COM",
        "cusip": "037833100",
        "value": 63200000000,      # in USD
        "shares": 300000000,
        "share_type": "SH",
        "weight": 23.64,
        "discretion": "DFND",
        "sole_voting": 300000000,
        "shared_voting": 0,
        "no_voting": 0
    }
    """
    if not os.path.exists(xml_path):
        logger.error("File not found: %s", xml_path)
        return []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        logger.error("XML parse error in %s: %s", xml_path, exc)
        return []

    ns = _detect_namespace(root)
    if not ns:
        logger.warning("Could not detect namespace in %s, trying without namespace", xml_path)
        ns = {"ns": ""}

    value_multiplier = _detect_value_multiplier(xml_path)
    if value_multiplier != 1:
        logger.info("Value multiplier = %d (likely pre-2023 schema) for %s", value_multiplier, xml_path)

    holdings: List[Dict] = []

    entries = root.findall("ns:infoTable", ns)
    if not entries:
        # Try without namespace
        entries = root.findall("infoTable")
    if not entries:
        # Try with wildcard
        entries = root.findall(".//{http://www.sec.gov/edgar/document/thirteenf/informationtable}infoTable")

    for entry in entries:
        try:
            raw_value = entry.findtext("ns:value", "0", ns)
            if raw_value == "0":
                raw_value = entry.findtext("{http://www.sec.gov/edgar/document/thirteenf/informationtable}value", "0")

            raw_shares = "0"
            shares_elem = entry.find("ns:shrsOrPrnAmt", ns)
            if shares_elem is None:
                shares_elem = entry.find("{http://www.sec.gov/edgar/document/thirteenf/informationtable}shrsOrPrnAmt")
            if shares_elem is not None:
                raw_shares = (
                    shares_elem.findtext("ns:sshPrnamt", "0", ns)
                    or shares_elem.findtext("{http://www.sec.gov/edgar/document/thirteenf/informationtable}sshPrnamt", "0")
                    or "0"
                )
                share_type = (
                    shares_elem.findtext("ns:sshPrnamtType", "SH", ns)
                    or shares_elem.findtext("{http://www.sec.gov/edgar/document/thirteenf/informationtable}sshPrnamtType", "SH")
                    or "SH"
                )
            else:
                share_type = "SH"

            # Voting authority
            vote_elem = entry.find("ns:votingAuthority", ns)
            if vote_elem is None:
                vote_elem = entry.find("{http://www.sec.gov/edgar/document/thirteenf/informationtable}votingAuthority")

            sole_voting = 0
            shared_voting = 0
            no_voting = 0
            if vote_elem is not None:
                sole_text = vote_elem.findtext("ns:Sole", "0", ns) or vote_elem.findtext("{http://www.sec.gov/edgar/document/thirteenf/informationtable}Sole", "0")
                shared_text = vote_elem.findtext("ns:Shared", "0", ns) or vote_elem.findtext("{http://www.sec.gov/edgar/document/thirteenf/informationtable}Shared", "0")
                none_text = vote_elem.findtext("ns:None", "0", ns) or vote_elem.findtext("{http://www.sec.gov/edgar/document/thirteenf/informationtable}None", "0")
                sole_voting = int(sole_text)
                shared_voting = int(shared_text)
                no_voting = int(none_text)

            issuer = (
                entry.findtext("ns:nameOfIssuer", "", ns)
                or entry.findtext("{http://www.sec.gov/edgar/document/thirteenf/informationtable}nameOfIssuer", "")
            ).strip()

            title = (
                entry.findtext("ns:titleOfClass", "", ns)
                or entry.findtext("{http://www.sec.gov/edgar/document/thirteenf/informationtable}titleOfClass", "")
            ).strip()

            cusip = (
                entry.findtext("ns:cusip", "", ns)
                or entry.findtext("{http://www.sec.gov/edgar/document/thirteenf/informationtable}cusip", "")
            ).strip()

            discretion = (
                entry.findtext("ns:investmentDiscretion", "", ns)
                or entry.findtext("{http://www.sec.gov/edgar/document/thirteenf/informationtable}investmentDiscretion", "")
            ).strip()

            holding = {
                "issuer": issuer,
                "title": title,
                "cusip": cusip,
                "value": int(raw_value) * value_multiplier,
                "shares": int(raw_shares),
                "share_type": share_type.strip(),
                "discretion": discretion,
                "sole_voting": sole_voting,
                "shared_voting": shared_voting,
                "no_voting": no_voting,
            }
            holdings.append(holding)
        except Exception as exc:
            logger.warning("Error parsing entry in %s: %s", xml_path, exc)
            continue

    if not holdings:
        logger.warning("No holdings parsed from %s", xml_path)
        return []

    # Aggregate same CUSIP entries
    aggregated = aggregate_by_cusip(holdings)

    # Calculate weights
    total_value = sum(h["value"] for h in aggregated)
    for h in aggregated:
        h["weight"] = round(h["value"] / total_value * 100, 2) if total_value > 0 else 0

    # Sort by value descending
    aggregated.sort(key=lambda x: x["value"], reverse=True)

    logger.info(
        "Parsed %d entries → %d unique holdings (total: $%s) from %s",
        len(holdings), len(aggregated),
        f"{total_value:,.0f}", xml_path,
    )
    return aggregated


def aggregate_by_cusip(holdings: List[Dict]) -> List[Dict]:
    """
    Aggregate holdings by CUSIP.

    Large institutions (e.g. Berkshire) have multiple investment managers,
    each reporting the same stock separately. We sum them up.
    """
    cusip_map: Dict[str, Dict] = {}
    for h in holdings:
        key = h["cusip"]
        if key in cusip_map:
            cusip_map[key]["value"] += h["value"]
            cusip_map[key]["shares"] += h["shares"]
            cusip_map[key]["sole_voting"] += h["sole_voting"]
            cusip_map[key]["shared_voting"] += h["shared_voting"]
            cusip_map[key]["no_voting"] += h["no_voting"]
        else:
            cusip_map[key] = h.copy()
    return list(cusip_map.values())


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def parse_all_raw() -> Dict[str, int]:
    """
    Parse all raw XML files that don't yet have a corresponding parsed JSON.

    Returns {"parsed": n, "errors": n, "skipped": n}
    """
    raw_dir = project_path("data", "raw")
    stats = {"parsed": 0, "errors": 0, "skipped": 0}

    if not os.path.exists(raw_dir):
        logger.warning("No raw data directory: %s", raw_dir)
        return stats

    config = load_json(project_path("config", "gurus.json"))
    guru_map = {g["id"]: g for g in config["gurus"]}

    for guru_dir in sorted(os.listdir(raw_dir)):
        guru_path = os.path.join(raw_dir, guru_dir)
        if not os.path.isdir(guru_path):
            continue

        for period_dir in sorted(os.listdir(guru_path)):
            period_path = os.path.join(guru_path, period_dir)
            if not os.path.isdir(period_path):
                continue

            xml_path = os.path.join(period_path, "infotable.xml")
            parsed_path = project_path("data", "parsed", guru_dir, f"{period_dir}.json")

            if os.path.exists(parsed_path):
                stats["skipped"] += 1
                continue

            if not os.path.exists(xml_path):
                continue

            logger.info("Parsing %s / %s ...", guru_dir, period_dir)
            holdings = parse_infotable(xml_path)

            if not holdings:
                logger.warning("No holdings parsed for %s / %s", guru_dir, period_dir)
                stats["errors"] += 1
                continue

            # Load meta if available
            meta_path = os.path.join(period_path, "meta.json")
            meta = load_json(meta_path) if os.path.exists(meta_path) else {}

            guru_info = guru_map.get(guru_dir, {})
            output = {
                "guru_id": guru_dir,
                "cik": guru_info.get("cik", ""),
                "period_ending": period_dir,
                "filing_date": meta.get("filing_date", ""),
                "accession_number": meta.get("accession_number", ""),
                "total_value": sum(h["value"] for h in holdings),
                "holdings_count": len(holdings),
                "holdings": holdings,
            }

            save_json(parsed_path, output)
            stats["parsed"] += 1

    return stats


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from scripts.utils import confirm_environment
    confirm_environment()
    stats = parse_all_raw()

    print(f"\nParse complete:")
    print(f"  Parsed: {stats['parsed']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Skipped (already done): {stats['skipped']}")
