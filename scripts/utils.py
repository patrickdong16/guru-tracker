"""
Guru Tracker — 公共工具模块

提供:
- fetch_with_retry: 带重试的 HTTP GET
- 日志配置
- 格式化工具
- 环境确认
"""

import os
import sys
import time
import logging
import requests
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("guru-tracker")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEC_BASE_URL = "https://data.sec.gov"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
USER_AGENT = os.environ.get("SEC_USER_AGENT", "GuruTracker patrickdong@gmail.com")
REQUEST_TIMEOUT = 10   # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2        # base seconds for exponential backoff
RATE_LIMIT_DELAY = 0.12  # ≥100ms between SEC requests (≤10 req/sec)

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------


def fetch_with_retry(url: str, headers: Optional[dict] = None) -> Optional[requests.Response]:
    """
    HTTP GET with timeout + exponential-backoff retry.

    Returns Response on success, raises on exhausted retries.
    """
    if headers is None:
        headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            time.sleep(RATE_LIMIT_DELAY)  # respect SEC rate limit
            return response
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            wait = RETRY_DELAY * (attempt + 1)
            logger.warning(
                "Request failed (attempt %d/%d) %s: %s — retrying in %ds",
                attempt + 1, MAX_RETRIES, url, exc, wait,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)

    # All retries exhausted
    logger.error("All %d retries exhausted for %s", MAX_RETRIES, url)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_value(value: int) -> str:
    """Format dollar value with B/M/K suffix."""
    if value == 0:
        return "$0"
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


def format_change_pct(pct: float) -> str:
    """Format percentage change with sign."""
    if pct > 0:
        return f"+{pct:.1f}%"
    if pct < 0:
        return f"{pct:.1f}%"
    return "0.0%"


def format_shares(shares: int) -> str:
    """Format share count with commas."""
    return f"{shares:,}"


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


def confirm_environment() -> str:
    """Print and return current environment context."""
    data_dir = os.environ.get("DATA_DIR", "data/")
    is_ci = os.environ.get("GITHUB_ACTIONS", "false") == "true"
    env_name = "CI (GitHub Actions)" if is_ci else "Local"
    logger.info("Environment: %s", env_name)
    logger.info("Data directory: %s", data_dir[:50])
    return env_name


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def project_path(*parts: str) -> str:
    """Return an absolute path relative to the project root."""
    return os.path.join(PROJECT_ROOT, *parts)


def load_json(path: str) -> dict:
    """Load and return JSON from *path*."""
    import json
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: str, data, indent: int = 2) -> None:
    """Save *data* as JSON to *path*, creating parent dirs as needed."""
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent, ensure_ascii=False)
    logger.info("Saved %s", path)
