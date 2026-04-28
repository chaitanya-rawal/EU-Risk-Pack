"""Centralized data source registry for the European Cross-Commodity Risk Pack.

Every external data feed used by the ingestion layer is described here as a
:class:`~euro_risk_pack.models.SourceConfig` entry.  The registry maps
canonical source names to their primary endpoints, fallback endpoints,
ticker symbols, API URLs, and cache keys.

No hardcoded API endpoints or tickers should appear outside this module and
:mod:`euro_risk_pack.config`.

Functions
---------
get_source(name)
    Look up a :class:`SourceConfig` by its canonical name.

Attributes
----------
SOURCES : dict[str, SourceConfig]
    Registry of all seven data sources keyed by canonical name.
"""

from __future__ import annotations

from euro_risk_pack.config import AGSI_API_URL, EUA_TICKER, TTF_TICKER
from euro_risk_pack.models import SourceConfig


# ---------------------------------------------------------------------------
# Source Registry
# ---------------------------------------------------------------------------

SOURCES: dict[str, SourceConfig] = {
    "TTF_DA": SourceConfig(
        name="TTF Day-Ahead",
        source_type="yfinance",
        primary_endpoint=TTF_TICKER,
        fallback_endpoint=None,
        ticker=TTF_TICKER,
        api_url=None,
        cache_key="ttf_da",
        description="TTF natural gas day-ahead price in EUR/MWh via Yahoo Finance.",
    ),
    "TTF_M1": SourceConfig(
        name="TTF Month-1 Forward",
        source_type="yfinance",
        primary_endpoint=TTF_TICKER,
        fallback_endpoint=None,
        ticker=TTF_TICKER,
        api_url=None,
        cache_key="ttf_m1",
        description="TTF Month-1 forward price in EUR/MWh derived from the futures chain.",
    ),
    "EUA": SourceConfig(
        name="EUA Carbon Allowance",
        source_type="yfinance",
        primary_endpoint=EUA_TICKER,
        fallback_endpoint="ember",
        ticker=EUA_TICKER,
        api_url=None,
        cache_key="eua",
        description="EU Allowance (EUA) carbon price in EUR/tCO2 via Yahoo Finance or Ember.",
    ),
    "DE_POWER": SourceConfig(
        name="German Power Day-Ahead",
        source_type="api",
        primary_endpoint="entsoe",
        fallback_endpoint="ember",
        ticker=None,
        api_url="https://web-api.tp.entsoe.eu/api",
        cache_key="de_power",
        description="German baseload day-ahead power price in EUR/MWh from ENTSO-E or Ember.",
    ),
    "FR_POWER": SourceConfig(
        name="French Power Day-Ahead",
        source_type="api",
        primary_endpoint="entsoe",
        fallback_endpoint="ember",
        ticker=None,
        api_url="https://web-api.tp.entsoe.eu/api",
        cache_key="fr_power",
        description="French baseload day-ahead power price in EUR/MWh from ENTSO-E or Ember.",
    ),
    "GAS_STORAGE": SourceConfig(
        name="EU Gas Storage (AGSI+)",
        source_type="api",
        primary_endpoint=AGSI_API_URL,
        fallback_endpoint=None,
        ticker=None,
        api_url=AGSI_API_URL,
        cache_key="gas_storage",
        description=(
            "EU aggregate gas storage fill level and 5-year seasonal average "
            "from the AGSI+ transparency platform."
        ),
    ),
    "LNG_SENDOUT": SourceConfig(
        name="LNG Send-out (GIE ALSI)",
        source_type="api",
        primary_endpoint="https://alsi.gie.eu/api",
        fallback_endpoint=None,
        ticker=None,
        api_url="https://alsi.gie.eu/api",
        cache_key="lng_sendout",
        description="LNG send-out proxy in GWh/day from the GIE ALSI platform.",
    ),
}


def get_source(name: str) -> SourceConfig:
    """Retrieve a data source configuration by its canonical name.

    Parameters
    ----------
    name : str
        Canonical source name — one of ``"TTF_DA"``, ``"TTF_M1"``,
        ``"EUA"``, ``"DE_POWER"``, ``"FR_POWER"``, ``"GAS_STORAGE"``,
        or ``"LNG_SENDOUT"``.

    Returns
    -------
    SourceConfig
        The matching source configuration dataclass instance.

    Raises
    ------
    KeyError
        If *name* does not match any registered source.
    """
    try:
        return SOURCES[name]
    except KeyError:
        valid = ", ".join(sorted(SOURCES.keys()))
        raise KeyError(
            f"Unknown data source {name!r}. Valid sources: {valid}"
        ) from None
