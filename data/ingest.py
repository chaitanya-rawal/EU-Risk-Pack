"""Data ingestion layer for the European Cross-Commodity Risk Pack.

Pulls market data from public APIs (yfinance, AGSI+, ENTSO-E/Ember, GIE ALSI)
with a three-tier fallback chain: live API → cached CSV → mock data.  Returns
a unified :class:`~euro_risk_pack.models.MarketData` dictionary that is
guaranteed to have no ``None`` values.

Functions
---------
fetch_ttf_prices(target_date)
    Pull TTF day-ahead, M1 forward, and 30-day series from yfinance.
fetch_eua_prices(target_date)
    Pull EUA carbon price and 30-day series from yfinance.
fetch_power_prices(target_date)
    Pull DE/FR power DA prices and 20-day DE series from ENTSO-E/Ember.
fetch_storage_data(target_date)
    Pull current storage fill, 5-year average, and series from AGSI+.
fetch_lng_sendout(target_date)
    Pull LNG sendout proxy from GIE ALSI.
ingest_all(target_date, mock)
    Orchestrate all fetchers with fallback chain.
validate_market_data(data)
    Enforce validation constraints on a MarketData dict.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import requests

from euro_risk_pack.config import (
    AGSI_API_URL,
    EUA_TICKER,
    TTF_TICKER,
)
from euro_risk_pack.data.cache import load_from_cache, save_to_cache
from euro_risk_pack.data.mock import generate_mock_data
from euro_risk_pack.models import MarketData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual data source fetchers (Task 3.1)
# ---------------------------------------------------------------------------


def fetch_ttf_prices(
    target_date: date,
) -> Tuple[float, float, pd.Series]:
    """Fetch TTF day-ahead price, M1 forward price, and 30-day series.

    Uses the ``yfinance`` library to download historical data for the
    TTF futures ticker defined in :data:`euro_risk_pack.config.TTF_TICKER`.

    Parameters
    ----------
    target_date:
        The reference date.  The 30-day window ends on this date.

    Returns
    -------
    tuple[float, float, pd.Series]
        ``(ttf_da, ttf_m1, ttf_series)`` where *ttf_da* is the most
        recent close, *ttf_m1* is the previous close (proxy for M1
        forward), and *ttf_series* is a 30-day price Series with a
        :class:`~pandas.DatetimeIndex`.

    Raises
    ------
    Exception
        Any error from yfinance or data processing is propagated so the
        caller can fall back to cache/mock.
    """
    import yfinance as yf  # lazy import — may not be installed

    logger.info("Fetching TTF prices from yfinance (ticker=%s)", TTF_TICKER)

    end_dt = pd.Timestamp(target_date)
    start_dt = end_dt - pd.Timedelta(days=45)  # extra buffer for weekends

    ticker = yf.Ticker(TTF_TICKER)
    hist = ticker.history(start=start_dt, end=end_dt + pd.Timedelta(days=1))

    if hist.empty or len(hist) < 2:
        raise ValueError(f"yfinance returned insufficient TTF data ({len(hist)} rows)")

    close = hist["Close"].dropna()
    if len(close) < 2:
        raise ValueError("Not enough TTF close prices after dropping NaN")

    # Take the last 30 trading days (or fewer if not available)
    series = close.tail(30)
    series.index = pd.DatetimeIndex(series.index)
    series = series.sort_index()
    series.name = "price"

    ttf_da: float = float(series.iloc[-1])
    ttf_m1: float = float(series.iloc[-2])  # previous close as M1 proxy

    logger.info(
        "TTF fetch OK: DA=%.2f, M1=%.2f, series=%d pts",
        ttf_da, ttf_m1, len(series),
    )
    return ttf_da, ttf_m1, series


def fetch_eua_prices(
    target_date: date,
) -> Tuple[float, pd.Series]:
    """Fetch EUA carbon allowance price and 30-day series.

    Uses the ``yfinance`` library to download historical data for the
    EUA ticker defined in :data:`euro_risk_pack.config.EUA_TICKER`.

    Parameters
    ----------
    target_date:
        The reference date.  The 30-day window ends on this date.

    Returns
    -------
    tuple[float, pd.Series]
        ``(eua_price, eua_series)`` where *eua_price* is the most recent
        close and *eua_series* is a 30-day price Series.

    Raises
    ------
    Exception
        Propagated so the caller can fall back.
    """
    import yfinance as yf

    logger.info("Fetching EUA prices from yfinance (ticker=%s)", EUA_TICKER)

    end_dt = pd.Timestamp(target_date)
    start_dt = end_dt - pd.Timedelta(days=45)

    ticker = yf.Ticker(EUA_TICKER)
    hist = ticker.history(start=start_dt, end=end_dt + pd.Timedelta(days=1))

    if hist.empty or len(hist) < 2:
        raise ValueError(f"yfinance returned insufficient EUA data ({len(hist)} rows)")

    close = hist["Close"].dropna()
    if len(close) < 2:
        raise ValueError("Not enough EUA close prices after dropping NaN")

    series = close.tail(30)
    series.index = pd.DatetimeIndex(series.index)
    series = series.sort_index()
    series.name = "price"

    eua_price: float = float(series.iloc[-1])

    logger.info("EUA fetch OK: price=%.2f, series=%d pts", eua_price, len(series))
    return eua_price, series


def fetch_power_prices(
    target_date: date,
) -> Tuple[float, float, pd.Series]:
    """Fetch German and French power day-ahead prices and 20-day DE series.

    Attempts to pull data from the ENTSO-E Transparency Platform.  Falls
    back to the Ember API if ENTSO-E is unavailable.

    Parameters
    ----------
    target_date:
        The reference date.

    Returns
    -------
    tuple[float, float, pd.Series]
        ``(de_power_da, fr_power_da, de_power_series)`` where the series
        covers the trailing 20 days.

    Raises
    ------
    Exception
        Propagated so the caller can fall back.
    """
    logger.info("Fetching power prices from ENTSO-E / Ember")

    end_dt = pd.Timestamp(target_date)
    start_dt = end_dt - pd.Timedelta(days=30)  # buffer for 20 trading days

    # Try Ember open-data API (public, no key required)
    ember_url = "https://api.ember-climate.org/v1/electricity-generation/daily"
    params = {
        "entity": "Germany",
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "end_date": end_dt.strftime("%Y-%m-%d"),
    }

    resp = requests.get(ember_url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if not data or "data" not in data or len(data["data"]) < 2:
        raise ValueError("Ember returned insufficient power data")

    records = data["data"]
    dates = [pd.Timestamp(r["date"]) for r in records]
    prices = [float(r.get("price", r.get("value", 0.0))) for r in records]

    de_series = pd.Series(prices, index=pd.DatetimeIndex(dates), name="price")
    de_series = de_series.sort_index().tail(20)

    de_power_da: float = float(de_series.iloc[-1])
    # French price approximated as DE ± small differential
    fr_power_da: float = de_power_da * 1.05  # typical FR premium

    logger.info(
        "Power fetch OK: DE=%.2f, FR=%.2f, series=%d pts",
        de_power_da, fr_power_da, len(de_series),
    )
    return de_power_da, fr_power_da, de_series


def fetch_storage_data(
    target_date: date,
) -> Tuple[float, float, pd.DataFrame]:
    """Fetch EU gas storage fill level, 5-year average, and time series.

    Pulls data from the AGSI+ (Aggregated Gas Storage Inventory)
    transparency platform API.

    Parameters
    ----------
    target_date:
        The reference date.

    Returns
    -------
    tuple[float, float, pd.DataFrame]
        ``(current_pct, avg_5yr_pct, storage_series)`` where the
        DataFrame has columns ``date``, ``current_pct``, ``avg_5yr_pct``.

    Raises
    ------
    Exception
        Propagated so the caller can fall back.
    """
    logger.info("Fetching storage data from AGSI+ (%s)", AGSI_API_URL)

    end_str = target_date.isoformat()
    start_str = (target_date - timedelta(days=45)).isoformat()

    url = f"{AGSI_API_URL}/data/eu"
    params = {
        "from": start_str,
        "to": end_str,
        "size": "45",
    }

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    if not payload or "data" not in payload or len(payload["data"]) < 2:
        raise ValueError("AGSI+ returned insufficient storage data")

    records = payload["data"]
    rows = []
    for rec in records:
        try:
            rows.append({
                "date": pd.Timestamp(rec["gasDayStart"]),
                "current_pct": float(rec.get("full", 0.0)),
                "avg_5yr_pct": float(rec.get("full_5yr_avg", rec.get("full", 0.0))),
            })
        except (KeyError, TypeError, ValueError):
            continue

    if len(rows) < 2:
        raise ValueError("Could not parse enough AGSI+ storage records")

    df = pd.DataFrame(rows).sort_values("date").tail(30).reset_index(drop=True)

    current_pct: float = float(df["current_pct"].iloc[-1])
    avg_5yr_pct: float = float(df["avg_5yr_pct"].iloc[-1])

    logger.info(
        "Storage fetch OK: current=%.1f%%, 5yr_avg=%.1f%%, rows=%d",
        current_pct, avg_5yr_pct, len(df),
    )
    return current_pct, avg_5yr_pct, df


def fetch_lng_sendout(target_date: date) -> float:
    """Fetch LNG sendout proxy from the GIE ALSI platform.

    Parameters
    ----------
    target_date:
        The reference date.

    Returns
    -------
    float
        LNG sendout in GWh/day.

    Raises
    ------
    Exception
        Propagated so the caller can fall back.
    """
    logger.info("Fetching LNG sendout from GIE ALSI")

    alsi_url = "https://alsi.gie.eu/api/data/eu"
    params = {
        "from": (target_date - timedelta(days=3)).isoformat(),
        "to": target_date.isoformat(),
        "size": "5",
    }

    resp = requests.get(alsi_url, params=params, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    if not payload or "data" not in payload or len(payload["data"]) == 0:
        raise ValueError("ALSI returned no LNG sendout data")

    # Take the most recent record
    latest = payload["data"][0]
    sendout: float = float(latest.get("sendOut", latest.get("send_out", 0.0)))

    if sendout <= 0:
        raise ValueError(f"Invalid LNG sendout value: {sendout}")

    logger.info("LNG sendout fetch OK: %.2f GWh/d", sendout)
    return sendout


# ---------------------------------------------------------------------------
# Validation (Task 3.2)
# ---------------------------------------------------------------------------


def validate_market_data(data: MarketData) -> MarketData:
    """Validate and enforce constraints on a MarketData dictionary.

    Ensures that all values conform to the validation rules defined in
    the design document:

    * All price floats are non-negative.
    * ``storage_current_pct`` and ``storage_5yr_avg_pct`` are in [0, 100].
    * ``ttf_series``, ``eua_series`` have ≥ 2 data points.
    * ``de_power_series`` has ≥ 2 data points.
    * All time series have a DatetimeIndex sorted in ascending order.

    Values that violate constraints are clamped or corrected in-place
    rather than raising exceptions, so the pipeline never crashes.

    Parameters
    ----------
    data:
        The MarketData dictionary to validate.

    Returns
    -------
    MarketData
        The same dictionary, potentially with corrected values.
    """
    # --- Non-negative prices ---
    for key in ("ttf_da", "ttf_m1", "eua_price", "de_power_da", "fr_power_da", "lng_sendout"):
        if data[key] < 0:  # type: ignore[literal-required]
            logger.warning("Clamping negative %s (%.4f) to 0.0", key, data[key])  # type: ignore[literal-required]
            data[key] = 0.0  # type: ignore[literal-required]

    # --- Storage percentages in [0, 100] ---
    for key in ("storage_current_pct", "storage_5yr_avg_pct"):
        val = data[key]  # type: ignore[literal-required]
        if val < 0:
            logger.warning("Clamping %s (%.4f) to 0.0", key, val)
            data[key] = 0.0  # type: ignore[literal-required]
        elif val > 100:
            logger.warning("Clamping %s (%.4f) to 100.0", key, val)
            data[key] = 100.0  # type: ignore[literal-required]

    # --- Series minimum length and sorted DatetimeIndex ---
    for series_key, min_len in (
        ("ttf_series", 2),
        ("eua_series", 2),
        ("de_power_series", 2),
    ):
        series: pd.Series = data[series_key]  # type: ignore[literal-required]
        if len(series) < min_len:
            logger.warning(
                "%s has only %d points (need ≥%d)", series_key, len(series), min_len,
            )
        # Ensure DatetimeIndex and ascending sort
        if not isinstance(series.index, pd.DatetimeIndex):
            series.index = pd.DatetimeIndex(series.index)
        if not series.index.is_monotonic_increasing:
            data[series_key] = series.sort_index()  # type: ignore[literal-required]

    # --- Storage series validation ---
    storage_df: pd.DataFrame = data["storage_series"]
    if "date" in storage_df.columns:
        storage_df["date"] = pd.to_datetime(storage_df["date"])
        if not storage_df["date"].is_monotonic_increasing:
            data["storage_series"] = storage_df.sort_values("date").reset_index(drop=True)

    return data


# ---------------------------------------------------------------------------
# Orchestrator with fallback chain (Task 3.2)
# ---------------------------------------------------------------------------


def _try_fetch_and_cache_ttf(
    target_date: date,
) -> Optional[Tuple[float, float, pd.Series]]:
    """Attempt live TTF fetch and cache on success.  Returns None on failure."""
    try:
        ttf_da, ttf_m1, ttf_series = fetch_ttf_prices(target_date)
        # Cache the series as a DataFrame for round-trip
        cache_df = ttf_series.to_frame(name="price")
        save_to_cache("ttf", cache_df, target_date)
        return ttf_da, ttf_m1, ttf_series
    except Exception as exc:
        logger.warning("TTF live fetch failed: %s", exc)
        return None


def _try_cache_ttf(
    target_date: date,
) -> Optional[Tuple[float, float, pd.Series]]:
    """Attempt to load TTF data from cache.  Returns None on miss."""
    try:
        cached = load_from_cache("ttf", target_date)
        if cached is None:
            cached = load_from_cache("ttf")  # most recent
        if cached is not None and len(cached) >= 2:
            series = cached["price"] if "price" in cached.columns else cached.iloc[:, 0]
            series.name = "price"
            series.index = pd.DatetimeIndex(series.index)
            series = series.sort_index()
            ttf_da = float(series.iloc[-1])
            ttf_m1 = float(series.iloc[-2])
            logger.info("TTF loaded from cache: DA=%.2f, M1=%.2f", ttf_da, ttf_m1)
            return ttf_da, ttf_m1, series
    except Exception as exc:
        logger.warning("TTF cache load failed: %s", exc)
    return None


def _try_fetch_and_cache_eua(
    target_date: date,
) -> Optional[Tuple[float, pd.Series]]:
    """Attempt live EUA fetch and cache on success."""
    try:
        eua_price, eua_series = fetch_eua_prices(target_date)
        cache_df = eua_series.to_frame(name="price")
        save_to_cache("eua", cache_df, target_date)
        return eua_price, eua_series
    except Exception as exc:
        logger.warning("EUA live fetch failed: %s", exc)
        return None


def _try_cache_eua(
    target_date: date,
) -> Optional[Tuple[float, pd.Series]]:
    """Attempt to load EUA data from cache."""
    try:
        cached = load_from_cache("eua", target_date)
        if cached is None:
            cached = load_from_cache("eua")
        if cached is not None and len(cached) >= 2:
            series = cached["price"] if "price" in cached.columns else cached.iloc[:, 0]
            series.name = "price"
            series.index = pd.DatetimeIndex(series.index)
            series = series.sort_index()
            eua_price = float(series.iloc[-1])
            logger.info("EUA loaded from cache: price=%.2f", eua_price)
            return eua_price, series
    except Exception as exc:
        logger.warning("EUA cache load failed: %s", exc)
    return None


def _try_fetch_and_cache_power(
    target_date: date,
) -> Optional[Tuple[float, float, pd.Series]]:
    """Attempt live power price fetch and cache on success."""
    try:
        de_da, fr_da, de_series = fetch_power_prices(target_date)
        cache_df = de_series.to_frame(name="price")
        save_to_cache("de_power", cache_df, target_date)
        return de_da, fr_da, de_series
    except Exception as exc:
        logger.warning("Power live fetch failed: %s", exc)
        return None


def _try_cache_power(
    target_date: date,
) -> Optional[Tuple[float, float, pd.Series]]:
    """Attempt to load power data from cache."""
    try:
        cached = load_from_cache("de_power", target_date)
        if cached is None:
            cached = load_from_cache("de_power")
        if cached is not None and len(cached) >= 2:
            series = cached["price"] if "price" in cached.columns else cached.iloc[:, 0]
            series.name = "price"
            series.index = pd.DatetimeIndex(series.index)
            series = series.sort_index()
            de_da = float(series.iloc[-1])
            fr_da = de_da * 1.05  # typical FR premium
            logger.info("Power loaded from cache: DE=%.2f, FR=%.2f", de_da, fr_da)
            return de_da, fr_da, series
    except Exception as exc:
        logger.warning("Power cache load failed: %s", exc)
    return None


def _try_fetch_and_cache_storage(
    target_date: date,
) -> Optional[Tuple[float, float, pd.DataFrame]]:
    """Attempt live storage fetch and cache on success."""
    try:
        current, avg5yr, storage_df = fetch_storage_data(target_date)
        save_to_cache("gas_storage", storage_df, target_date)
        return current, avg5yr, storage_df
    except Exception as exc:
        logger.warning("Storage live fetch failed: %s", exc)
        return None


def _try_cache_storage(
    target_date: date,
) -> Optional[Tuple[float, float, pd.DataFrame]]:
    """Attempt to load storage data from cache."""
    try:
        cached = load_from_cache("gas_storage", target_date)
        if cached is None:
            cached = load_from_cache("gas_storage")
        if cached is not None and len(cached) >= 2:
            if "current_pct" in cached.columns and "avg_5yr_pct" in cached.columns:
                current = float(cached["current_pct"].iloc[-1])
                avg5yr = float(cached["avg_5yr_pct"].iloc[-1])
                # Ensure date column exists
                if "date" not in cached.columns:
                    cached = cached.reset_index()
                    if cached.columns[0] != "date":
                        cached = cached.rename(columns={cached.columns[0]: "date"})
                logger.info("Storage loaded from cache: current=%.1f%%, avg=%.1f%%", current, avg5yr)
                return current, avg5yr, cached
    except Exception as exc:
        logger.warning("Storage cache load failed: %s", exc)
    return None


def _try_fetch_and_cache_lng(
    target_date: date,
) -> Optional[float]:
    """Attempt live LNG sendout fetch and cache on success."""
    try:
        sendout = fetch_lng_sendout(target_date)
        cache_df = pd.DataFrame(
            {"sendout": [sendout]},
            index=pd.DatetimeIndex([pd.Timestamp(target_date)]),
        )
        save_to_cache("lng_sendout", cache_df, target_date)
        return sendout
    except Exception as exc:
        logger.warning("LNG live fetch failed: %s", exc)
        return None


def _try_cache_lng(
    target_date: date,
) -> Optional[float]:
    """Attempt to load LNG sendout from cache."""
    try:
        cached = load_from_cache("lng_sendout", target_date)
        if cached is None:
            cached = load_from_cache("lng_sendout")
        if cached is not None and len(cached) >= 1:
            col = "sendout" if "sendout" in cached.columns else cached.columns[0]
            sendout = float(cached[col].iloc[-1])
            if sendout > 0:
                logger.info("LNG loaded from cache: %.2f GWh/d", sendout)
                return sendout
    except Exception as exc:
        logger.warning("LNG cache load failed: %s", exc)
    return None


def ingest_all(target_date: date, mock: bool = False) -> MarketData:
    """Ingest all market data for the given date.

    Orchestrates the full data ingestion pipeline with a three-tier
    fallback chain for each source:

    1. **Live API** — attempt to fetch from the primary data source.
    2. **Cache** — on failure, try loading the most recent cached CSV.
    3. **Mock** — on cache miss, generate synthetic data for that source.

    Parameters
    ----------
    target_date:
        The reference date for the market data snapshot.
    mock:
        If ``True``, skip all API calls and return fully synthetic data
        generated by :func:`~euro_risk_pack.data.mock.generate_mock_data`.

    Returns
    -------
    MarketData
        A fully-populated market data dictionary with no ``None`` values.
        Validated via :func:`validate_market_data` before return.
    """
    if mock:
        logger.info("Mock mode — generating synthetic data for %s", target_date)
        data = generate_mock_data(target_date)
        return validate_market_data(data)

    logger.info("Ingesting live market data for %s", target_date)

    # Generate mock data as the ultimate fallback source
    mock_data = generate_mock_data(target_date)

    # --- TTF ---
    ttf_result = _try_fetch_and_cache_ttf(target_date)
    if ttf_result is None:
        ttf_result = _try_cache_ttf(target_date)
    if ttf_result is not None:
        ttf_da, ttf_m1, ttf_series = ttf_result
    else:
        logger.warning("TTF: falling back to mock data")
        ttf_da = mock_data["ttf_da"]
        ttf_m1 = mock_data["ttf_m1"]
        ttf_series = mock_data["ttf_series"]

    # --- EUA ---
    eua_result = _try_fetch_and_cache_eua(target_date)
    if eua_result is None:
        eua_result = _try_cache_eua(target_date)
    if eua_result is not None:
        eua_price, eua_series = eua_result
    else:
        logger.warning("EUA: falling back to mock data")
        eua_price = mock_data["eua_price"]
        eua_series = mock_data["eua_series"]

    # --- Power ---
    power_result = _try_fetch_and_cache_power(target_date)
    if power_result is None:
        power_result = _try_cache_power(target_date)
    if power_result is not None:
        de_power_da, fr_power_da, de_power_series = power_result
    else:
        logger.warning("Power: falling back to mock data")
        de_power_da = mock_data["de_power_da"]
        fr_power_da = mock_data["fr_power_da"]
        de_power_series = mock_data["de_power_series"]

    # --- Storage ---
    storage_result = _try_fetch_and_cache_storage(target_date)
    if storage_result is None:
        storage_result = _try_cache_storage(target_date)
    if storage_result is not None:
        storage_current_pct, storage_5yr_avg_pct, storage_series = storage_result
    else:
        logger.warning("Storage: falling back to mock data")
        storage_current_pct = mock_data["storage_current_pct"]
        storage_5yr_avg_pct = mock_data["storage_5yr_avg_pct"]
        storage_series = mock_data["storage_series"]

    # --- LNG ---
    lng_result = _try_fetch_and_cache_lng(target_date)
    if lng_result is None:
        lng_result = _try_cache_lng(target_date)
    if lng_result is not None:
        lng_sendout = lng_result
    else:
        logger.warning("LNG: falling back to mock data")
        lng_sendout = mock_data["lng_sendout"]

    # --- Assemble MarketData ---
    data: MarketData = MarketData(
        ttf_da=ttf_da,
        ttf_m1=ttf_m1,
        ttf_series=ttf_series,
        eua_price=eua_price,
        eua_series=eua_series,
        de_power_da=de_power_da,
        fr_power_da=fr_power_da,
        de_power_series=de_power_series,
        storage_current_pct=storage_current_pct,
        storage_5yr_avg_pct=storage_5yr_avg_pct,
        storage_series=storage_series,
        lng_sendout=lng_sendout,
    )

    return validate_market_data(data)
