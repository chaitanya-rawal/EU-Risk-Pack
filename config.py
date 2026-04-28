"""Centralized configuration for the European Cross-Commodity Risk Pack.

Loads API keys and analyst info from a ``.env`` file via python-dotenv.
Defines all constants, metric thresholds, output paths, design tokens,
and data-source tickers used throughout the package.  No computation
happens here — this module is configuration only.
"""

from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

# ---------------------------------------------------------------------------
# Package version
# ---------------------------------------------------------------------------
VERSION: str = "0.1.0"

# ---------------------------------------------------------------------------
# API Keys (loaded from .env)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ENTSOE_API_KEY: str = os.getenv("ENTSOE_API_KEY", "")

# ---------------------------------------------------------------------------
# Analyst Info (loaded from .env with sensible defaults)
# ---------------------------------------------------------------------------
ANALYST_NAME: str = os.getenv("ANALYST_NAME", "European Risk Desk")
ANALYST_EMAIL: str = os.getenv("ANALYST_EMAIL", "risk@example.com")

# ---------------------------------------------------------------------------
# LLM Model Configuration
# ---------------------------------------------------------------------------
LLM_MODEL: str = "claude-sonnet-4-20250514"
LLM_MAX_TOKENS: int = 1024

# ---------------------------------------------------------------------------
# Output Paths (as Path objects)
# ---------------------------------------------------------------------------
OUTPUT_DIR: Path = Path("outputs")
CACHE_DIR: Path = Path("data/cache")
CHART_DIR: Path = OUTPUT_DIR / "charts"

# ---------------------------------------------------------------------------
# Power-Plant Efficiency Constants
# ---------------------------------------------------------------------------
GAS_PLANT_EFFICIENCY: float = 0.49   # 49 % thermal efficiency
EMISSION_FACTOR: float = 0.37        # tCO2/MWh for a gas-fired plant

# ---------------------------------------------------------------------------
# Metric Thresholds
# ---------------------------------------------------------------------------
THRESHOLDS: dict[str, dict[str, float]] = {
    "ttf_da_vs_m1_spread": {
        "backwardation": 0.5,
        "deep_contango": -2.0,
    },
    "eua_30d_momentum": {
        "strong_bull": 10.0,
        "strong_bear": -10.0,
    },
    "gas_storage_deficit_pct": {
        "tight": -5.0,
        "comfortable": 5.0,
    },
    "dark_spread_de": {
        "profitable": 5.0,
        "unprofitable": -5.0,
    },
    "clean_spark_spread_de": {
        "profitable": 3.0,
        "unprofitable": -3.0,
    },
    "ttf_eua_correlation_30d": {
        "high": 0.7,
        "decorrelated": 0.3,
    },
    "power_da_realised_vol_20d": {
        "high_vol": 15.0,
        "low_vol": 5.0,
    },
}

# ---------------------------------------------------------------------------
# Data Source Tickers
# ---------------------------------------------------------------------------
TTF_TICKER: str = "TTF=F"
EUA_TICKER: str = "CO2.L"
AGSI_API_URL: str = "https://agsi.gie.eu/api"

# ---------------------------------------------------------------------------
# Dashboard Design Tokens (dark terminal aesthetic)
# ---------------------------------------------------------------------------
COLORS: dict[str, str] = {
    "bg": "#0d1117",
    "surface": "#161b22",
    "border": "#30363d",
    "ttf": "#58a6ff",
    "eua": "#f0883e",
    "power": "#3fb950",
    "negative": "#f85149",
    "text": "#c9d1d9",
    "text_muted": "#6e7681",
    "bullish": "#3fb950",
    "bearish": "#f85149",
    "neutral": "#6e7681",
    "alert": "#f0883e",
}

# ---------------------------------------------------------------------------
# Server Configuration
# ---------------------------------------------------------------------------
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "5050"))
SERVER_HOST: str = os.getenv("SERVER_HOST", "127.0.0.1")
AUTO_OPEN_BROWSER: bool = os.getenv("AUTO_OPEN_BROWSER", "true").lower() == "true"
