"""Chart generation for the European Cross-Commodity Risk Pack.

Produces three Matplotlib PNG charts from market data and metrics:

1. **TTF / EUA 30-day dual-axis line chart** — TTF on the left axis
   (blue) and EUA on the right axis (amber).
2. **Storage vs seasonal area chart** — current fill level vs the
   5-year average band.
3. **Dark spread / clean spark spread grouped bar chart** — side-by-side
   bars over the last 20 trading days.

All charts use a dark background style consistent with the dashboard
aesthetic and accent colours defined in :mod:`euro_risk_pack.config`.

The :func:`generate_all_charts` orchestrator calls each chart generator
inside a ``try/except`` block.  On failure it writes a 1×1 pixel
placeholder PNG so that downstream components (desk note, dashboard)
never encounter a missing image reference.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend — must be set before pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from euro_risk_pack.config import (
    CHART_DIR,
    COLORS,
    EMISSION_FACTOR,
    GAS_PLANT_EFFICIENCY,
)
from euro_risk_pack.models import MarketData, MetricsResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_dark_style() -> None:
    """Apply the dark background base style and customise further."""
    plt.style.use("dark_background")


def _create_placeholder_png(output_path: Path) -> Path:
    """Write a minimal 1×1 pixel PNG to *output_path*.

    Used as a fallback when chart rendering fails so that downstream
    components (desk note image references, dashboard ``<img>`` tags)
    never encounter a missing file.

    Parameters
    ----------
    output_path:
        Destination file path for the placeholder image.

    Returns
    -------
    Path
        The same *output_path*, now pointing to the written file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a small placeholder figure with a "no data" message
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.set_facecolor(COLORS["surface"])
    fig.patch.set_facecolor(COLORS["bg"])
    ax.text(
        0.5, 0.5, "No Data",
        ha="center", va="center",
        color=COLORS["text_muted"],
        fontsize=8,
        transform=ax.transAxes,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.savefig(output_path, dpi=10, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Chart 1: TTF / EUA dual-axis line chart
# ---------------------------------------------------------------------------


def generate_ttf_eua_chart(
    ttf_series: pd.Series,
    eua_series: pd.Series,
    target_date: date,
    output_path: Path,
) -> Path:
    """Generate a dual-axis line chart for TTF and EUA prices.

    TTF prices are plotted on the left y-axis in blue (#58a6ff) and EUA
    prices on the right y-axis in amber (#f0883e).  Both series share
    the same x-axis (dates).

    Parameters
    ----------
    ttf_series:
        30-day TTF price series with :class:`~pandas.DatetimeIndex`.
    eua_series:
        30-day EUA price series with :class:`~pandas.DatetimeIndex`.
    target_date:
        Reference date used in the chart title.
    output_path:
        Destination file path for the PNG image.

    Returns
    -------
    Path
        The *output_path* where the chart was saved.
    """
    _apply_dark_style()

    fig, ax1 = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(COLORS["bg"])
    ax1.set_facecolor(COLORS["surface"])

    # TTF on left axis
    color_ttf = COLORS["ttf"]
    ax1.plot(
        ttf_series.index,
        ttf_series.values,
        color=color_ttf,
        linewidth=1.8,
        label="TTF DA (EUR/MWh)",
    )
    ax1.set_ylabel("TTF (EUR/MWh)", color=color_ttf, fontsize=10)
    ax1.tick_params(axis="y", labelcolor=color_ttf, labelsize=8)
    ax1.tick_params(axis="x", labelsize=8)

    # EUA on right axis
    ax2 = ax1.twinx()
    color_eua = COLORS["eua"]
    ax2.plot(
        eua_series.index,
        eua_series.values,
        color=color_eua,
        linewidth=1.8,
        label="EUA (EUR/tCO₂)",
    )
    ax2.set_ylabel("EUA (EUR/tCO₂)", color=color_eua, fontsize=10)
    ax2.tick_params(axis="y", labelcolor=color_eua, labelsize=8)

    # Title and formatting
    ax1.set_title(
        f"TTF Gas vs EUA Carbon — 30 Day ({target_date.isoformat()})",
        color=COLORS["text"],
        fontsize=12,
        pad=12,
    )

    # X-axis date formatting
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax1.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    fig.autofmt_xdate(rotation=30, ha="right")

    # Grid
    ax1.grid(True, alpha=0.15, color=COLORS["border"])
    ax1.set_axisbelow(True)

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(
        lines1 + lines2,
        labels1 + labels2,
        loc="upper left",
        fontsize=8,
        facecolor=COLORS["surface"],
        edgecolor=COLORS["border"],
        labelcolor=COLORS["text"],
    )

    # Spine styling
    for spine in ax1.spines.values():
        spine.set_color(COLORS["border"])
    for spine in ax2.spines.values():
        spine.set_color(COLORS["border"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)
    logger.info("Saved TTF/EUA chart to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Chart 2: Storage vs seasonal area chart
# ---------------------------------------------------------------------------


def generate_storage_chart(
    storage_series: pd.DataFrame,
    target_date: date,
    output_path: Path,
) -> Path:
    """Generate an area chart of current storage fill vs 5-year average.

    The current fill level is drawn as a filled area in the TTF accent
    colour and the 5-year average as a dashed line with a translucent
    band.

    Parameters
    ----------
    storage_series:
        DataFrame with columns ``date``, ``current_pct``, and
        ``avg_5yr_pct``.
    target_date:
        Reference date used in the chart title.
    output_path:
        Destination file path for the PNG image.

    Returns
    -------
    Path
        The *output_path* where the chart was saved.
    """
    _apply_dark_style()

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["surface"])

    dates = pd.to_datetime(storage_series["date"])
    current_pct = storage_series["current_pct"].values
    avg_5yr_pct = storage_series["avg_5yr_pct"].values

    # 5-year average band (±2 pp for visual effect)
    band_width = 2.0
    ax.fill_between(
        dates,
        avg_5yr_pct - band_width,
        avg_5yr_pct + band_width,
        alpha=0.15,
        color=COLORS["text_muted"],
        label="5yr Avg ±2pp",
    )
    ax.plot(
        dates,
        avg_5yr_pct,
        color=COLORS["text_muted"],
        linewidth=1.2,
        linestyle="--",
        label="5yr Average",
    )

    # Current fill area
    ax.fill_between(
        dates,
        0,
        current_pct,
        alpha=0.35,
        color=COLORS["power"],
    )
    ax.plot(
        dates,
        current_pct,
        color=COLORS["power"],
        linewidth=1.8,
        label="Current Fill",
    )

    # Title and labels
    ax.set_title(
        f"EU Gas Storage — Fill vs 5yr Seasonal ({target_date.isoformat()})",
        color=COLORS["text"],
        fontsize=12,
        pad=12,
    )
    ax.set_ylabel("Fill Level (%)", color=COLORS["text"], fontsize=10)
    ax.set_ylim(0, 100)
    ax.tick_params(axis="both", labelsize=8)

    # X-axis date formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    fig.autofmt_xdate(rotation=30, ha="right")

    # Grid
    ax.grid(True, alpha=0.15, color=COLORS["border"])
    ax.set_axisbelow(True)

    # Legend
    ax.legend(
        loc="upper left",
        fontsize=8,
        facecolor=COLORS["surface"],
        edgecolor=COLORS["border"],
        labelcolor=COLORS["text"],
    )

    # Spine styling
    for spine in ax.spines.values():
        spine.set_color(COLORS["border"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)
    logger.info("Saved storage chart to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Chart 3: Dark spread / clean spark spread grouped bar chart
# ---------------------------------------------------------------------------


def generate_spread_chart(
    dark_spread_series: pd.Series,
    spark_spread_series: pd.Series,
    target_date: date,
    output_path: Path,
) -> Path:
    """Generate a grouped bar chart of dark spread vs clean spark spread.

    Each trading day gets two side-by-side bars: dark spread (EUA amber)
    and clean spark spread (power green).

    Parameters
    ----------
    dark_spread_series:
        20-day dark spread series with :class:`~pandas.DatetimeIndex`.
    spark_spread_series:
        20-day clean spark spread series with :class:`~pandas.DatetimeIndex`.
    target_date:
        Reference date used in the chart title.
    output_path:
        Destination file path for the PNG image.

    Returns
    -------
    Path
        The *output_path* where the chart was saved.
    """
    _apply_dark_style()

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["surface"])

    n = len(dark_spread_series)
    x = np.arange(n)
    bar_width = 0.35

    # Dark spread bars
    ax.bar(
        x - bar_width / 2,
        dark_spread_series.values,
        bar_width,
        color=COLORS["eua"],
        alpha=0.85,
        label="Dark Spread",
    )

    # Clean spark spread bars
    ax.bar(
        x + bar_width / 2,
        spark_spread_series.values,
        bar_width,
        color=COLORS["power"],
        alpha=0.85,
        label="Clean Spark Spread",
    )

    # Zero line
    ax.axhline(y=0, color=COLORS["border"], linewidth=0.8, linestyle="-")

    # Title and labels
    ax.set_title(
        f"Dark Spread vs Clean Spark Spread — 20 Day ({target_date.isoformat()})",
        color=COLORS["text"],
        fontsize=12,
        pad=12,
    )
    ax.set_ylabel("Spread (EUR/MWh)", color=COLORS["text"], fontsize=10)
    ax.tick_params(axis="both", labelsize=8)

    # X-axis labels — use dates from the series
    date_labels = [d.strftime("%d %b") for d in dark_spread_series.index]
    ax.set_xticks(x)
    ax.set_xticklabels(date_labels, rotation=45, ha="right", fontsize=7)

    # Grid
    ax.grid(True, axis="y", alpha=0.15, color=COLORS["border"])
    ax.set_axisbelow(True)

    # Legend
    ax.legend(
        loc="upper left",
        fontsize=8,
        facecolor=COLORS["surface"],
        edgecolor=COLORS["border"],
        labelcolor=COLORS["text"],
    )

    # Spine styling
    for spine in ax.spines.values():
        spine.set_color(COLORS["border"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)
    logger.info("Saved spread chart to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Orchestrator: generate_all_charts
# ---------------------------------------------------------------------------


def generate_all_charts(
    data: MarketData,
    metrics: MetricsResult,
    target_date: date,
    output_dir: Path = CHART_DIR,
) -> list[Path]:
    """Generate all three charts, returning a list of output file paths.

    Each chart generator is called inside a ``try/except`` block.  On
    failure a 1×1 pixel placeholder PNG is written so that downstream
    components (desk note, dashboard) never encounter a missing image
    reference.

    Parameters
    ----------
    data:
        Complete :class:`MarketData` dictionary from the ingestion layer.
    metrics:
        Complete :class:`MetricsResult` from the metrics calculator.
    target_date:
        Reference date for chart titles and file naming.
    output_dir:
        Directory where chart PNGs are written.  Defaults to
        ``outputs/charts``.

    Returns
    -------
    list[Path]
        A list of exactly three :class:`Path` objects pointing to the
        generated (or placeholder) PNG files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    chart_paths: list[Path] = []

    # --- Chart 1: TTF / EUA dual-axis line chart ----------------------
    ttf_eua_path = output_dir / "ttf_eua_30d.png"
    try:
        generate_ttf_eua_chart(
            ttf_series=data["ttf_series"],
            eua_series=data["eua_series"],
            target_date=target_date,
            output_path=ttf_eua_path,
        )
    except Exception:
        logger.exception("Failed to generate TTF/EUA chart")
        _create_placeholder_png(ttf_eua_path)
    chart_paths.append(ttf_eua_path)

    # --- Chart 2: Storage vs seasonal area chart ----------------------
    storage_path = output_dir / "storage_vs_seasonal.png"
    try:
        generate_storage_chart(
            storage_series=data["storage_series"],
            target_date=target_date,
            output_path=storage_path,
        )
    except Exception:
        logger.exception("Failed to generate storage chart")
        _create_placeholder_png(storage_path)
    chart_paths.append(storage_path)

    # --- Chart 3: Dark spread / clean spark spread bar chart ----------
    spread_path = output_dir / "dark_spread_spark_spread.png"
    try:
        # Compute spread series from the power series and metric parameters
        de_power_series: pd.Series = data["de_power_series"]
        ttf_series: pd.Series = data["ttf_series"]
        eua_series: pd.Series = data["eua_series"]

        # Align TTF and EUA to the power series dates (20 days)
        # Use the last N values from TTF/EUA to match power series length
        power_dates = de_power_series.index
        n_power = len(power_dates)

        # Reindex TTF and EUA to power dates, forward-filling gaps
        ttf_aligned = ttf_series.reindex(power_dates, method="ffill")
        eua_aligned = eua_series.reindex(power_dates, method="ffill")

        # If reindex left NaNs (dates before TTF/EUA series start),
        # back-fill as a last resort
        ttf_aligned = ttf_aligned.bfill()
        eua_aligned = eua_aligned.bfill()

        # Compute spreads element-wise
        efficiency = GAS_PLANT_EFFICIENCY
        emission_factor = EMISSION_FACTOR

        dark_spread_series = de_power_series - (
            ttf_aligned / efficiency + eua_aligned * emission_factor
        )
        dark_spread_series.name = "dark_spread"

        spark_spread_series = de_power_series - (
            ttf_aligned / efficiency + eua_aligned * emission_factor
        )
        spark_spread_series.name = "spark_spread"

        generate_spread_chart(
            dark_spread_series=dark_spread_series,
            spark_spread_series=spark_spread_series,
            target_date=target_date,
            output_path=spread_path,
        )
    except Exception:
        logger.exception("Failed to generate spread chart")
        _create_placeholder_png(spread_path)
    chart_paths.append(spread_path)

    return chart_paths
