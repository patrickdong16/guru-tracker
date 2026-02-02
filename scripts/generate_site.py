#!/usr/bin/env python3
"""
Guru Tracker — Static site generator

Reads parsed/compared data and generates:
1. JSON data files for the frontend (site/data/)
2. HTML pages using Jinja2 templates (templates/)

Usage:
    python scripts/generate_site.py
"""

import os
import sys
import json
import glob
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from jinja2 import Environment, FileSystemLoader

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.utils import (
    project_path,
    load_json,
    save_json,
    format_value,
    format_change_pct,
    format_shares,
    confirm_environment,
)

logger = logging.getLogger("guru-tracker.site")

# Max holdings to embed in HTML (keep pages fast)
MAX_HOLDINGS_IN_HTML = 200
MAX_CHANGES_IN_HTML = 100

# Style badge colors (Tailwind classes)
STYLE_COLORS = {
    "value": ("blue", "bg-blue-500/20 text-blue-400 border-blue-500/30"),
    "macro": ("purple", "bg-purple-500/20 text-purple-400 border-purple-500/30"),
    "growth": ("emerald", "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"),
    "quant": ("amber", "bg-amber-500/20 text-amber-400 border-amber-500/30"),
    "activist": ("rose", "bg-rose-500/20 text-rose-400 border-rose-500/30"),
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def get_latest_period(guru_id: str) -> Optional[str]:
    """Get the latest period for a guru from parsed data."""
    parsed_dir = project_path("data", "parsed", guru_id)
    if not os.path.isdir(parsed_dir):
        return None
    periods = sorted(glob.glob(os.path.join(parsed_dir, "*.json")))
    if not periods:
        return None
    return os.path.basename(periods[-1]).replace(".json", "")


def get_latest_comparison(guru_id: str) -> Optional[dict]:
    """Get the latest comparison for a guru."""
    compared_dir = project_path("data", "compared", guru_id)
    if not os.path.isdir(compared_dir):
        return None
    files = sorted(glob.glob(os.path.join(compared_dir, "*.json")))
    if not files:
        return None
    return load_json(files[-1])


def get_all_periods(guru_id: str) -> List[str]:
    """Get all available periods for a guru."""
    parsed_dir = project_path("data", "parsed", guru_id)
    if not os.path.isdir(parsed_dir):
        return []
    files = sorted(glob.glob(os.path.join(parsed_dir, "*.json")))
    return [os.path.basename(f).replace(".json", "") for f in files]


# ---------------------------------------------------------------------------
# JSON generation
# ---------------------------------------------------------------------------


def generate_gurus_json(config: dict) -> dict:
    """Generate the guru list JSON for the frontend."""
    gurus = []
    for guru in config["gurus"]:
        guru_id = guru["id"]
        latest_period = get_latest_period(guru_id)

        guru_data = {
            "id": guru_id,
            "display_name": guru["display_name"],
            "name": guru["name"],
            "style": guru["style"],
            "style_label": guru["style_label"],
            "aum": guru["aum"],
            "representative": guru["representative"],
            "bio": guru["bio"],
            "famous_trade": guru.get("famous_trade", ""),
            "cik": guru["cik"],
            "filing_type": guru.get("filing_type", "13F-HR"),
            "active": guru.get("active", True),
            "has_data": False,
        }

        if latest_period:
            parsed_path = project_path("data", "parsed", guru_id, f"{latest_period}.json")
            if os.path.exists(parsed_path):
                parsed = load_json(parsed_path)
                guru_data["has_data"] = True
                guru_data["latest_period"] = latest_period
                guru_data["latest_filing_date"] = parsed.get("filing_date", "")
                guru_data["total_value"] = parsed.get("total_value", 0)
                guru_data["holdings_count"] = parsed.get("holdings_count", 0)

            comparison = get_latest_comparison(guru_id)
            if comparison:
                guru_data["summary"] = comparison.get("summary", {})

        gurus.append(guru_data)

    # Sort: gurus with data first, then by filing date desc (most recently updated first),
    # then by total value desc as tiebreaker
    gurus.sort(key=lambda g: (
        not g["has_data"],
        -(datetime.strptime(g["latest_filing_date"], "%Y-%m-%d").timestamp()
          if g.get("latest_filing_date") else 0),
        -(g.get("total_value", 0)),
    ))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "generated_at": now,
        "guru_count": len(gurus),
        "gurus_with_data": sum(1 for g in gurus if g["has_data"]),
        "gurus": gurus,
    }


def generate_guru_detail_json(guru_config: dict) -> Optional[dict]:
    """Generate detailed JSON for a single guru page."""
    guru_id = guru_config["id"]
    parsed_dir = project_path("data", "parsed", guru_id)

    if not os.path.isdir(parsed_dir):
        return None

    period_files = sorted(glob.glob(os.path.join(parsed_dir, "*.json")))
    if not period_files:
        return None

    latest_parsed = load_json(period_files[-1])
    comparison = get_latest_comparison(guru_id)

    return {
        "info": {
            "id": guru_config["id"],
            "display_name": guru_config["display_name"],
            "name": guru_config["name"],
            "style": guru_config["style"],
            "style_label": guru_config["style_label"],
            "aum": guru_config["aum"],
            "representative": guru_config["representative"],
            "bio": guru_config["bio"],
            "famous_trade": guru_config.get("famous_trade", ""),
            "cik": guru_config["cik"],
            "filing_type": guru_config.get("filing_type", "13F-HR"),
        },
        "latest_period": latest_parsed.get("period_ending", ""),
        "filing_date": latest_parsed.get("filing_date", ""),
        "total_value": latest_parsed.get("total_value", 0),
        "holdings_count": latest_parsed.get("holdings_count", 0),
        "holdings": latest_parsed.get("holdings", []),
        "comparison": comparison,
        "periods": [os.path.basename(f).replace(".json", "") for f in period_files],
    }


def generate_consensus_json(config: dict) -> dict:
    """Generate cross-guru stock consensus data."""
    stock_map: Dict[str, dict] = {}

    for guru in config["gurus"]:
        guru_id = guru["id"]
        latest_period = get_latest_period(guru_id)
        if not latest_period:
            continue

        parsed_path = project_path("data", "parsed", guru_id, f"{latest_period}.json")
        if not os.path.exists(parsed_path):
            continue

        parsed = load_json(parsed_path)
        for h in parsed.get("holdings", []):
            cusip = h["cusip"]
            if cusip not in stock_map:
                stock_map[cusip] = {
                    "cusip": cusip,
                    "issuer": h["issuer"],
                    "title": h.get("title", ""),
                    "gurus": [],
                    "total_value": 0,
                    "weights": [],
                }
            stock_map[cusip]["gurus"].append({
                "id": guru_id,
                "display_name": guru["display_name"],
                "value": h["value"],
                "shares": h["shares"],
                "weight": h.get("weight", 0),
            })
            stock_map[cusip]["total_value"] += h["value"]
            stock_map[cusip]["weights"].append(h.get("weight", 0))

    consensus = []
    for data in stock_map.values():
        consensus.append({
            "cusip": data["cusip"],
            "issuer": data["issuer"],
            "title": data.get("title", ""),
            "guru_count": len(data["gurus"]),
            "gurus": sorted(data["gurus"], key=lambda g: g["value"], reverse=True),
            "total_value": data["total_value"],
            "avg_weight": round(
                sum(data["weights"]) / len(data["weights"]), 2
            ) if data["weights"] else 0,
        })

    consensus.sort(key=lambda x: (-x["guru_count"], -x["total_value"]))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "generated_at": now,
        "total_stocks": len(consensus),
        "stocks": consensus,
    }


def generate_json_data() -> tuple:
    """Generate all JSON data files. Returns (gurus_data, consensus_data)."""
    config = load_json(project_path("config", "gurus.json"))

    # 1. Gurus list
    gurus_data = generate_gurus_json(config)
    save_json(project_path("site", "data", "gurus.json"), gurus_data)
    logger.info("Generated gurus.json (%d gurus)", gurus_data["guru_count"])

    # 2. Individual guru details
    guru_data_dir = project_path("site", "data", "guru")
    os.makedirs(guru_data_dir, exist_ok=True)
    count = 0
    for guru in config["gurus"]:
        detail = generate_guru_detail_json(guru)
        if detail:
            save_json(os.path.join(guru_data_dir, f"{guru['id']}.json"), detail)
            count += 1
    logger.info("Generated %d individual guru JSON files", count)

    # 3. Consensus
    consensus_data = generate_consensus_json(config)
    save_json(project_path("site", "data", "consensus.json"), consensus_data)
    logger.info("Generated consensus.json (%d stocks)", consensus_data["total_stocks"])

    return gurus_data, consensus_data


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def setup_jinja_env() -> Environment:
    """Create and configure Jinja2 environment."""
    template_dir = project_path("templates")
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=False,  # We control HTML output; allows embedding JSON safely
    )

    # Custom filters
    env.filters["format_value"] = format_value
    env.filters["format_shares"] = format_shares
    env.filters["format_pct"] = format_change_pct
    env.filters["to_json"] = lambda v: json.dumps(v, ensure_ascii=False)
    env.filters["style_badge"] = lambda style: STYLE_COLORS.get(style, ("zinc", "bg-zinc-500/20 text-zinc-400 border-zinc-500/30"))[1]

    def period_to_quarter(period_str: str) -> str:
        """Convert '2025-09-30' to 'Q3 2025'."""
        if not period_str:
            return ""
        try:
            dt = datetime.strptime(period_str, "%Y-%m-%d")
            q = (dt.month - 1) // 3 + 1
            return f"Q{q} {dt.year}"
        except ValueError:
            return period_str

    def is_recent_filing(filing_date: str, days: int = 30) -> bool:
        """Check if filing was within the last N days."""
        if not filing_date:
            return False
        try:
            dt = datetime.strptime(filing_date, "%Y-%m-%d")
            return (datetime.now() - dt).days <= days
        except ValueError:
            return False

    env.filters["to_quarter"] = period_to_quarter
    env.globals["is_recent_filing"] = is_recent_filing

    return env


def get_style_list(config: dict) -> List[dict]:
    """Get unique style categories with colors."""
    seen = set()
    styles = []
    for guru in config["gurus"]:
        s = guru["style"]
        if s not in seen:
            seen.add(s)
            color_name, badge_class = STYLE_COLORS.get(
                s, ("zinc", "bg-zinc-500/20 text-zinc-400 border-zinc-500/30")
            )
            styles.append({
                "id": s,
                "label": guru["style_label"],
                "color": color_name,
                "badge": badge_class,
            })
    return styles


def render_html(gurus_data: dict, consensus_data: dict):
    """Render all HTML pages using Jinja2 templates."""
    env = setup_jinja_env()
    config = load_json(project_path("config", "gurus.json"))
    styles = get_style_list(config)
    now = gurus_data["generated_at"]

    # --- Index page ---
    tpl = env.get_template("index.html")
    html = tpl.render(
        gurus=gurus_data["gurus"],
        consensus_top=consensus_data["stocks"][:15],
        generated_at=now,
        styles=styles,
        total_gurus=gurus_data["guru_count"],
        gurus_with_data=gurus_data["gurus_with_data"],
    )
    _write(project_path("site", "index.html"), html)
    logger.info("Rendered index.html")

    # --- Consensus page (limit to stocks held by ≥3 gurus, max 500) ---
    consensus_stocks_html = [
        s for s in consensus_data["stocks"] if s["guru_count"] >= 3
    ][:500]
    tpl = env.get_template("consensus.html")
    html = tpl.render(
        stocks=consensus_stocks_html,
        generated_at=now,
        total_stocks=len(consensus_stocks_html),
        total_all=consensus_data["total_stocks"],
    )
    _write(project_path("site", "consensus.html"), html)
    logger.info("Rendered consensus.html")

    # --- Individual guru pages ---
    tpl = env.get_template("guru.html")
    guru_dir = project_path("site", "guru")
    os.makedirs(guru_dir, exist_ok=True)
    count = 0

    for guru_cfg in config["gurus"]:
        detail_path = project_path("site", "data", "guru", f"{guru_cfg['id']}.json")
        if not os.path.exists(detail_path):
            continue

        detail = load_json(detail_path)
        # Limit holdings for HTML embed
        all_holdings = detail.get("holdings", [])
        html_holdings = all_holdings[:MAX_HOLDINGS_IN_HTML]

        # Limit changes for HTML embed
        comparison = detail.get("comparison")
        html_changes = None
        if comparison and comparison.get("changes"):
            changes = comparison["changes"]
            html_changes = {
                "new": changes.get("new", [])[:MAX_CHANGES_IN_HTML],
                "increased": changes.get("increased", [])[:MAX_CHANGES_IN_HTML],
                "decreased": changes.get("decreased", [])[:MAX_CHANGES_IN_HTML],
                "sold": changes.get("sold", [])[:MAX_CHANGES_IN_HTML],
            }

        html = tpl.render(
            guru=detail,
            holdings=html_holdings,
            total_holdings=len(all_holdings),
            truncated=len(all_holdings) > MAX_HOLDINGS_IN_HTML,
            comparison=comparison,
            changes=html_changes,
            generated_at=now,
            # Top 10 for chart
            top10=all_holdings[:10],
        )
        _write(os.path.join(guru_dir, f"{guru_cfg['id']}.html"), html)
        count += 1

    logger.info("Rendered %d guru detail pages", count)


def _write(path: str, content: str):
    """Write content to file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    confirm_environment()

    logger.info("=" * 60)
    logger.info("GENERATING SITE DATA + HTML")
    logger.info("=" * 60)

    gurus_data, consensus_data = generate_json_data()
    render_html(gurus_data, consensus_data)

    logger.info("=" * 60)
    logger.info("SITE GENERATION COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
