"""Canonical definitions for all seven European Cross-Commodity Risk Pack metrics.

This module is the single source of truth for metric names, formulas, units,
threshold values, and trading-relevance descriptions.  It contains **no
computation** — only static definitions consumed by the calculator, prompt
builder, and dashboard components.

The :data:`METRIC_DEFINITIONS` dictionary maps each metric's canonical key
(matching the keys in :class:`~euro_risk_pack.models.MetricsResult`) to a
:class:`MetricDefinition` dataclass instance.
"""

from __future__ import annotations

from dataclasses import dataclass

from euro_risk_pack.config import THRESHOLDS


# ---------------------------------------------------------------------------
# MetricDefinition dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricDefinition:
    """Immutable definition of a single monitor metric.

    Attributes:
        name: Full human-readable metric name
            (e.g. ``"TTF DA vs M1 Spread"``).
        short_name: Abbreviated label used in dashboard metric cards
            (e.g. ``"TTF Spread"``).
        formula: Mathematical formula expressed as a concise string
            (e.g. ``"TTF_DA - TTF_M1"``).
        unit: Unit of measurement for the computed value
            (e.g. ``"EUR/MWh"``, ``"%"``, ``"pp"``).  Empty string when
            the metric is dimensionless.
        thresholds: Signal-classification thresholds copied from
            :data:`euro_risk_pack.config.THRESHOLDS`.  Keys are threshold
            names (e.g. ``"backwardation"``, ``"deep_contango"``), values
            are the numeric boundary.
        trading_relevance: Multi-line prose explaining what the metric
            signals to a trader and how it should inform positioning.
    """

    name: str
    short_name: str
    formula: str
    unit: str
    thresholds: dict[str, float]
    trading_relevance: str


# ---------------------------------------------------------------------------
# METRIC_DEFINITIONS — all 7 metrics
# ---------------------------------------------------------------------------

METRIC_DEFINITIONS: dict[str, MetricDefinition] = {
    "ttf_da_vs_m1_spread": MetricDefinition(
        name="TTF DA vs M1 Spread",
        short_name="TTF Spread",
        formula="TTF_DA - TTF_M1",
        unit="EUR/MWh",
        thresholds=THRESHOLDS["ttf_da_vs_m1_spread"],
        trading_relevance=(
            "Positive spread (backwardation) signals near-term supply\n"
            "tightness — the market is willing to pay a premium for\n"
            "immediate delivery over the front-month forward.  This\n"
            "typically occurs during cold snaps, unplanned outages, or\n"
            "LNG cargo diversions.  Negative spread (contango) indicates\n"
            "comfortable prompt supply and incentivises storage injection.\n"
            "Deep contango beyond −2 EUR/MWh suggests oversupply or\n"
            "demand destruction and may warrant short prompt / long\n"
            "forward positioning."
        ),
    ),
    "eua_30d_momentum": MetricDefinition(
        name="EUA 30d Momentum",
        short_name="EUA Mom",
        formula="((last-first)/first)*100",
        unit="%",
        thresholds=THRESHOLDS["eua_30d_momentum"],
        trading_relevance=(
            "Thirty-day momentum captures the medium-term trend in\n"
            "carbon allowance prices.  Strong positive momentum (>10 %)\n"
            "often reflects tightening compliance demand, reduced free\n"
            "allocation, or speculative buying ahead of surrender\n"
            "deadlines.  Strong negative momentum (<−10 %) may signal\n"
            "industrial demand weakness, policy uncertainty, or a\n"
            "broader risk-off move.  Because EUA costs feed directly\n"
            "into power generation margins, sustained momentum shifts\n"
            "reprice the entire forward power curve."
        ),
    ),
    "gas_storage_deficit_pct": MetricDefinition(
        name="Gas Storage Deficit",
        short_name="Storage Δ",
        formula="current_pct - avg_5yr_pct",
        unit="pp",
        thresholds=THRESHOLDS["gas_storage_deficit_pct"],
        trading_relevance=(
            "The storage deficit measures how current EU aggregate gas\n"
            "inventories compare to the five-year seasonal average.\n"
            "A deficit below −5 pp signals that stocks are materially\n"
            "below normal, increasing the risk of winter supply\n"
            "shortfalls and supporting prompt gas prices.  A surplus\n"
            "above +5 pp indicates comfortable inventories that dampen\n"
            "upside price risk and may encourage producers to curtail\n"
            "injection.  Traders watch this metric alongside injection/\n"
            "withdrawal rates to gauge restocking pace relative to\n"
            "seasonal norms."
        ),
    ),
    "dark_spread_de": MetricDefinition(
        name="Dark Spread DE",
        short_name="Dark Sprd",
        formula="power_da - (gas/eff + eua*ef)",
        unit="EUR/MWh",
        thresholds=THRESHOLDS["dark_spread_de"],
        trading_relevance=(
            "The dark spread approximates the gross margin of a German\n"
            "gas-fired power plant by subtracting fuel and carbon costs\n"
            "from the day-ahead power price.  A spread above +5 EUR/MWh\n"
            "signals profitable generation and incentivises plant\n"
            "dispatch, which in turn increases gas demand.  A spread\n"
            "below −5 EUR/MWh means gas plants are out of the money,\n"
            "reducing gas burn and potentially tightening the power\n"
            "stack if renewables underperform.  This metric is a key\n"
            "input for gas-to-power flow modelling."
        ),
    ),
    "clean_spark_spread_de": MetricDefinition(
        name="Clean Spark Spread DE",
        short_name="Spark Sprd",
        formula="power_da - gas/eff - eua*ef",
        unit="EUR/MWh",
        thresholds=THRESHOLDS["clean_spark_spread_de"],
        trading_relevance=(
            "The clean spark spread refines the dark spread by\n"
            "explicitly deducting the carbon cost component for a\n"
            "gas-fired plant.  It is the standard profitability\n"
            "benchmark used by European power desks.  A positive\n"
            "spread above +3 EUR/MWh indicates that gas generation\n"
            "is economically viable after accounting for emissions.\n"
            "A negative spread below −3 EUR/MWh signals that gas\n"
            "plants should be mothballed or that the power price\n"
            "needs to rise to clear the market.  Divergence between\n"
            "dark and clean spark spreads highlights the marginal\n"
            "impact of carbon pricing on dispatch economics."
        ),
    ),
    "ttf_eua_correlation_30d": MetricDefinition(
        name="TTF-EUA Correlation 30d",
        short_name="TTF-EUA ρ",
        formula="pearson(ttf_returns, eua_returns)",
        unit="",
        thresholds=THRESHOLDS["ttf_eua_correlation_30d"],
        trading_relevance=(
            "The 30-day rolling Pearson correlation between TTF gas\n"
            "and EUA carbon daily returns measures the strength of\n"
            "the gas-carbon linkage.  High correlation (|ρ| > 0.7)\n"
            "indicates that gas and carbon are moving in lockstep,\n"
            "often driven by a common macro factor such as weather\n"
            "or geopolitical risk.  Low correlation (|ρ| < 0.3)\n"
            "suggests the two markets are decoupled, creating\n"
            "potential relative-value opportunities.  Sudden\n"
            "correlation regime changes can signal structural\n"
            "shifts in the fuel-switching stack or policy\n"
            "interventions."
        ),
    ),
    "power_da_realised_vol_20d": MetricDefinition(
        name="Power DA Vol 20d",
        short_name="Pwr Vol",
        formula="std(power_da[-20:])",
        unit="EUR/MWh",
        thresholds=THRESHOLDS["power_da_realised_vol_20d"],
        trading_relevance=(
            "Twenty-day realised volatility of German day-ahead power\n"
            "prices measures recent price dispersion.  High volatility\n"
            "(>15 EUR/MWh) typically accompanies tight reserve margins,\n"
            "renewable intermittency, or transmission constraints and\n"
            "increases the value of flexible generation and storage\n"
            "assets.  Low volatility (<5 EUR/MWh) suggests a stable\n"
            "supply-demand balance and compresses option premia.\n"
            "Traders use this metric to calibrate hedging ratios and\n"
            "assess whether implied volatility in the options market\n"
            "is rich or cheap relative to realised moves."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Accessor functions
# ---------------------------------------------------------------------------


def get_definition(metric_key: str) -> MetricDefinition:
    """Retrieve the definition for a single metric by its canonical key.

    Args:
        metric_key: One of the seven canonical metric keys, e.g.
            ``"ttf_da_vs_m1_spread"`` or ``"eua_30d_momentum"``.

    Returns:
        The corresponding :class:`MetricDefinition` instance.

    Raises:
        KeyError: If *metric_key* is not found in
            :data:`METRIC_DEFINITIONS`.
    """
    return METRIC_DEFINITIONS[metric_key]


def get_all_definitions() -> dict[str, MetricDefinition]:
    """Return the complete dictionary of all metric definitions.

    Returns:
        A dictionary mapping each canonical metric key to its
        :class:`MetricDefinition`.  The returned object is the
        module-level :data:`METRIC_DEFINITIONS` dict itself (not a
        copy), so callers should treat it as read-only.
    """
    return METRIC_DEFINITIONS
