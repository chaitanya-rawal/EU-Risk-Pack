"""LLM client for the European Cross-Commodity Risk Pack.

Calls the Anthropic Claude API to generate the desk-note narrative.  On any
API failure (timeout, rate-limit, authentication, network) the client falls
back to a deterministic template-based narrative prefixed with
``[FALLBACK MODE]``.

Every call — whether it succeeds or falls back — is logged via
:func:`~euro_risk_pack.narrative.logger.log_prompt_call` before the
response is returned.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Generator

from euro_risk_pack.config import ANTHROPIC_API_KEY, LLM_MAX_TOKENS, LLM_MODEL, OUTPUT_DIR
from euro_risk_pack.metrics.definitions import METRIC_DEFINITIONS
from euro_risk_pack.models import MetricsResult
from euro_risk_pack.narrative.logger import log_prompt_call

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def call_claude(
    system_prompt: str,
    user_prompt: str,
    metrics: MetricsResult,
    model: str = LLM_MODEL,
) -> str:
    """Call the Anthropic Claude API and return the narrative text.

    On any API failure the function falls back to
    :func:`generate_fallback_narrative` and returns the template text
    prefixed with ``[FALLBACK MODE]``.  Every call (success or fallback)
    is logged via :func:`~euro_risk_pack.narrative.logger.log_prompt_call`.

    Args:
        system_prompt: System prompt instructing the model's persona.
        user_prompt: Structured user prompt containing metric data.
        metrics: The full :class:`MetricsResult` dictionary, used to
            generate the fallback narrative if the API call fails.
        model: Anthropic model identifier.  Defaults to
            :data:`~euro_risk_pack.config.LLM_MODEL`.

    Returns:
        The narrative text — either from Claude or the template fallback.
    """
    is_fallback = False
    response_text = ""
    timestamp = datetime.now(timezone.utc)

    try:
        import anthropic  # noqa: F811 — deferred import to avoid hard dep

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=model,
            max_tokens=LLM_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Extract text from the response content blocks
        response_text = "".join(
            block.text for block in message.content if hasattr(block, "text")
        )
        logger.info("Claude API call succeeded (model=%s)", model)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Claude API call failed: %s — using fallback narrative", exc)
        is_fallback = True
        response_text = generate_fallback_narrative(metrics)

    # Log every call (success or fallback)
    log_prompt_call(
        timestamp=timestamp,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=response_text,
        model=model,
        is_fallback=is_fallback,
        log_path=OUTPUT_DIR / "prompts_log.jsonl",
    )

    return response_text


# ---------------------------------------------------------------------------
# Streaming API
# ---------------------------------------------------------------------------


def stream_claude(
    system_prompt: str,
    user_prompt: str,
    metrics: MetricsResult,
    model: str = LLM_MODEL,
) -> Generator[str, None, None]:
    """Stream Claude API response as text chunks for SSE delivery.

    Yields text chunks as they arrive from the streaming API.
    On failure, yields the fallback narrative in one chunk.
    Logs the complete call after streaming finishes.
    """
    timestamp = datetime.now(timezone.utc)
    full_response = ""
    is_fallback = False

    try:
        import anthropic

        if not ANTHROPIC_API_KEY:
            raise ValueError("No ANTHROPIC_API_KEY configured")
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        with client.messages.stream(
            model=model,
            max_tokens=LLM_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                yield text
    except Exception as exc:
        logger.warning("Claude streaming failed: %s — using fallback", exc)
        is_fallback = True
        full_response = generate_fallback_narrative(metrics)
        yield full_response

    # Log after streaming completes
    log_prompt_call(
        timestamp=timestamp,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=full_response,
        model=model,
        is_fallback=is_fallback,
        log_path=OUTPUT_DIR / "prompts_log.jsonl",
    )


# ---------------------------------------------------------------------------
# Fallback narrative
# ---------------------------------------------------------------------------


def generate_fallback_narrative(metrics: MetricsResult) -> str:
    """Generate a template-based narrative when the API is unavailable.

    The output is prefixed with ``[FALLBACK MODE]`` and structured as three
    paragraphs matching the expected desk-note format: GAS TIGHTNESS,
    CARBON SIGNAL, and POWER CURVE IMPLICATION.

    Args:
        metrics: A complete :class:`MetricsResult` dictionary.

    Returns:
        A non-empty narrative string prefixed with ``[FALLBACK MODE]``.
    """
    # Extract individual metric results
    ttf_spread = metrics["ttf_da_vs_m1_spread"]
    storage_deficit = metrics["gas_storage_deficit_pct"]
    eua_momentum = metrics["eua_30d_momentum"]
    ttf_eua_corr = metrics["ttf_eua_correlation_30d"]
    dark_spread = metrics["dark_spread_de"]
    spark_spread = metrics["clean_spark_spread_de"]
    power_vol = metrics["power_da_realised_vol_20d"]

    # Look up short names from definitions for cleaner prose
    def _short(key: str) -> str:
        defn = METRIC_DEFINITIONS.get(key)
        return defn.short_name if defn else key

    # --- GAS TIGHTNESS -----------------------------------------------------
    gas_paragraph = (
        f"GAS TIGHTNESS: The TTF day-ahead vs M1 spread stands at "
        f"{ttf_spread['formatted']} ({ttf_spread['signal']}). "
        f"Gas storage deficit relative to the 5-year seasonal average is "
        f"{storage_deficit['formatted']} ({storage_deficit['signal']}). "
    )
    if storage_deficit["value"] < 0:
        gas_paragraph += (
            "Inventories are running below seasonal norms, suggesting "
            "near-term supply tightness that supports prompt gas prices."
        )
    else:
        gas_paragraph += (
            "Inventories are at or above seasonal norms, providing a "
            "comfortable supply cushion that limits upside price risk."
        )

    # --- CARBON SIGNAL -----------------------------------------------------
    carbon_paragraph = (
        f"CARBON SIGNAL: EUA 30-day momentum is {eua_momentum['formatted']} "
        f"({eua_momentum['signal']}), "
    )
    if eua_momentum["value"] > 0:
        carbon_paragraph += "indicating a strengthening carbon market. "
    else:
        carbon_paragraph += "indicating a weakening carbon market. "

    carbon_paragraph += (
        f"The TTF-EUA 30-day return correlation is "
        f"{ttf_eua_corr['formatted']} ({ttf_eua_corr['signal']}). "
    )
    if abs(ttf_eua_corr["value"]) > 0.7:
        carbon_paragraph += (
            "Gas and carbon are moving in lockstep, driven by a common "
            "macro factor. Cross-commodity hedges should account for this "
            "tight linkage."
        )
    else:
        carbon_paragraph += (
            "Gas and carbon markets are showing some degree of decoupling, "
            "which may present relative-value opportunities."
        )

    # --- POWER CURVE IMPLICATION -------------------------------------------
    power_paragraph = (
        f"POWER CURVE IMPLICATION: The German dark spread is "
        f"{dark_spread['formatted']} ({dark_spread['signal']}) and the "
        f"clean spark spread is {spark_spread['formatted']} "
        f"({spark_spread['signal']}). "
    )
    if dark_spread["value"] > 0:
        power_paragraph += (
            "Gas-fired generation is currently in the money, supporting "
            "gas demand from the power sector. "
        )
    else:
        power_paragraph += (
            "Gas-fired generation is currently out of the money, reducing "
            "gas burn from the power sector. "
        )

    power_paragraph += (
        f"Power day-ahead realised volatility over 20 days is "
        f"{power_vol['formatted']} ({power_vol['signal']}). "
    )
    if power_vol["value"] > 15.0:
        power_paragraph += (
            "Elevated volatility increases the value of flexible assets "
            "and warrants wider hedging bands."
        )
    elif power_vol["value"] < 5.0:
        power_paragraph += (
            "Low volatility suggests a stable supply-demand balance and "
            "compresses option premia."
        )
    else:
        power_paragraph += (
            "Moderate volatility is consistent with normal market "
            "conditions."
        )

    return f"[FALLBACK MODE]\n\n{gas_paragraph}\n\n{carbon_paragraph}\n\n{power_paragraph}"
