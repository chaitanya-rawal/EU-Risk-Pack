"""Mock data generation for the European Cross-Commodity Risk Pack.

Generates plausible synthetic market data using a date-derived seed so that
the same target date always produces identical output.  Used in ``--mock``
mode and as the last-resort fallback when both live APIs and cached data are
unavailable.

The random walk helper works *backwards* from the base price so that the
final value in each series equals the spot/DA price, giving a coherent
snapshot where the latest observation matches the scalar fields.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from euro_risk_pack.models import MarketData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _random_walk_array(
    rng: np.random.Generator,
    base: float,
    length: int,
    volatility: float,
) -> np.ndarray:
    """Build a raw numpy array random walk ending at *base*.

    Used internally for storage percentage series where we don't need a
    full pandas Series with DatetimeIndex.
    """
    arr = np.empty(length, dtype=np.float64)
    arr[-1] = base
    for i in range(length - 2, -1, -1):
        step = rng.normal(0.0, volatility)
        arr[i] = arr[i + 1] * (1.0 - step)
    return arr


def generate_random_walk(
    rng: np.random.Generator,
    base: float,
    days: int,
    volatility: float,
    target_date: date,
) -> pd.Series:
    """Generate a random-walk price series ending at *base*.

    The series is built backwards from *base* so that the last value is
    exactly the base price.  Each step is a normally-distributed return
    scaled by *volatility*.  All values are clamped to a minimum of 0.01
    to guarantee positivity.

    Parameters
    ----------
    rng:
        A :class:`numpy.random.Generator` instance for reproducibility.
    base:
        The ending price (i.e. the most recent observation).
    days:
        Number of data points in the series.
    volatility:
        Standard deviation of the daily log-return used to generate steps.
    target_date:
        The date corresponding to the last element of the series.  Earlier
        dates are computed by subtracting calendar days.

    Returns
    -------
    pd.Series
        A Series of length *days* with a :class:`~pandas.DatetimeIndex`
        sorted in ascending chronological order.  The last value equals
        *base*.
    """
    # Build prices backwards from the base price
    prices = np.empty(days, dtype=np.float64)
    prices[-1] = base

    for i in range(days - 2, -1, -1):
        step = rng.normal(0.0, volatility)
        prices[i] = prices[i + 1] * (1.0 - step)

    # Clamp to ensure positivity
    prices = np.maximum(prices, 0.01)

    # Restore the exact base as the last value (clamping may have shifted it
    # only if base itself were < 0.01, which our ranges prevent).
    prices[-1] = base

    # Build a DatetimeIndex ending at target_date
    dates = pd.date_range(
        end=pd.Timestamp(target_date),
        periods=days,
        freq="D",
    )

    return pd.Series(prices, index=dates, name="price")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_mock_data(target_date: date) -> MarketData:
    """Generate a complete :class:`MarketData` dict with synthetic values.

    The random seed is derived deterministically from *target_date* as
    ``int(target_date.strftime("%Y%m%d"))``, so calling this function
    twice with the same date always returns identical data.

    Price ranges
    ------------
    * TTF day-ahead / M1 / series: **[28, 35]** EUR/MWh
    * EUA price / series: **[55, 75]** EUR/tCO₂
    * DE/FR power DA / series: **[45, 90]** EUR/MWh
    * Gas storage fill: **[55, 85]** %

    Series lengths
    --------------
    * ``ttf_series``, ``eua_series``: 30 days
    * ``de_power_series``: 20 days
    * ``storage_series``: 30 rows

    Parameters
    ----------
    target_date:
        The reference date for the mock snapshot.

    Returns
    -------
    MarketData
        A fully-populated market data dictionary with no ``None`` values.
    """
    seed = int(target_date.strftime("%Y%m%d"))
    rng = np.random.default_rng(seed)

    # --- Scalar prices ------------------------------------------------
    ttf_da: float = float(rng.uniform(28.0, 35.0))
    ttf_m1: float = float(rng.uniform(28.0, 35.0))
    eua_price: float = float(rng.uniform(55.0, 75.0))
    de_power_da: float = float(rng.uniform(45.0, 90.0))
    fr_power_da: float = float(rng.uniform(45.0, 90.0))
    storage_current_pct: float = float(rng.uniform(55.0, 85.0))
    storage_5yr_avg_pct: float = float(rng.uniform(55.0, 85.0))
    lng_sendout: float = float(rng.uniform(3.0, 12.0))

    # --- Time series --------------------------------------------------
    ttf_series = generate_random_walk(
        rng, base=ttf_da, days=30, volatility=0.02, target_date=target_date,
    )
    eua_series = generate_random_walk(
        rng, base=eua_price, days=30, volatility=0.015, target_date=target_date,
    )
    de_power_series = generate_random_walk(
        rng, base=de_power_da, days=20, volatility=0.03, target_date=target_date,
    )

    # --- Storage series (DataFrame) -----------------------------------
    storage_dates = pd.date_range(
        end=pd.Timestamp(target_date),
        periods=30,
        freq="D",
    )

    # Generate current_pct as a random walk ending at storage_current_pct
    current_pcts = _random_walk_array(rng, storage_current_pct, 30, 0.01)
    current_pcts = np.clip(current_pcts, 0.01, 100.0)
    current_pcts[-1] = storage_current_pct  # restore exact endpoint

    # Generate avg_5yr_pct as a smooth seasonal curve around storage_5yr_avg_pct
    avg_5yr_pcts = _random_walk_array(rng, storage_5yr_avg_pct, 30, 0.005)
    avg_5yr_pcts = np.clip(avg_5yr_pcts, 0.01, 100.0)
    avg_5yr_pcts[-1] = storage_5yr_avg_pct  # restore exact endpoint

    storage_series = pd.DataFrame({
        "date": storage_dates,
        "current_pct": current_pcts,
        "avg_5yr_pct": avg_5yr_pcts,
    })

    return MarketData(
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
