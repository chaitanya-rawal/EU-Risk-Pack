"""Data model type definitions for the European Cross-Commodity Risk Pack.

This module defines all shared data structures used across the package:

- **MarketData**: Unified container for all ingested market data returned by
  the data ingestion layer.  Holds spot prices, forward prices, time series,
  and storage metrics for TTF gas, EUA carbon, German/French power, and LNG.

- **MetricResult**: The output of a single metric calculation, carrying the
  raw numeric value, a signal classification, a human-readable formatted
  string, and a threshold-breach flag.

- **MetricsResult**: Aggregation of all seven monitor metrics keyed by their
  canonical names.

- **SourceConfig**: Dataclass describing a single external data source with
  its primary and fallback endpoints, ticker symbols, API URLs, and cache key.

- **PromptLogEntry**: Schema for a single entry in the ``prompts_log.jsonl``
  audit log, recording every LLM call (or fallback) with full prompt text.

- **DashboardMetricCard**: Data needed to render one metric card in the HTML
  dashboard's metric strip.

- **DeskNoteContent**: Structural breakdown of the markdown desk note into
  its constituent sections (header, metrics table, narrative, charts, footer).

All types use :class:`~typing.TypedDict` or :func:`~dataclasses.dataclass`
so that static type checkers and IDE tooling can validate usage across the
codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TypedDict

import pandas as pd


# ---------------------------------------------------------------------------
# Market Data
# ---------------------------------------------------------------------------


class MarketData(TypedDict):
    """Unified market data container returned by ``ingest_all()``.

    Every field is required — the ingestion layer guarantees that all values
    are populated (falling back to cache or mock data when live APIs fail).

    Scalar prices are in EUR and represent the most recent available value
    for the target date.  Time series carry a :class:`~pandas.DatetimeIndex`
    sorted in ascending chronological order.

    Attributes:
        ttf_da: TTF day-ahead price in EUR/MWh.
        ttf_m1: TTF Month-1 forward price in EUR/MWh.
        ttf_series: 30-day TTF price series with DatetimeIndex.
        eua_price: EUA carbon allowance price in EUR/tCO₂.
        eua_series: 30-day EUA price series with DatetimeIndex.
        de_power_da: German baseload day-ahead price in EUR/MWh.
        fr_power_da: French baseload day-ahead price in EUR/MWh.
        de_power_series: 20-day German power day-ahead series with
            DatetimeIndex.
        storage_current_pct: Current EU aggregate gas storage fill level
            as a percentage (0–100).
        storage_5yr_avg_pct: Five-year seasonal average gas storage fill
            level as a percentage (0–100).
        storage_series: Storage time series :class:`~pandas.DataFrame` with
            columns ``date``, ``current_pct``, and ``avg_5yr_pct``.
        lng_sendout: LNG send-out proxy in GWh/day (from GIE ALSI).
    """

    ttf_da: float
    ttf_m1: float
    ttf_series: pd.Series
    eua_price: float
    eua_series: pd.Series
    de_power_da: float
    fr_power_da: float
    de_power_series: pd.Series
    storage_current_pct: float
    storage_5yr_avg_pct: float
    storage_series: pd.DataFrame
    lng_sendout: float


# ---------------------------------------------------------------------------
# Metric Results
# ---------------------------------------------------------------------------


class MetricResult(TypedDict):
    """Result of a single computed monitor metric.

    Produced by each individual metric calculator function and consumed by
    the dashboard builder, report builder, and prompt builder.

    Attributes:
        value: Raw numeric result of the metric calculation.
        signal: Classification string — one of ``"BULLISH"``,
            ``"BEARISH"``, ``"NEUTRAL"``, or ``"ALERT"``.
        formatted: Human-readable display string including sign prefix and
            unit (e.g. ``"+2.35 EUR/MWh"``, ``"-4.2%"``).
        threshold_breach: ``True`` when the metric value exceeds any of its
            configured thresholds in ``config.THRESHOLDS``.
    """

    value: float
    signal: str
    formatted: str
    threshold_breach: bool


class MetricsResult(TypedDict):
    """All seven computed monitor metrics.

    Returned by ``calculate_all_metrics()`` and consumed by the chart
    generator, prompt builder, report builder, and dashboard builder.
    Every key corresponds to one of the canonical metric names defined in
    ``metrics/definitions.py``.

    Attributes:
        ttf_da_vs_m1_spread: TTF day-ahead minus Month-1 forward spread.
        eua_30d_momentum: 30-day percentage change in EUA price.
        gas_storage_deficit_pct: Current storage fill minus 5-year seasonal
            average (negative = deficit).
        dark_spread_de: German dark spread — power DA minus fuel + carbon
            cost.
        clean_spark_spread_de: German clean spark spread — dark spread with
            explicit carbon cost deduction.
        ttf_eua_correlation_30d: 30-day rolling Pearson correlation of TTF
            and EUA daily returns.
        power_da_realised_vol_20d: 20-day realised volatility (std dev) of
            German power day-ahead prices.
    """

    ttf_da_vs_m1_spread: MetricResult
    eua_30d_momentum: MetricResult
    gas_storage_deficit_pct: MetricResult
    dark_spread_de: MetricResult
    clean_spark_spread_de: MetricResult
    ttf_eua_correlation_30d: MetricResult
    power_da_realised_vol_20d: MetricResult


# ---------------------------------------------------------------------------
# Source Configuration
# ---------------------------------------------------------------------------


@dataclass
class SourceConfig:
    """Configuration for a single external data source.

    Used by the data source registry (``data/sources.py``) to describe how
    to fetch, cache, and fall back for each market data feed.

    Attributes:
        name: Human-readable display name (e.g. ``"TTF Day-Ahead"``).
        source_type: Provider category — ``"yfinance"``, ``"api"``, or
            ``"csv"``.
        primary_endpoint: Primary data source identifier (ticker, URL, or
            file path depending on *source_type*).
        fallback_endpoint: Optional secondary source tried when the primary
            fails.  ``None`` if no fallback is configured.
        ticker: Yahoo Finance ticker symbol (e.g. ``"TTF=F"``).  ``None``
            for non-yfinance sources.
        api_url: REST API base URL for API-type sources.  ``None`` for
            non-API sources.
        cache_key: Prefix used when storing/loading cached CSV files
            (e.g. ``"ttf_da"``).
        description: Short prose description of what this source provides.
    """

    name: str
    source_type: str
    primary_endpoint: str
    fallback_endpoint: Optional[str]
    ticker: Optional[str]
    api_url: Optional[str]
    cache_key: str
    description: str


# ---------------------------------------------------------------------------
# Prompt Logging
# ---------------------------------------------------------------------------


class PromptLogEntry(TypedDict):
    """Schema for a single entry in ``prompts_log.jsonl``.

    Every LLM call — whether it succeeds or falls back to a template
    narrative — is recorded as one JSON line with this structure.

    Attributes:
        timestamp: ISO 8601 formatted timestamp of the call.
        model: Model identifier used (e.g. ``"claude-sonnet-4-20250514"``).
        system_prompt: Full system prompt text sent to the model.
        user_prompt: Full user prompt text sent to the model.
        response: Complete response text (or fallback narrative).
        is_fallback: ``True`` if a template fallback was used instead of a
            live API response.
        tokens_used: Token count reported by the API, or ``None`` if
            unavailable (e.g. during fallback).
    """

    timestamp: str
    model: str
    system_prompt: str
    user_prompt: str
    response: str
    is_fallback: bool
    tokens_used: Optional[int]


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class DashboardMetricCard(TypedDict):
    """Data for a single metric card in the dashboard's metric strip.

    Produced by ``dashboard/builder.py:format_metric_cards()`` and serialised
    to JSON for embedding in the HTML template.

    Attributes:
        label: Uppercase short label (e.g. ``"TTF SPREAD"``).
        value: Formatted numeric value (e.g. ``"+2.35"``).
        unit: Unit of measurement (e.g. ``"EUR/MWh"``).
        signal: Signal classification — ``"BULLISH"``, ``"BEARISH"``,
            ``"NEUTRAL"``, or ``"ALERT"``.
        color: Hex colour code for rendering the value text.
        arrow: Directional indicator — ``"↑"``, ``"↓"``, or ``"→"``.
    """

    label: str
    value: str
    unit: str
    signal: str
    color: str
    arrow: str


# ---------------------------------------------------------------------------
# Desk Note
# ---------------------------------------------------------------------------


class DeskNoteContent(TypedDict):
    """Structural breakdown of the markdown desk note.

    Used internally by ``report/builder.py`` to assemble the final markdown
    document from its constituent sections before writing to disk.

    Attributes:
        header: Opening section with the report date, analyst name, and
            contact email.
        metrics_table: Markdown-formatted table containing all seven metric
            values, signals, and formatted strings.
        narrative: LLM-generated (or fallback) three-paragraph narrative
            covering gas tightness, carbon signal, and power curve
            implications.
        chart_references: List of markdown image reference strings pointing
            to the generated PNG chart files.
        footer: Closing section with data source attributions and the
            pipeline run timestamp.
    """

    header: str
    metrics_table: str
    narrative: str
    chart_references: list[str]
    footer: str
