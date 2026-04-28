"""CLI entry point and pipeline orchestrator for the European Cross-Commodity Risk Pack.

Parses command-line arguments, creates output directories, and runs the full
pipeline: data ingestion → metric calculation → chart generation → LLM
narrative → desk note → HTML dashboard → stdout summary.

Usage::

    python -m euro_risk_pack.main --date 2024-01-15
    python -m euro_risk_pack.main --mock
    python -m euro_risk_pack.main --date 2024-01-15 --mock

Functions
---------
parse_args()
    Parse ``--date`` and ``--mock`` CLI arguments.
ensure_output_dirs()
    Create ``outputs/`` and ``outputs/charts/`` if they don't exist.
run(target_date, mock)
    Execute the full pipeline end-to-end.
main()
    CLI entry point that wires argument parsing to the pipeline runner.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from euro_risk_pack.config import CHART_DIR, OUTPUT_DIR


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------


def _configure_logging() -> None:
    """Configure root logger to write to ``outputs/run.log`` with timestamps.

    Also attaches a stderr handler at WARNING level so critical issues
    are visible on the console.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT_DIR / "run.log"

    # File handler — DEBUG and above
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Console handler — WARNING and above
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    # Avoid duplicate handlers on repeated calls
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the European Risk Pack pipeline.

    Parameters
    ----------
    argv:
        Argument list to parse.  Defaults to ``sys.argv[1:]`` when
        ``None``.

    Returns
    -------
    argparse.Namespace
        Namespace with ``date`` (:class:`datetime.date`) and ``mock``
        (bool) attributes.

    Raises
    ------
    SystemExit
        Exits with code 1 and prints usage when the date string is
        invalid.
    """
    parser = argparse.ArgumentParser(
        prog="euro_risk_pack",
        description=(
            "European Cross-Commodity Risk Pack — daily energy market "
            "monitor.  Ingests TTF gas, EUA carbon, DE/FR power, and gas "
            "storage data, computes 7 risk metrics, generates charts, "
            "produces an LLM desk note, and assembles an HTML dashboard."
        ),
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD format (default: today).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="Use synthetic mock data instead of live API calls.",
    )

    # Override exit code so argparse errors use code 1 per requirements
    parser.exit = lambda status=0, message=None: (  # type: ignore[assignment]
        sys.stderr.write(message) if message else None,
        sys.exit(1 if status != 0 else 0),
    )

    args = parser.parse_args(argv)

    # Resolve date
    if args.date is None:
        args.date = date.today()
    else:
        try:
            args.date = date.fromisoformat(args.date)
        except ValueError:
            parser.error(
                f"Invalid date format: '{args.date}'. "
                "Expected YYYY-MM-DD (e.g. 2024-01-15)."
            )

    return args


# ---------------------------------------------------------------------------
# Output directory creation
# ---------------------------------------------------------------------------


def ensure_output_dirs() -> None:
    """Create ``outputs/`` and ``outputs/charts/`` directories if missing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


def run(target_date: date, mock: bool) -> None:
    """Execute the full European Risk Pack pipeline.

    Steps:
      1. Ingest market data (or generate mock data).
      2. Calculate all 7 metrics.
      3. Generate 3 PNG charts.
      4. Build prompt and call Claude API (or fallback) for narrative.
      5. Write desk note (Markdown + PDF).
      6. Write HTML dashboard.
      7. Print summary to stdout.

    All errors are logged to ``outputs/run.log``.  Unhandled exceptions
    are caught at the top level so the pipeline exits gracefully.

    Parameters
    ----------
    target_date:
        The market date to run the pipeline for.
    mock:
        If ``True``, use synthetic data and skip live API calls.
    """
    logger = logging.getLogger("euro_risk_pack.main")
    logger.info(
        "=== European Risk Pack pipeline started for %s (mock=%s) ===",
        target_date.isoformat(),
        mock,
    )

    # ------------------------------------------------------------------
    # 1. Ingest data
    # ------------------------------------------------------------------
    logger.info("Step 1/7: Ingesting market data …")
    from euro_risk_pack.data.ingest import ingest_all

    market_data = ingest_all(target_date, mock=mock)
    logger.info("Data ingestion complete.")

    # ------------------------------------------------------------------
    # 2. Calculate metrics
    # ------------------------------------------------------------------
    logger.info("Step 2/7: Calculating metrics …")
    from euro_risk_pack.metrics.calculator import calculate_all_metrics

    metrics = calculate_all_metrics(market_data)
    logger.info("Metrics calculation complete.")

    # ------------------------------------------------------------------
    # 3. Generate charts
    # ------------------------------------------------------------------
    logger.info("Step 3/7: Generating charts …")
    from euro_risk_pack.charts.generator import generate_all_charts

    chart_paths = generate_all_charts(
        data=market_data,
        metrics=metrics,
        target_date=target_date,
        output_dir=CHART_DIR,
    )
    logger.info("Chart generation complete (%d charts).", len(chart_paths))

    # ------------------------------------------------------------------
    # 4. Build prompt and call LLM
    # ------------------------------------------------------------------
    logger.info("Step 4/7: Generating narrative …")
    from euro_risk_pack.narrative.prompt_builder import build_prompt, build_system_prompt
    from euro_risk_pack.narrative.llm_client import call_claude

    user_prompt = build_prompt(metrics)
    system_prompt = build_system_prompt()
    narrative = call_claude(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        metrics=metrics,
    )
    logger.info("Narrative generation complete.")

    # ------------------------------------------------------------------
    # 5. Write desk note (MD + PDF)
    # ------------------------------------------------------------------
    logger.info("Step 5/7: Building desk note …")
    from euro_risk_pack.report.builder import build_desk_note

    md_path, pdf_path = build_desk_note(
        target_date=target_date,
        metrics=metrics,
        narrative=narrative,
        chart_paths=chart_paths,
        output_dir=OUTPUT_DIR,
    )
    logger.info("Desk note written: MD=%s, PDF=%s", md_path, pdf_path)

    # ------------------------------------------------------------------
    # 6. Write HTML dashboard
    # ------------------------------------------------------------------
    logger.info("Step 6/7: Building dashboard …")
    from euro_risk_pack.narrative.logger import read_latest_log_entry
    from euro_risk_pack.dashboard.builder import build_dashboard

    prompt_log_entry = read_latest_log_entry()
    dashboard_path = build_dashboard(
        target_date=target_date,
        metrics=metrics,
        market_data=market_data,
        narrative=narrative,
        prompt_log_entry=prompt_log_entry,
        output_dir=OUTPUT_DIR,
    )
    logger.info("Dashboard written: %s", dashboard_path)

    # ------------------------------------------------------------------
    # 7. Print summary to stdout
    # ------------------------------------------------------------------
    logger.info("Step 7/7: Printing summary …")
    _print_summary(
        target_date=target_date,
        mock=mock,
        metrics=metrics,
        chart_paths=chart_paths,
        md_path=md_path,
        pdf_path=pdf_path,
        dashboard_path=dashboard_path,
    )

    logger.info("=== Pipeline completed successfully ===")


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def _print_summary(
    target_date: date,
    mock: bool,
    metrics: dict,
    chart_paths: list[Path],
    md_path: Path,
    pdf_path: Optional[Path],
    dashboard_path: Path,
) -> None:
    """Print a human-readable summary to stdout.

    Lists all generated output files, a table of metric values with
    signals, and a signal summary line.

    Parameters
    ----------
    target_date:
        The market date the pipeline ran for.
    mock:
        Whether mock mode was used.
    metrics:
        The computed :class:`MetricsResult` dictionary.
    chart_paths:
        List of chart PNG file paths.
    md_path:
        Path to the generated Markdown desk note.
    pdf_path:
        Path to the generated PDF desk note, or ``None`` if PDF failed.
    dashboard_path:
        Path to the generated HTML dashboard.
    """
    from euro_risk_pack.metrics.definitions import METRIC_DEFINITIONS

    sep = "=" * 64
    print()
    print(sep)
    print("  EUROPEAN CROSS-COMMODITY RISK PACK — RUN SUMMARY")
    print(sep)
    print(f"  Date:       {target_date.isoformat()}")
    print(f"  Mode:       {'MOCK' if mock else 'LIVE'}")
    print(f"  Timestamp:  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    # --- Metrics table ---
    print("  METRICS")
    print("  " + "-" * 60)
    print(f"  {'Metric':<30s} {'Value':>12s}  {'Signal':<10s}")
    print("  " + "-" * 60)

    for key, defn in METRIC_DEFINITIONS.items():
        result = metrics.get(key)
        if result is None:
            continue
        print(f"  {defn.short_name:<30s} {result['formatted']:>12s}  {result['signal']:<10s}")

    print("  " + "-" * 60)

    # --- Signal summary ---
    signals = [r["signal"] for r in metrics.values() if isinstance(r, dict)]
    bullish = signals.count("BULLISH")
    bearish = signals.count("BEARISH")
    neutral = signals.count("NEUTRAL")
    alert = signals.count("ALERT")
    print()
    print(
        f"  Signals: {bullish} BULLISH | {bearish} BEARISH | "
        f"{neutral} NEUTRAL | {alert} ALERT"
    )

    # --- Output files ---
    print()
    print("  OUTPUT FILES")
    print("  " + "-" * 60)
    for cp in chart_paths:
        print(f"  Chart:      {cp}")
    print(f"  Desk Note:  {md_path}")
    if pdf_path is not None:
        print(f"  PDF:        {pdf_path}")
    else:
        print("  PDF:        (generation failed — see run.log)")
    print(f"  Dashboard:  {dashboard_path}")
    print(f"  Run Log:    {OUTPUT_DIR / 'run.log'}")
    print(f"  Prompt Log: {OUTPUT_DIR / 'prompts_log.jsonl'}")
    print(sep)
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> None:
    """CLI entry point for the European Risk Pack.

    Parses arguments, configures logging, ensures output directories
    exist, and runs the pipeline.  Catches all unhandled exceptions,
    logs them, and exits with code 1.

    Parameters
    ----------
    argv:
        Optional argument list (defaults to ``sys.argv[1:]``).
    """
    args = parse_args(argv)

    _configure_logging()
    ensure_output_dirs()

    logger = logging.getLogger("euro_risk_pack.main")

    try:
        run(target_date=args.date, mock=args.mock)
    except Exception:
        logger.exception("Unhandled exception in pipeline")
        print(
            "\nERROR: Pipeline failed — see outputs/run.log for details.",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Allow `python -m euro_risk_pack.main`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
