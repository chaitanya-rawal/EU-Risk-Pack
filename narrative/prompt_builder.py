"""Prompt construction for the European Cross-Commodity Risk Pack LLM narrative.

Builds a structured user prompt from the computed :class:`MetricsResult` and
a fixed system prompt that instructs Claude to write as a senior European
power and gas trader.  The user prompt includes all seven metric values with
their signal classifications and trading-relevance context drawn from
:data:`~euro_risk_pack.metrics.definitions.METRIC_DEFINITIONS`.

The prompt requests a three-paragraph response structured as:

1. **GAS TIGHTNESS** — TTF spread, storage deficit, LNG context
2. **CARBON SIGNAL** — EUA momentum, TTF-EUA correlation
3. **POWER CURVE IMPLICATION** — dark/clean spark spreads, realised vol
"""

from __future__ import annotations

from euro_risk_pack.metrics.definitions import METRIC_DEFINITIONS
from euro_risk_pack.models import MetricsResult


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def build_system_prompt() -> str:
    """Return the system prompt for Claude.

    Instructs the model to write as a senior European power and gas trader
    producing a morning desk note in tight analyst prose.

    Returns:
        A non-empty system prompt string.
    """
    return (
        "You are a senior European power and gas trader writing a morning "
        "desk note. Be precise, use numbers, avoid filler. Write in tight "
        "analyst prose, not bullet points."
    )


# ---------------------------------------------------------------------------
# User prompt
# ---------------------------------------------------------------------------


def build_prompt(metrics: MetricsResult) -> str:
    """Build a structured user prompt from the computed metrics.

    The prompt contains:

    * A 3-sentence market context preamble setting the scene.
    * All seven metric values with their signal classifications and
      trading-relevance context from the canonical definitions.
    * An explicit instruction requesting a three-paragraph response
      structured as GAS TIGHTNESS, CARBON SIGNAL, and POWER CURVE
      IMPLICATION.

    Args:
        metrics: A complete :class:`MetricsResult` dictionary containing
            all seven monitor metrics.

    Returns:
        A non-empty prompt string suitable for the Claude API user message.
    """
    # --- Market context preamble -------------------------------------------
    preamble = (
        "Below are today's European cross-commodity risk metrics for the "
        "morning desk note. The monitor covers TTF natural gas, EUA carbon "
        "allowances, and German power day-ahead markets. Use these numbers "
        "to write a concise, actionable trading summary."
    )

    # --- Metric sections ---------------------------------------------------
    metric_lines: list[str] = []

    for key, result in metrics.items():
        defn = METRIC_DEFINITIONS.get(key)
        if defn is None:
            continue

        # Clean up multi-line trading relevance into a single paragraph
        relevance = " ".join(defn.trading_relevance.split())

        unit_label = f" ({defn.unit})" if defn.unit else ""
        metric_lines.append(
            f"### {defn.name}{unit_label}\n"
            f"- Value: {result['formatted']}\n"
            f"- Signal: {result['signal']}\n"
            f"- Formula: {defn.formula}\n"
            f"- Trading relevance: {relevance}"
        )

    metrics_block = "\n\n".join(metric_lines)

    # --- Response structure instruction ------------------------------------
    instruction = (
        "Write exactly three paragraphs with these headings:\n"
        "\n"
        "GAS TIGHTNESS\n"
        "Discuss the TTF spread, gas storage deficit, and any supply "
        "tightness or comfort signals. Reference the specific numbers.\n"
        "\n"
        "CARBON SIGNAL\n"
        "Discuss EUA momentum and the TTF-EUA correlation. Explain what "
        "the carbon trend means for generation margins.\n"
        "\n"
        "POWER CURVE IMPLICATION\n"
        "Discuss the dark spread, clean spark spread, and power realised "
        "volatility. Explain what these mean for dispatch economics and "
        "hedging.\n"
        "\n"
        "Use the exact metric values provided. Do not invent data."
    )

    return f"{preamble}\n\n{metrics_block}\n\n{instruction}"
