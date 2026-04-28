"""Local CSV cache layer for market data.

Stores fetched DataFrames as CSV files in the ``data/cache/`` directory,
keyed by a short identifier and the target date.  Provides fallback reads
when live APIs are unavailable and housekeeping to prevent unbounded growth.

File naming convention::

    {CACHE_DIR}/{key}_{YYYY-MM-DD}.csv

The cache directory is created automatically on the first write if it does
not already exist.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from euro_risk_pack.config import CACHE_DIR

logger = logging.getLogger(__name__)


def _cache_path(key: str, target_date: date) -> Path:
    """Build the canonical cache file path for a key and date.

    Args:
        key: Short identifier for the data source (e.g. ``"ttf_da"``).
        target_date: The date the data corresponds to.

    Returns:
        Absolute-ish :class:`~pathlib.Path` of the form
        ``{CACHE_DIR}/{key}_{YYYY-MM-DD}.csv``.
    """
    filename = f"{key}_{target_date.isoformat()}.csv"
    return CACHE_DIR / filename


def save_to_cache(key: str, data: pd.DataFrame, target_date: date) -> Path:
    """Save a DataFrame to the local CSV cache.

    Creates the cache directory (including parents) if it does not exist.

    Args:
        key: Short identifier for the data source (e.g. ``"ttf_da"``).
        data: The DataFrame to persist.
        target_date: The date the data corresponds to.

    Returns:
        The :class:`~pathlib.Path` of the written CSV file.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(key, target_date)
    data.to_csv(path, index=True)
    logger.info("Cached %s → %s (%d rows)", key, path, len(data))
    return path


def load_from_cache(
    key: str, target_date: Optional[date] = None
) -> Optional[pd.DataFrame]:
    """Load cached data for a given key.

    If *target_date* is provided, looks for an exact match.  Otherwise,
    returns the most recently dated file for that key (determined by the
    date embedded in the filename).

    Args:
        key: Short identifier for the data source.
        target_date: Exact date to look up, or ``None`` for the most recent.

    Returns:
        The cached :class:`~pandas.DataFrame`, or ``None`` if no matching
        file is found.
    """
    if target_date is not None:
        path = _cache_path(key, target_date)
        if path.exists():
            logger.info("Cache hit: %s", path)
            return pd.read_csv(path, index_col=0, parse_dates=True)
        logger.debug("Cache miss: %s", path)
        return None

    # No date specified — find the most recent file for this key.
    if not CACHE_DIR.exists():
        return None

    prefix = f"{key}_"
    candidates = sorted(
        (f for f in CACHE_DIR.iterdir() if f.name.startswith(prefix) and f.suffix == ".csv"),
        key=lambda p: p.name,
        reverse=True,
    )

    if not candidates:
        logger.debug("No cached files found for key '%s'", key)
        return None

    best = candidates[0]
    logger.info("Cache fallback (most recent): %s", best)
    return pd.read_csv(best, index_col=0, parse_dates=True)


def cache_exists(key: str, target_date: date) -> bool:
    """Check whether a cache file exists for the given key and date.

    Args:
        key: Short identifier for the data source.
        target_date: The date to check.

    Returns:
        ``True`` if the file exists on disk, ``False`` otherwise.
    """
    return _cache_path(key, target_date).exists()


def clear_old_cache(days: int = 30) -> int:
    """Remove cache files older than *days* days.

    Age is determined by the file's last-modification time.

    Args:
        days: Maximum age in days.  Files strictly older than this are
            removed.  Defaults to 30.

    Returns:
        The number of files deleted.
    """
    if not CACHE_DIR.exists():
        return 0

    cutoff = time.time() - days * 86_400
    removed = 0

    for path in CACHE_DIR.iterdir():
        if path.suffix != ".csv":
            continue
        if path.stat().st_mtime < cutoff:
            path.unlink()
            logger.info("Removed stale cache file: %s", path)
            removed += 1

    logger.info("Cleared %d old cache file(s) (older than %d days)", removed, days)
    return removed
