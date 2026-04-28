"""Prompt logging for the European Cross-Commodity Risk Pack.

Appends each LLM call (or fallback) to a JSONL audit log at
``outputs/prompts_log.jsonl``.  Every entry records the timestamp, model
identifier, full system and user prompts, the response text, and whether
the response came from the template fallback.

The logger is designed to **never raise** — any I/O or serialisation error
is caught and reported as a warning on ``stderr`` so that a logging failure
cannot disrupt the main pipeline.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from euro_risk_pack.config import OUTPUT_DIR


# ---------------------------------------------------------------------------
# Default log path
# ---------------------------------------------------------------------------

_DEFAULT_LOG_PATH: Path = OUTPUT_DIR / "prompts_log.jsonl"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def log_prompt_call(
    timestamp: datetime,
    system_prompt: str,
    user_prompt: str,
    response: str,
    model: str,
    is_fallback: bool,
    log_path: Path = _DEFAULT_LOG_PATH,
) -> None:
    """Append a single prompt/response entry to the JSONL log.

    Creates the log file (and parent directories) on the first write.
    On any failure the error is printed to ``stderr`` and the function
    returns silently — it never raises an exception.

    Args:
        timestamp: When the LLM call was made.
        system_prompt: Full system prompt text sent to the model.
        user_prompt: Full user prompt text sent to the model.
        response: Complete response text (or fallback narrative).
        model: Model identifier (e.g. ``"claude-sonnet-4-20250514"``).
        is_fallback: ``True`` if a template fallback was used instead of
            a live API response.
        log_path: Path to the JSONL log file.  Defaults to
            ``outputs/prompts_log.jsonl``.
    """
    entry = {
        "timestamp": timestamp.isoformat(),
        "model": model,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response": response,
        "is_fallback": is_fallback,
    }

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        print(
            f"[WARNING] Failed to write prompt log to {log_path}: {exc}",
            file=sys.stderr,
        )


def read_latest_log_entry(
    log_path: Path = _DEFAULT_LOG_PATH,
) -> Optional[dict]:
    """Read the most recent entry from the JSONL log.

    Args:
        log_path: Path to the JSONL log file.  Defaults to
            ``outputs/prompts_log.jsonl``.

    Returns:
        A dictionary parsed from the last JSON line, or ``None`` if the
        file does not exist or is empty.
    """
    try:
        if not log_path.exists():
            return None

        last_line: Optional[str] = None
        with open(log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped:
                    last_line = stripped

        if last_line is None:
            return None

        return json.loads(last_line)
    except Exception:  # noqa: BLE001
        return None
