"""Desk note report builder for the European Cross-Commodity Risk Pack.

Assembles a structured markdown desk note from computed metrics, an
LLM-generated (or fallback) narrative, and chart image paths.  Optionally
converts the markdown to PDF via *weasyprint*.

Public API:

- :func:`build_markdown` — generates the full markdown string.
- :func:`markdown_to_pdf` — converts markdown to PDF via weasyprint.
- :func:`build_desk_note` — writes both ``.md`` and ``.pdf`` to disk.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from euro_risk_pack.config import ANALYST_EMAIL, ANALYST_NAME, OUTPUT_DIR, VERSION
from euro_risk_pack.metrics.definitions import METRIC_DEFINITIONS
from euro_risk_pack.models import MetricsResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data sources listed in the footer
# ---------------------------------------------------------------------------

_DATA_SOURCES: list[str] = [
    "Yahoo Finance",
    "AGSI+",
    "ENTSO-E",
    "Ember",
    "GIE ALSI",
]


# ---------------------------------------------------------------------------
# build_markdown
# ---------------------------------------------------------------------------


def build_markdown(
    target_date: date,
    metrics: MetricsResult,
    narrative: str,
    chart_paths: list[Path],
) -> str:
    """Generate the full markdown content for the desk note.

    The document is structured as:

    1. **Header** — report date, analyst name/email, version.
    2. **Metrics table** — all 7 metrics with value, unit, and signal.
    3. **Narrative** — LLM-generated (or fallback) analysis.
    4. **Charts** — markdown image references for each chart PNG.
    5. **Footer** — data sources and pipeline run timestamp.

    Args:
        target_date: The market date the report covers.
        metrics: Computed :class:`MetricsResult` with all 7 metric keys.
        narrative: The LLM narrative text (may include ``[FALLBACK MODE]``
            prefix).
        chart_paths: List of :class:`Path` objects pointing to generated
            chart PNG files.

    Returns:
        A complete markdown string ready to be written to disk or converted
        to PDF.
    """
    sections: list[str] = []

    # ---- Header ----------------------------------------------------------
    header = (
        f"# European Cross-Commodity Risk Pack — Desk Note\n\n"
        f"**Date:** {target_date.isoformat()}\n\n"
        f"**Analyst:** {ANALYST_NAME} ({ANALYST_EMAIL})\n\n"
        f"**Version:** {VERSION}\n\n"
        f"---\n"
    )
    sections.append(header)

    # ---- Metrics table ---------------------------------------------------
    table_lines: list[str] = [
        "## Metrics Summary\n",
        "| Metric | Value | Unit | Signal |",
        "|--------|-------|------|--------|",
    ]

    for key, definition in METRIC_DEFINITIONS.items():
        result = metrics.get(key)  # type: ignore[arg-type]
        if result is None:
            continue
        value_str = f"{result['value']:.2f}"
        unit = definition.unit if definition.unit else "—"
        signal = result["signal"]
        table_lines.append(f"| {definition.name} | {value_str} | {unit} | {signal} |")

    table_lines.append("")  # trailing blank line
    sections.append("\n".join(table_lines))

    # ---- Narrative -------------------------------------------------------
    narrative_section = (
        f"## Market Narrative\n\n"
        f"{narrative}\n"
    )
    sections.append(narrative_section)

    # ---- Chart references ------------------------------------------------
    chart_lines: list[str] = ["## Charts\n"]
    for chart_path in chart_paths:
        caption = chart_path.stem.replace("_", " ").title()
        chart_lines.append(f"![{caption}]({chart_path})\n")
    sections.append("\n".join(chart_lines))

    # ---- Footer ----------------------------------------------------------
    sources_str = ", ".join(_DATA_SOURCES)
    run_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    footer = (
        f"---\n\n"
        f"## Footer\n\n"
        f"**Data Sources:** {sources_str}\n\n"
        f"**Run Timestamp:** {run_timestamp}\n"
    )
    sections.append(footer)

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# markdown_to_pdf
# ---------------------------------------------------------------------------


def markdown_to_pdf(md_content: str, output_path: Path) -> Optional[Path]:
    """Convert a markdown string to PDF via *weasyprint*.

    The markdown is first rendered to HTML using Python's :mod:`markdown`
    library, then wrapped in a minimal HTML document with table styling
    before being passed to weasyprint for PDF generation.

    Args:
        md_content: The markdown text to convert.
        output_path: Destination path for the PDF file.

    Returns:
        The *output_path* on success, or ``None`` if PDF generation fails.
    """
    try:
        import markdown as md_lib  # noqa: F811
        from weasyprint import HTML

        html_body = md_lib.markdown(md_content, extensions=["tables"])

        html_doc = (
            "<!DOCTYPE html>\n"
            "<html><head><meta charset='utf-8'>\n"
            "<style>\n"
            "  body { font-family: 'IBM Plex Sans', Arial, sans-serif;\n"
            "         font-size: 12px; color: #222; margin: 40px; }\n"
            "  h1 { font-size: 20px; }\n"
            "  h2 { font-size: 16px; margin-top: 24px; }\n"
            "  table { border-collapse: collapse; width: 100%;\n"
            "          margin: 16px 0; }\n"
            "  th, td { border: 1px solid #30363d; padding: 6px 12px;\n"
            "           text-align: left; }\n"
            "  th { background-color: #161b22; color: #c9d1d9; }\n"
            "  img { max-width: 100%; height: auto; }\n"
            "  hr { border: none; border-top: 1px solid #30363d;\n"
            "       margin: 24px 0; }\n"
            "</style>\n"
            "</head><body>\n"
            f"{html_body}\n"
            "</body></html>"
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html_doc).write_pdf(str(output_path))
        logger.info("PDF desk note written to %s", output_path)
        return output_path

    except Exception:
        logger.exception("PDF generation failed for %s", output_path)
        return None


# ---------------------------------------------------------------------------
# build_desk_note
# ---------------------------------------------------------------------------


def build_desk_note(
    target_date: date,
    metrics: MetricsResult,
    narrative: str,
    chart_paths: list[Path],
    output_dir: Path = OUTPUT_DIR,
) -> tuple[Path, Optional[Path]]:
    """Build the desk note as markdown and (optionally) PDF.

    Writes the markdown file first, then attempts PDF conversion.  If PDF
    generation fails the markdown file is still produced and the error is
    logged.

    Args:
        target_date: The market date the report covers.
        metrics: Computed :class:`MetricsResult` with all 7 metric keys.
        narrative: The LLM narrative text.
        chart_paths: List of :class:`Path` objects for chart PNGs.
        output_dir: Directory to write output files into.  Defaults to
            :data:`euro_risk_pack.config.OUTPUT_DIR`.

    Returns:
        A tuple ``(md_path, pdf_path)`` where *pdf_path* is ``None`` if
        PDF generation failed.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = target_date.isoformat()
    md_path = output_dir / f"desk_note_{date_str}.md"
    pdf_path = output_dir / f"desk_note_{date_str}.pdf"

    # ---- Generate markdown -----------------------------------------------
    md_content = build_markdown(target_date, metrics, narrative, chart_paths)
    md_path.write_text(md_content, encoding="utf-8")
    logger.info("Markdown desk note written to %s", md_path)

    # ---- Attempt PDF conversion ------------------------------------------
    pdf_result = markdown_to_pdf(md_content, pdf_path)

    return md_path, pdf_result
