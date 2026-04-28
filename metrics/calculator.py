"""Metrics calculator for the European Cross-Commodity Risk Pack.

Computes all seven monitor metrics from ingested market data.  Each metric
has a defined formula, threshold-based signal classification, and formatted
display string.  The :func:`calculate_all_metrics` orchestrator calls every
individual calculator and returns a complete :class:`MetricsResult`.

Individual calculators:

- :func:`calc_ttf_da_vs_m1_spread` — TTF day-ahead vs M1 forward spread
- :func:`calc_eua_30d_momentum` — 30-day EUA price momentum
- :func:`calc_gas_storage_deficit` — gas storage deficit vs 5-year average
- :func:`calc_dark_spread_de` — German dark spread
- :func:`calc_clean_spark_spread_de` — German clean spark spread
- :func:`calc_ttf_eua_correlation` — TTF-EUA 30-day return correlation
- :func:`calc_power_realised_vol` — 20-day power price realised volatility
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from euro_risk_pack.config import (
    EMISSION_FACTOR,
    GAS_PLANT_EFFICIENCY,
    THRESHOLDS,
)
from euro_risk_pack.models import MarketData, MetricResult, MetricsResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: format a float with explicit sign prefix
# ---------------------------------------------------------------------------


def _format_signed(value: float, decimals: int = 2) -> str:
    """Return a string with explicit ``+`` or ``-`` prefix.

    Examples:
        >>> _format_signed(2.35)
        '+2.35'
        >>> _format_signed(-0.8)
        '-0.80'
        >>> _format_signed(0.0)
        '+0.00'
    """
    return f"{value:+.{decimals}f}"


# ---------------------------------------------------------------------------
# Default (fallback) MetricResult
# ---------------------------------------------------------------------------

_DEFAULT_METRIC: MetricResult = {
    "value": 0.0,
    "signal": "NEUTRAL",
    "formatted": "N/A",
    "threshold_breach": False,
}


# ---------------------------------------------------------------------------
# 1. TTF DA vs M1 Spread
# ---------------------------------------------------------------------------


def calc_ttf_da_vs_m1_spread(ttf_da: float, ttf_m1: float) -> MetricResult:
    """Compute the TTF day-ahead minus Month-1 forward spread.

    Positive spread indicates backwardation (near-term tightness);
    negative spread indicates contango (comfortable prompt supply).

    Args:
        ttf_da: TTF day-ahead price in EUR/MWh.
        ttf_m1: TTF Month-1 forward price in EUR/MWh.

    Returns:
        A :class:`MetricResult` with the spread value, signal, formatted
        string (e.g. ``"+2.35 EUR/MWh"``), and threshold breach flag.
    """
    spread = ttf_da - ttf_m1
    thresholds = THRESHOLDS["ttf_da_vs_m1_spread"]

    if spread > thresholds["backwardation"]:
        signal = "BULLISH"
    elif spread < thresholds["deep_contango"]:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    breach = spread > thresholds["backwardation"] or spread < thresholds["deep_contango"]

    return {
        "value": spread,
        "signal": signal,
        "formatted": f"{_format_signed(spread)} EUR/MWh",
        "threshold_breach": breach,
    }


# ---------------------------------------------------------------------------
# 2. EUA 30-day Momentum
# ---------------------------------------------------------------------------


def calc_eua_30d_momentum(eua_series: pd.Series) -> MetricResult:
    """Compute the 30-day percentage change in EUA price.

    Momentum is calculated as ``((last - first) / first) * 100`` where
    *first* and *last* are the earliest and latest values in the series.

    Args:
        eua_series: 30-day EUA price series with DatetimeIndex.

    Returns:
        A :class:`MetricResult` with momentum as a percentage, signal,
        formatted string (e.g. ``"+5.30%"``), and threshold breach flag.
    """
    first = float(eua_series.iloc[0])
    last = float(eua_series.iloc[-1])
    momentum = ((last - first) / first) * 100.0

    thresholds = THRESHOLDS["eua_30d_momentum"]

    if momentum > thresholds["strong_bull"]:
        signal = "BULLISH"
    elif momentum < thresholds["strong_bear"]:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    breach = momentum > thresholds["strong_bull"] or momentum < thresholds["strong_bear"]

    return {
        "value": momentum,
        "signal": signal,
        "formatted": f"{_format_signed(momentum)}%",
        "threshold_breach": breach,
    }


# ---------------------------------------------------------------------------
# 3. Gas Storage Deficit
# ---------------------------------------------------------------------------


def calc_gas_storage_deficit(
    current_pct: float, avg_5yr_pct: float
) -> MetricResult:
    """Compute the gas storage deficit vs the 5-year seasonal average.

    Deficit is ``current_pct - avg_5yr_pct``.  Negative values indicate
    stocks are below the seasonal norm.

    Args:
        current_pct: Current EU aggregate gas storage fill level (0–100).
        avg_5yr_pct: Five-year seasonal average fill level (0–100).

    Returns:
        A :class:`MetricResult` with deficit in percentage points, signal,
        formatted string (e.g. ``"-4.20 pp"``), and threshold breach flag.
    """
    deficit = current_pct - avg_5yr_pct
    thresholds = THRESHOLDS["gas_storage_deficit_pct"]

    if deficit < thresholds["tight"]:
        signal = "BEARISH"
    elif deficit > thresholds["comfortable"]:
        signal = "BULLISH"
    else:
        signal = "NEUTRAL"

    breach = deficit < thresholds["tight"] or deficit > thresholds["comfortable"]

    return {
        "value": deficit,
        "signal": signal,
        "formatted": f"{_format_signed(deficit)} pp",
        "threshold_breach": breach,
    }


# ---------------------------------------------------------------------------
# 4. Dark Spread DE
# ---------------------------------------------------------------------------


def calc_dark_spread_de(
    power_da: float,
    gas_price: float,
    eua_price: float,
    efficiency: float,
    emission_factor: float,
) -> MetricResult:
    """Compute the German dark spread.

    Dark spread approximates the gross margin of a gas-fired power plant:
    ``power_da - (gas_price / efficiency + eua_price * emission_factor)``.

    Args:
        power_da: German baseload day-ahead price in EUR/MWh.
        gas_price: TTF day-ahead gas price in EUR/MWh.
        eua_price: EUA carbon price in EUR/tCO₂.
        efficiency: Gas plant thermal efficiency (e.g. 0.49).
        emission_factor: Emission factor in tCO₂/MWh (e.g. 0.37).

    Returns:
        A :class:`MetricResult` with spread in EUR/MWh, signal, formatted
        string, and threshold breach flag.
    """
    spread = power_da - (gas_price / efficiency + eua_price * emission_factor)
    thresholds = THRESHOLDS["dark_spread_de"]

    if spread > thresholds["profitable"]:
        signal = "BULLISH"
    elif spread < thresholds["unprofitable"]:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    breach = spread > thresholds["profitable"] or spread < thresholds["unprofitable"]

    return {
        "value": spread,
        "signal": signal,
        "formatted": f"{_format_signed(spread)} EUR/MWh",
        "threshold_breach": breach,
    }


# ---------------------------------------------------------------------------
# 5. Clean Spark Spread DE
# ---------------------------------------------------------------------------


def calc_clean_spark_spread_de(
    power_da: float,
    gas_price: float,
    eua_price: float,
    efficiency: float,
    emission_factor: float,
) -> MetricResult:
    """Compute the German clean spark spread.

    Same formula as the dark spread — the distinction is in the threshold
    levels and the naming convention used by European power desks:
    ``power_da - (gas_price / efficiency + eua_price * emission_factor)``.

    Args:
        power_da: German baseload day-ahead price in EUR/MWh.
        gas_price: TTF day-ahead gas price in EUR/MWh.
        eua_price: EUA carbon price in EUR/tCO₂.
        efficiency: Gas plant thermal efficiency (e.g. 0.49).
        emission_factor: Emission factor in tCO₂/MWh (e.g. 0.37).

    Returns:
        A :class:`MetricResult` with spread in EUR/MWh, signal, formatted
        string, and threshold breach flag.
    """
    spread = power_da - (gas_price / efficiency + eua_price * emission_factor)
    thresholds = THRESHOLDS["clean_spark_spread_de"]

    if spread > thresholds["profitable"]:
        signal = "BULLISH"
    elif spread < thresholds["unprofitable"]:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    breach = spread > thresholds["profitable"] or spread < thresholds["unprofitable"]

    return {
        "value": spread,
        "signal": signal,
        "formatted": f"{_format_signed(spread)} EUR/MWh",
        "threshold_breach": breach,
    }


# ---------------------------------------------------------------------------
# 6. TTF-EUA Correlation (30-day)
# ---------------------------------------------------------------------------


def calc_ttf_eua_correlation(
    ttf_series: pd.Series, eua_series: pd.Series
) -> MetricResult:
    """Compute the 30-day Pearson correlation of TTF and EUA daily returns.

    Daily percentage returns are computed for each series, then aligned by
    date.  If fewer than 2 aligned data points exist after alignment, the
    function returns a correlation of 0.0 with a ``"NEUTRAL"`` signal.

    Args:
        ttf_series: 30-day TTF price series with DatetimeIndex.
        eua_series: 30-day EUA price series with DatetimeIndex.

    Returns:
        A :class:`MetricResult` with correlation coefficient, signal,
        formatted string (e.g. ``"+0.72"``), and threshold breach flag.
    """
    # Compute daily percentage returns
    ttf_returns = ttf_series.pct_change().dropna()
    eua_returns = eua_series.pct_change().dropna()

    # Align by date (inner join on index)
    aligned = pd.DataFrame(
        {"ttf": ttf_returns, "eua": eua_returns}
    ).dropna()

    if len(aligned) < 2:
        return {
            "value": 0.0,
            "signal": "NEUTRAL",
            "formatted": "+0.00",
            "threshold_breach": False,
        }

    corr = float(aligned["ttf"].corr(aligned["eua"]))

    # Handle NaN from constant series
    if np.isnan(corr):
        corr = 0.0

    thresholds = THRESHOLDS["ttf_eua_correlation_30d"]
    abs_corr = abs(corr)

    if abs_corr > thresholds["high"]:
        signal = "ALERT"
    elif abs_corr < thresholds["decorrelated"]:
        signal = "NEUTRAL"
    else:
        signal = "BULLISH"

    breach = abs_corr > thresholds["high"] or abs_corr < thresholds["decorrelated"]

    return {
        "value": corr,
        "signal": signal,
        "formatted": _format_signed(corr),
        "threshold_breach": breach,
    }


# ---------------------------------------------------------------------------
# 7. Power DA Realised Volatility (20-day)
# ---------------------------------------------------------------------------


def calc_power_realised_vol(power_series: pd.Series) -> MetricResult:
    """Compute the 20-day realised volatility of German DA power prices.

    Volatility is the standard deviation of the trailing 20-day price
    series.

    Args:
        power_series: 20-day German power day-ahead price series with
            DatetimeIndex.

    Returns:
        A :class:`MetricResult` with volatility in EUR/MWh, signal,
        formatted string, and threshold breach flag.
    """
    vol = float(power_series.std())

    thresholds = THRESHOLDS["power_da_realised_vol_20d"]

    if vol > thresholds["high_vol"]:
        signal = "ALERT"
    elif vol < thresholds["low_vol"]:
        signal = "NEUTRAL"
    else:
        signal = "BULLISH"

    breach = vol > thresholds["high_vol"] or vol < thresholds["low_vol"]

    return {
        "value": vol,
        "signal": signal,
        "formatted": f"{vol:.2f} EUR/MWh",
        "threshold_breach": breach,
    }


# ---------------------------------------------------------------------------
# Orchestrator: calculate_all_metrics
# ---------------------------------------------------------------------------


def calculate_all_metrics(data: MarketData) -> MetricsResult:
    """Compute all seven monitor metrics from market data.

    Calls each individual calculator, passing the appropriate fields from
    *data*.  Each call is wrapped in a ``try/except`` — on failure, a
    default :class:`MetricResult` with ``value=0.0``, ``signal="NEUTRAL"``,
    ``formatted="N/A"``, and ``threshold_breach=False`` is used so that one
    failing metric does not prevent the others from being computed.

    Args:
        data: A complete :class:`MarketData` dictionary from the ingestion
            layer.

    Returns:
        A :class:`MetricsResult` containing all seven metric keys.
    """

    def _safe_calc(name: str, fn: Any, *args: Any, **kwargs: Any) -> MetricResult:
        """Execute *fn* and return its result, or the default on failure."""
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.exception("Metric calculation failed for %s", name)
            return dict(_DEFAULT_METRIC)  # type: ignore[return-value]

    return {
        "ttf_da_vs_m1_spread": _safe_calc(
            "ttf_da_vs_m1_spread",
            calc_ttf_da_vs_m1_spread,
            data["ttf_da"],
            data["ttf_m1"],
        ),
        "eua_30d_momentum": _safe_calc(
            "eua_30d_momentum",
            calc_eua_30d_momentum,
            data["eua_series"],
        ),
        "gas_storage_deficit_pct": _safe_calc(
            "gas_storage_deficit_pct",
            calc_gas_storage_deficit,
            data["storage_current_pct"],
            data["storage_5yr_avg_pct"],
        ),
        "dark_spread_de": _safe_calc(
            "dark_spread_de",
            calc_dark_spread_de,
            data["de_power_da"],
            data["ttf_da"],
            data["eua_price"],
            GAS_PLANT_EFFICIENCY,
            EMISSION_FACTOR,
        ),
        "clean_spark_spread_de": _safe_calc(
            "clean_spark_spread_de",
            calc_clean_spark_spread_de,
            data["de_power_da"],
            data["ttf_da"],
            data["eua_price"],
            GAS_PLANT_EFFICIENCY,
            EMISSION_FACTOR,
        ),
        "ttf_eua_correlation_30d": _safe_calc(
            "ttf_eua_correlation_30d",
            calc_ttf_eua_correlation,
            data["ttf_series"],
            data["eua_series"],
        ),
        "power_da_realised_vol_20d": _safe_calc(
            "power_da_realised_vol_20d",
            calc_power_realised_vol,
            data["de_power_series"],
        ),
    }
