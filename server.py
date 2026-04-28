"""Flask web server for the European Cross-Commodity Risk Pack.

Provides a live interactive dashboard with SSE streaming for narrative
generation, per-component refresh endpoints, and download routes for
the desk note and self-contained HTML dashboard.

Usage::

    python -m euro_risk_pack.server
    # or
    from euro_risk_pack.server import app
    app.run()
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
import webbrowser
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Generator

from flask import Flask, Response, jsonify, render_template, send_file, send_from_directory

from euro_risk_pack.config import (
    AUTO_OPEN_BROWSER,
    CHART_DIR,
    COLORS,
    OUTPUT_DIR,
    SERVER_HOST,
    SERVER_PORT,
    VERSION,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure root logger for the server process."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT_DIR / "server.log"

    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)

# ---------------------------------------------------------------------------
# Shared state (thread-safe)
# ---------------------------------------------------------------------------

_state: dict[str, Any] = {
    "market_data": None,
    "metrics": None,
    "narrative": None,
    "chart_paths": None,
    "prompt_log": None,
    "last_run": None,
    "is_running": False,
    "mock_mode": True,
    "error": None,
}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_serial(obj: Any) -> Any:
    """Custom JSON serializer for non-standard types."""
    import numpy as np
    import pandas as pd

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
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _to_json(obj: Any) -> str:
    """Serialize to compact JSON string."""
    return json.dumps(obj, default=_json_serial, ensure_ascii=False)


def _error_response(message: str, status_code: int = 500) -> tuple:
    """Return a JSON error response."""
    return jsonify({
        "error": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), status_code


def _sse_event(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data, default=_json_serial, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _get_target_date() -> date:
    """Return today's date as the pipeline target."""
    return date.today()


def _run_ingest(mock: bool = True) -> dict:
    """Run data ingestion and return market_data."""
    from euro_risk_pack.data.ingest import ingest_all

    target_date = _get_target_date()
    return ingest_all(target_date, mock=mock)


def _run_metrics(market_data: dict) -> dict:
    """Calculate all metrics from market data."""
    from euro_risk_pack.metrics.calculator import calculate_all_metrics

    return calculate_all_metrics(market_data)


def _run_charts(market_data: dict, metrics: dict) -> list[Path]:
    """Generate all charts and return paths."""
    from euro_risk_pack.charts.generator import generate_all_charts

    target_date = _get_target_date()
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    return generate_all_charts(
        data=market_data,
        metrics=metrics,
        target_date=target_date,
        output_dir=CHART_DIR,
    )


def _run_narrative(metrics: dict) -> str:
    """Generate narrative via Claude (non-streaming)."""
    from euro_risk_pack.narrative.llm_client import call_claude
    from euro_risk_pack.narrative.prompt_builder import build_prompt, build_system_prompt

    user_prompt = build_prompt(metrics)
    system_prompt = build_system_prompt()
    return call_claude(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        metrics=metrics,
    )


def _build_dashboard_data() -> dict[str, Any]:
    """Build the dashboard data payload from current state."""
    from euro_risk_pack.dashboard.builder import format_metric_cards, prepare_chart_data
    from euro_risk_pack.narrative.logger import read_latest_log_entry

    with _lock:
        market_data = _state["market_data"]
        metrics = _state["metrics"]
        narrative = _state["narrative"]
        last_run = _state["last_run"]
        mock_mode = _state["mock_mode"]

    if market_data is None or metrics is None:
        return {
            "metrics": [],
            "chart_data": {},
            "narrative": "",
            "prompt_log": None,
            "last_run": None,
            "mock_mode": mock_mode,
            "version": VERSION,
            "colors": COLORS,
        }

    chart_data = prepare_chart_data(market_data)
    metric_cards = format_metric_cards(metrics)
    prompt_log = read_latest_log_entry()

    return {
        "metrics": metric_cards,
        "chart_data": chart_data,
        "narrative": narrative or "",
        "prompt_log": prompt_log,
        "last_run": last_run,
        "mock_mode": mock_mode,
        "version": VERSION,
        "colors": COLORS,
    }


def _run_full_pipeline(mock: bool = True) -> Generator[str, None, None]:
    """Run the full pipeline, yielding SSE progress events."""
    with _lock:
        if _state["is_running"]:
            yield _sse_event({"error": "Pipeline already running"})
            return
        _state["is_running"] = True
        _state["error"] = None

    try:
        # Step 1: Ingest
        yield _sse_event({"step": "ingest", "status": "running", "message": "Ingesting market data…"})
        market_data = _run_ingest(mock=mock)
        with _lock:
            _state["market_data"] = market_data
            _state["mock_mode"] = mock
        yield _sse_event({"step": "ingest", "status": "done", "message": "Market data ingested"})

        # Step 2: Metrics
        yield _sse_event({"step": "metrics", "status": "running", "message": "Calculating metrics…"})
        metrics = _run_metrics(market_data)
        with _lock:
            _state["metrics"] = metrics
        yield _sse_event({"step": "metrics", "status": "done", "message": "Metrics calculated"})

        # Step 3: Charts
        yield _sse_event({"step": "charts", "status": "running", "message": "Generating charts…"})
        chart_paths = _run_charts(market_data, metrics)
        with _lock:
            _state["chart_paths"] = chart_paths
        yield _sse_event({"step": "charts", "status": "done", "message": "Charts generated"})

        # Step 4: Narrative
        yield _sse_event({"step": "narrative", "status": "running", "message": "Generating narrative…"})
        narrative = _run_narrative(metrics)
        with _lock:
            _state["narrative"] = narrative
        yield _sse_event({"step": "narrative", "status": "done", "message": "Narrative generated"})

        # Step 5: Update timestamp
        now = datetime.now(timezone.utc).isoformat()
        with _lock:
            _state["last_run"] = now

        # Build final dashboard data for the client
        dashboard_data = _build_dashboard_data()
        yield _sse_event({
            "step": "complete",
            "status": "done",
            "message": "Pipeline complete",
            "dashboard_data": dashboard_data,
        })

    except Exception as exc:
        logger.exception("Pipeline failed")
        with _lock:
            _state["error"] = str(exc)
        yield _sse_event({"step": "error", "status": "failed", "message": str(exc)})
    finally:
        with _lock:
            _state["is_running"] = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Render the main dashboard page.

    On first load with no data, runs the pipeline in mock mode to populate
    the dashboard.
    """
    try:
        with _lock:
            has_data = _state["market_data"] is not None

        if not has_data:
            logger.info("First load — running mock pipeline to populate dashboard")
            market_data = _run_ingest(mock=True)
            metrics = _run_metrics(market_data)
            chart_paths = _run_charts(market_data, metrics)
            narrative = _run_narrative(metrics)
            now = datetime.now(timezone.utc).isoformat()

            with _lock:
                _state["market_data"] = market_data
                _state["metrics"] = metrics
                _state["chart_paths"] = chart_paths
                _state["narrative"] = narrative
                _state["last_run"] = now
                _state["mock_mode"] = True

        dashboard_data = _build_dashboard_data()
        dashboard_json = _to_json(dashboard_data)

        return render_template("index.html", dashboard_data=dashboard_json)

    except Exception as exc:
        logger.exception("Error rendering index")
        return _error_response(str(exc))


@app.route("/api/status")
def api_status():
    """Return current server status as JSON."""
    try:
        with _lock:
            return jsonify({
                "status": "running" if _state["is_running"] else "idle",
                "last_run": _state["last_run"],
                "mock_mode": _state["mock_mode"],
                "has_data": _state["market_data"] is not None,
                "error": _state["error"],
                "version": VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as exc:
        return _error_response(str(exc))


@app.route("/api/refresh/prices", methods=["POST"])
def refresh_prices():
    """Re-ingest market data and recalculate metrics."""
    try:
        with _lock:
            mock = _state["mock_mode"]

        market_data = _run_ingest(mock=mock)
        metrics = _run_metrics(market_data)

        with _lock:
            _state["market_data"] = market_data
            _state["metrics"] = metrics
            _state["last_run"] = datetime.now(timezone.utc).isoformat()

        from euro_risk_pack.dashboard.builder import format_metric_cards, prepare_chart_data

        return jsonify({
            "status": "ok",
            "metrics": format_metric_cards(metrics),
            "chart_data": prepare_chart_data(market_data),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.exception("refresh/prices failed")
        return _error_response(str(exc))


@app.route("/api/refresh/storage", methods=["POST"])
def refresh_storage():
    """Re-fetch storage data only and update metrics."""
    try:
        with _lock:
            mock = _state["mock_mode"]

        # Re-run full ingest (storage is part of the unified ingest)
        market_data = _run_ingest(mock=mock)
        metrics = _run_metrics(market_data)

        with _lock:
            _state["market_data"] = market_data
            _state["metrics"] = metrics

        from euro_risk_pack.dashboard.builder import prepare_chart_data

        chart_data = prepare_chart_data(market_data)
        return jsonify({
            "status": "ok",
            "storage_series": chart_data["storage_series"],
            "storage_avg": chart_data["storage_avg"],
            "dates_storage": chart_data["dates_storage"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.exception("refresh/storage failed")
        return _error_response(str(exc))


@app.route("/api/refresh/narrative", methods=["POST"])
def refresh_narrative():
    """Stream narrative generation via SSE."""
    try:
        with _lock:
            metrics = _state["metrics"]

        if metrics is None:
            return _error_response("No metrics available. Run pipeline first.", 400)

        from euro_risk_pack.narrative.llm_client import stream_claude
        from euro_risk_pack.narrative.prompt_builder import build_prompt, build_system_prompt

        user_prompt = build_prompt(metrics)
        system_prompt = build_system_prompt()

        def generate():
            full_text = ""
            try:
                for chunk in stream_claude(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    metrics=metrics,
                ):
                    full_text += chunk
                    yield _sse_event({"token": chunk})

                # Update state with complete narrative
                with _lock:
                    _state["narrative"] = full_text

                yield _sse_event({"done": True, "timestamp": datetime.now(timezone.utc).isoformat()})
            except Exception as exc:
                logger.exception("Narrative streaming failed")
                yield _sse_event({"error": str(exc)})

        return Response(generate(), content_type="text/event-stream")

    except Exception as exc:
        logger.exception("refresh/narrative failed")
        return _error_response(str(exc))


@app.route("/api/refresh/charts", methods=["POST"])
def refresh_charts():
    """Regenerate charts and return chart URLs."""
    try:
        with _lock:
            market_data = _state["market_data"]
            metrics = _state["metrics"]

        if market_data is None or metrics is None:
            return _error_response("No data available. Run pipeline first.", 400)

        chart_paths = _run_charts(market_data, metrics)

        with _lock:
            _state["chart_paths"] = chart_paths

        chart_urls = [f"/outputs/charts/{p.name}" for p in chart_paths]
        return jsonify({
            "status": "ok",
            "charts": chart_urls,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.exception("refresh/charts failed")
        return _error_response(str(exc))


@app.route("/api/refresh/all", methods=["POST"])
def refresh_all():
    """Run full pipeline with SSE progress streaming."""
    try:
        with _lock:
            mock = _state["mock_mode"]

        return Response(
            _run_full_pipeline(mock=mock),
            content_type="text/event-stream",
        )
    except Exception as exc:
        logger.exception("refresh/all failed")
        return _error_response(str(exc))


@app.route("/api/run/mock", methods=["POST"])
def run_mock():
    """Run full pipeline in mock mode with SSE progress streaming."""
    try:
        return Response(
            _run_full_pipeline(mock=True),
            content_type="text/event-stream",
        )
    except Exception as exc:
        logger.exception("run/mock failed")
        return _error_response(str(exc))


@app.route("/api/download/desk-note")
def download_desk_note():
    """Serve the latest desk note PDF or MD as a download."""
    try:
        target_date = _get_target_date()
        date_str = target_date.isoformat()

        # Try PDF first, then MD
        pdf_path = OUTPUT_DIR / f"desk_note_{date_str}.pdf"
        md_path = OUTPUT_DIR / f"desk_note_{date_str}.md"

        if pdf_path.exists():
            return send_file(
                str(pdf_path.resolve()),
                as_attachment=True,
                download_name=pdf_path.name,
            )
        elif md_path.exists():
            return send_file(
                str(md_path.resolve()),
                as_attachment=True,
                download_name=md_path.name,
            )
        else:
            # Generate desk note on the fly
            with _lock:
                metrics = _state["metrics"]
                narrative = _state["narrative"]
                chart_paths = _state["chart_paths"]

            if metrics is None:
                return _error_response("No data available. Run pipeline first.", 400)

            from euro_risk_pack.report.builder import build_desk_note

            md_result, pdf_result = build_desk_note(
                target_date=target_date,
                metrics=metrics,
                narrative=narrative or "",
                chart_paths=chart_paths or [],
                output_dir=OUTPUT_DIR,
            )

            serve_path = pdf_result if pdf_result else md_result
            return send_file(
                str(serve_path.resolve()),
                as_attachment=True,
                download_name=serve_path.name,
            )
    except Exception as exc:
        logger.exception("download/desk-note failed")
        return _error_response(str(exc))


@app.route("/api/download/dashboard")
def download_dashboard():
    """Serve the self-contained HTML dashboard as a download."""
    try:
        with _lock:
            market_data = _state["market_data"]
            metrics = _state["metrics"]
            narrative = _state["narrative"]

        if market_data is None or metrics is None:
            return _error_response("No data available. Run pipeline first.", 400)

        from euro_risk_pack.dashboard.builder import build_dashboard
        from euro_risk_pack.narrative.logger import read_latest_log_entry

        target_date = _get_target_date()
        prompt_log = read_latest_log_entry()

        dashboard_path = build_dashboard(
            target_date=target_date,
            metrics=metrics,
            market_data=market_data,
            narrative=narrative or "",
            prompt_log_entry=prompt_log,
            output_dir=OUTPUT_DIR,
        )

        return send_file(
            str(dashboard_path.resolve()),
            as_attachment=True,
            download_name=dashboard_path.name,
        )
    except Exception as exc:
        logger.exception("download/dashboard failed")
        return _error_response(str(exc))


@app.route("/outputs/charts/<filename>")
def serve_chart(filename: str):
    """Serve chart PNG files from the outputs/charts directory."""
    try:
        return send_from_directory(
            str(CHART_DIR.resolve()),
            filename,
        )
    except Exception as exc:
        logger.exception("serve_chart failed for %s", filename)
        return _error_response(str(exc), 404)


# ---------------------------------------------------------------------------
# Auto-open browser
# ---------------------------------------------------------------------------

def _open_browser() -> None:
    """Open the dashboard in the default browser after a short delay."""
    time.sleep(1.5)
    url = f"http://{SERVER_HOST}:{SERVER_PORT}"
    logger.info("Opening browser at %s", url)
    webbrowser.open(url)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the Flask development server."""
    _configure_logging()

    # Ensure output directories exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Starting Euro Risk Pack server on %s:%d (version %s)",
        SERVER_HOST, SERVER_PORT, VERSION,
    )

    if AUTO_OPEN_BROWSER:
        browser_thread = threading.Thread(target=_open_browser, daemon=True)
        browser_thread.start()

    app.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        threaded=True,
        debug=False,
    )


if __name__ == "__main__":
    main()
