"""Dashboard builder for the European Cross-Commodity Risk Pack.

Assembles and writes a self-contained HTML dashboard file by rendering the
template from :mod:`euro_risk_pack.dashboard.template` with market data,
computed metrics, narrative text, and prompt log information.

Uses Python :class:`string.Template` with ``$``-syntax for placeholder
substitution — no Jinja2 dependency.

Public API
----------
- :func:`prepare_chart_data` — converts pandas Series/DataFrames to
  JSON-serializable lists for Chart.js.
- :func:`format_metric_cards` — formats metrics into
  :class:`~euro_risk_pack.models.DashboardMetricCard` dicts.
- :func:`build_dashboard` — renders the template, embeds chart data as
  JSON, and writes the HTML file to disk.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from string import Template
from typing import Any, Optional

import numpy as np
import pandas as pd

from euro_risk_pack.config import (
    ANALYST_EMAIL,
    ANALYST_NAME,
    COLORS,
    OUTPUT_DIR,
    VERSION,
)
from euro_risk_pack.dashboard.template import DASHBOARD_TEMPLATE
from euro_risk_pack.metrics.definitions import METRIC_DEFINITIONS
from euro_risk_pack.models import (
    DashboardMetricCard,
    MarketData,
    MetricResult,
    MetricsResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal → colour / arrow mapping
# ---------------------------------------------------------------------------

_SIGNAL_COLORS: dict[str, str] = {
    "BULLISH": COLORS["power"],    # #3fb950
    "BEARISH": COLORS["negative"],  # #f85149
    "NEUTRAL": COLORS["text_muted"],  # #6e7681
    "ALERT": COLORS["eua"],        # #f0883e
}

_SIGNAL_ARROWS: dict[str, str] = {
    "BULLISH": "\u2191",   # ↑
    "BEARISH": "\u2193",   # ↓
    "NEUTRAL": "\u2192",   # →
    "ALERT": "\u2191",     # ↑
}


# ---------------------------------------------------------------------------
# prepare_chart_data
# ---------------------------------------------------------------------------


def prepare_chart_data(market_data: MarketData) -> dict[str, Any]:
    """Convert market data series to JSON-serializable structures for Chart.js.

    Extracts date labels and numeric values from pandas Series and
    DataFrames, rounding floats to 2 decimal places.

    Args:
        market_data: A complete :class:`MarketData` dictionary from the
            ingestion layer.

    Returns:
        A dictionary with keys:

        - ``ttf_series`` — list of TTF price floats
        - ``eua_series`` — list of EUA price floats
        - ``dates_ttf`` — list of TTF date label strings
        - ``dates_eua`` — list of EUA date label strings
        - ``storage_series`` — list of current storage % floats
        - ``storage_avg`` — list of 5yr avg storage % floats
        - ``dates_storage`` — list of storage date label strings
        - ``spread_series`` — dict with ``dark`` and ``spark`` lists
        - ``dates_spread`` — list of spread date label strings
    """

    def _series_to_lists(
        series: pd.Series,
    ) -> tuple[list[str], list[float]]:
        """Extract date labels and rounded values from a pandas Series."""
        dates: list[str] = []
        values: list[float] = []
        for idx, val in series.items():
            if isinstance(idx, pd.Timestamp):
                dates.append(idx.strftime("%Y-%m-%d"))
            else:
                dates.append(str(idx))
            values.append(round(float(val), 2))
        return dates, values

    # TTF series
    dates_ttf, ttf_values = _series_to_lists(market_data["ttf_series"])

    # EUA series
    dates_eua, eua_values = _series_to_lists(market_data["eua_series"])

    # Storage series (DataFrame with date, current_pct, avg_5yr_pct)
    storage_df = market_data["storage_series"]
    dates_storage: list[str] = []
    storage_current: list[float] = []
    storage_avg: list[float] = []

    if isinstance(storage_df, pd.DataFrame) and len(storage_df) > 0:
        for _, row in storage_df.iterrows():
            date_val = row.get("date", "")
            if isinstance(date_val, pd.Timestamp):
                dates_storage.append(date_val.strftime("%Y-%m-%d"))
            else:
                dates_storage.append(str(date_val))
            storage_current.append(round(float(row.get("current_pct", 0)), 2))
            storage_avg.append(round(float(row.get("avg_5yr_pct", 0)), 2))

    # Spread series — compute from power series and market data
    # We derive dark/spark spreads from the power series for charting
    de_power = market_data["de_power_series"]
    ttf_da = market_data["ttf_da"]
    eua_price = market_data["eua_price"]
    efficiency = 0.49
    emission_factor = 0.37

    dates_spread: list[str] = []
    dark_spreads: list[float] = []
    spark_spreads: list[float] = []

    for idx, power_val in de_power.items():
        if isinstance(idx, pd.Timestamp):
            dates_spread.append(idx.strftime("%Y-%m-%d"))
        else:
            dates_spread.append(str(idx))
        pv = float(power_val)
        dark = pv - (ttf_da / efficiency + eua_price * emission_factor)
        spark = pv - (ttf_da / efficiency + eua_price * emission_factor)
        dark_spreads.append(round(dark, 2))
        spark_spreads.append(round(spark, 2))

    return {
        "ttf_series": ttf_values,
        "eua_series": eua_values,
        "dates_ttf": dates_ttf,
        "dates_eua": dates_eua,
        "storage_series": storage_current,
        "storage_avg": storage_avg,
        "dates_storage": dates_storage,
        "spread_series": {"dark": dark_spreads, "spark": spark_spreads},
        "dates_spread": dates_spread,
    }


# ---------------------------------------------------------------------------
# format_metric_cards
# ---------------------------------------------------------------------------


def format_metric_cards(metrics: MetricsResult) -> list[DashboardMetricCard]:
    """Format computed metrics into dashboard metric card dictionaries.

    Produces one :class:`~euro_risk_pack.models.DashboardMetricCard` per
    metric, ordered to match the canonical metric definitions.

    Args:
        metrics: Computed :class:`MetricsResult` with all 7 metric keys.

    Returns:
        A list of 7 :class:`DashboardMetricCard` dicts, each containing
        ``label``, ``value``, ``unit``, ``signal``, ``color``, and
        ``arrow``.
    """
    cards: list[DashboardMetricCard] = []

    for key, definition in METRIC_DEFINITIONS.items():
        result: Optional[MetricResult] = metrics.get(key)  # type: ignore[arg-type]
        if result is None:
            continue

        signal = result["signal"]
        color = _SIGNAL_COLORS.get(signal, COLORS["text_muted"])
        arrow = _SIGNAL_ARROWS.get(signal, "\u2192")

        # Use the formatted value from the metric result, stripping the unit
        # since we display it separately
        formatted_value = result["formatted"]
        unit = definition.unit if definition.unit else ""

        # Strip the unit suffix from the formatted value if present
        if unit and formatted_value.endswith(unit):
            formatted_value = formatted_value[: -len(unit)].strip()

        card: DashboardMetricCard = {
            "label": definition.short_name.upper(),
            "value": formatted_value,
            "unit": unit,
            "signal": signal,
            "color": color,
            "arrow": arrow,
        }
        cards.append(card)

    return cards


# ---------------------------------------------------------------------------
# _format_signals — extract key trading signals for the signal panel
# ---------------------------------------------------------------------------


def _format_signals(metrics: MetricsResult) -> list[dict[str, str]]:
    """Extract the 4 most important trading signals for the signal panel.

    Selects TTF spread, storage deficit, dark spread, and EUA momentum
    as the key signals displayed in the trading signals panel.

    Args:
        metrics: Computed :class:`MetricsResult`.

    Returns:
        A list of 4 signal dicts with ``label``, ``value``, ``signal``,
        and ``color`` keys.
    """
    signal_keys = [
        ("ttf_da_vs_m1_spread", "TTF CURVE"),
        ("gas_storage_deficit_pct", "GAS STORAGE"),
        ("dark_spread_de", "DARK SPREAD"),
        ("eua_30d_momentum", "CARBON MOMENTUM"),
    ]

    signals: list[dict[str, str]] = []
    for key, label in signal_keys:
        result: Optional[MetricResult] = metrics.get(key)  # type: ignore[arg-type]
        if result is None:
            continue
        sig = result["signal"]
        color = _SIGNAL_COLORS.get(sig, COLORS["text_muted"])
        signals.append({
            "label": label,
            "value": result["formatted"],
            "signal": sig,
            "color": color,
        })

    return signals


# ---------------------------------------------------------------------------
# _format_narrative_html — convert narrative text to HTML sections
# ---------------------------------------------------------------------------


def _format_narrative_html(narrative: str) -> str:
    """Convert the narrative text into HTML sections for the desk note panel.

    Attempts to split the narrative into the three expected sections
    (GAS TIGHTNESS, CARBON SIGNAL, POWER CURVE IMPLICATION).  Falls back
    to wrapping the entire text in a single section if splitting fails.

    Args:
        narrative: The LLM-generated (or fallback) narrative text.

    Returns:
        An HTML string with ``desk-note-section`` divs.
    """
    section_titles = [
        "GAS TIGHTNESS",
        "CARBON SIGNAL",
        "POWER CURVE IMPLICATION",
    ]

    # Try to split on section headers
    parts: list[tuple[str, str]] = []
    remaining = narrative

    for i, title in enumerate(section_titles):
        # Look for the title in the text (case-insensitive)
        lower_remaining = remaining.lower()
        title_lower = title.lower()
        idx = lower_remaining.find(title_lower)

        if idx >= 0:
            # Find the end of this section (start of next title or end)
            next_idx = len(remaining)
            for next_title in section_titles[i + 1 :]:
                ni = lower_remaining.find(next_title.lower(), idx + len(title))
                if ni >= 0:
                    next_idx = ni
                    break

            section_text = remaining[idx + len(title) :next_idx].strip()
            # Remove leading colons, dashes, newlines
            section_text = section_text.lstrip(":").lstrip("-").lstrip().lstrip("\n")
            parts.append((title, section_text))
            remaining = remaining[next_idx:]

    if not parts:
        # Fallback: wrap entire narrative in a single section
        escaped = narrative.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return (
            '<div class="desk-note-section">'
            '<div class="desk-note-text">'
            + escaped.replace("\n", "<br>")
            + "</div></div>"
        )

    html_parts: list[str] = []
    for title, text in parts:
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_parts.append(
            f'<div class="desk-note-section">'
            f'<div class="desk-note-section-title">{title}</div>'
            f'<div class="desk-note-text">{escaped.replace(chr(10), "<br>")}</div>'
            f"</div>"
        )

    return "\n".join(html_parts)


# ---------------------------------------------------------------------------
# _json_serializer — custom JSON serializer for numpy/pandas types
# ---------------------------------------------------------------------------


def _json_serializer(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _to_json(obj: Any) -> str:
    """Serialize an object to a compact JSON string."""
    return json.dumps(obj, default=_json_serializer, ensure_ascii=False)


# ---------------------------------------------------------------------------
# build_dashboard
# ---------------------------------------------------------------------------


def build_dashboard(
    target_date: date,
    metrics: MetricsResult,
    market_data: MarketData,
    narrative: str,
    prompt_log_entry: Optional[dict[str, Any]],
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    """Build and write the self-contained HTML dashboard.

    Renders the HTML template from
    :mod:`euro_risk_pack.dashboard.template` using
    :class:`string.Template` with ``$``-syntax substitution.  All chart
    data is embedded as JSON in ``<script>`` blocks so the dashboard is
    fully self-contained.

    Args:
        target_date: The market date the dashboard covers.
        metrics: Computed :class:`MetricsResult` with all 7 metric keys.
        market_data: Complete :class:`MarketData` from the ingestion layer.
        narrative: The LLM-generated (or fallback) narrative text.
        prompt_log_entry: The most recent prompt log entry dict, or
            ``None`` if unavailable.
        output_dir: Directory to write the HTML file into.  Defaults to
            :data:`euro_risk_pack.config.OUTPUT_DIR`.

    Returns:
        The :class:`Path` to the written HTML file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = target_date.isoformat()
    output_path = output_dir / f"dashboard_{date_str}.html"

    # Prepare chart data
    chart_data = prepare_chart_data(market_data)

    # Format metric cards
    metric_cards = format_metric_cards(metrics)

    # Format trading signals
    signals = _format_signals(metrics)

    # Format narrative HTML
    narrative_html = _format_narrative_html(narrative)

    # Prepare prompt log (sanitize for JSON embedding)
    prompt_log = prompt_log_entry if prompt_log_entry is not None else {}

    # Build run timestamp
    run_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Render template using string.Template $-syntax
    template = Template(DASHBOARD_TEMPLATE)
    html_content = template.safe_substitute(
        date=date_str,
        metrics_json=_to_json(metric_cards),
        ttf_series_json=_to_json(chart_data["ttf_series"]),
        eua_series_json=_to_json(chart_data["eua_series"]),
        dates_ttf_json=_to_json(chart_data["dates_ttf"]),
        dates_eua_json=_to_json(chart_data["dates_eua"]),
        storage_series_json=_to_json(chart_data["storage_series"]),
        storage_avg_json=_to_json(chart_data["storage_avg"]),
        dates_storage_json=_to_json(chart_data["dates_storage"]),
        spread_series_json=_to_json(chart_data["spread_series"]),
        dates_spread_json=_to_json(chart_data["dates_spread"]),
        narrative_html=narrative_html,
        prompt_log_json=_to_json(prompt_log),
        signals_json=_to_json(signals),
        analyst_name=ANALYST_NAME,
        analyst_email=ANALYST_EMAIL,
        run_timestamp=run_timestamp,
        version=VERSION,
    )

    output_path.write_text(html_content, encoding="utf-8")
    logger.info("Dashboard written to %s", output_path)

    return output_path
