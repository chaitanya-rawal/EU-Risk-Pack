# European Cross-Commodity Risk Pack
### Gas + Carbon → Power Curve Monitor

A production-grade daily monitoring system for European energy markets that ingests live public data across TTF natural gas, EUA carbon allowances, German/French power day-ahead prices, and EU gas storage levels — computes seven cross-commodity risk metrics used by trading desks, generates publication-quality charts, calls Anthropic's Claude API to produce an AI-written analyst desk note, and serves everything through a live interactive Flask dashboard with real-time refresh capabilities and streaming narrative generation.

Built from the ground up as a full-stack quantitative trading tool: the backend implements a resilient multi-source data ingestion pipeline with automatic fallback chains (live API → cached CSV → synthetic mock), a metrics engine covering spread analysis, momentum indicators, correlation regimes, and realized volatility, a Chart.js-powered frontend with dark terminal aesthetics matching Bloomberg/Reuters styling, Server-Sent Events for streaming LLM output token-by-token into the browser, and a complete report generation pipeline producing both Markdown and PDF desk notes. The system is designed to never crash — every external dependency (market data APIs, LLM, PDF renderer) has a graceful fallback path, and the entire pipeline can run in demo mode with deterministic seeded synthetic data for evaluation without any API keys.

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/chaitanya-rawal/EU-Risk-Pack.git
cd EU-Risk-Pack
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

**Requirements:** Python 3.10+, pip. All dependencies are standard PyPI packages.

### 3. Configure environment (optional)

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```
ANTHROPIC_API_KEY=your_key_here
ENTSOE_API_KEY=your_key_here_optional
ANALYST_NAME=Your Name
ANALYST_EMAIL=your@email.com
```

> **No API keys?** No problem. The system runs fully in mock mode with realistic synthetic data and a template-based narrative. Every feature works without any keys.

### 4. Start the dashboard

```bash
python server.py
```

The dashboard auto-opens at **http://localhost:5050** in your default browser.

That's it. You should see the full trading dashboard with 7 metric cards, 3 interactive charts, trading signals, and an AI desk note.

---

## Running Without API Keys (Demo Mode)

The system is fully functional without any API keys:

```bash
python server.py
```

- All market data is generated synthetically using a seeded random number generator (deterministic — same date always produces the same data)
- The narrative uses a template-based fallback prefixed with `[FALLBACK MODE]`
- All charts, metrics, signals, and the dashboard render identically to a live run
- Click **▶ RUN MOCK** in the dashboard header to regenerate with fresh mock data

---

## CLI Mode (No Server)

For headless/scripted usage without the web dashboard:

```bash
# Mock mode (no API keys needed)
python main.py --mock

# Specific date
python main.py --date 2024-01-15

# Mock mode for a specific date
python main.py --date 2024-01-15 --mock
```

Outputs are written to the `outputs/` directory.

---

## Dashboard Features

### Header Bar
- **▶ RUN MOCK** — Runs the full pipeline with synthetic data
- **⟳ REFRESH ALL** — Re-fetches all live data and regenerates everything
- **↓ DOWNLOAD** — Download the PDF desk note or a self-contained offline HTML dashboard
- Connection status indicator (green = fresh, amber = stale, red = error)

### Metric Strip (7 Cards)
Each card shows the metric value, unit, signal classification (BULLISH/BEARISH/NEUTRAL/ALERT), and a directional arrow. Cards are color-tinted by signal. Each card has a small refresh button to update just that data source.

| # | Metric | What It Measures | Unit |
|---|--------|-----------------|------|
| 1 | TTF Spread | Day-ahead vs M1 forward — backwardation/contango | EUR/MWh |
| 2 | EUA Momentum | 30-day carbon price trend | % |
| 3 | Storage Deficit | Current fill vs 5-year seasonal average | pp |
| 4 | Dark Spread DE | Gas plant profitability (gross) | EUR/MWh |
| 5 | Spark Spread DE | Gas plant profitability (carbon-adjusted) | EUR/MWh |
| 6 | TTF-EUA Correlation | Gas-carbon return linkage | ρ |
| 7 | Power Volatility | 20-day realized vol of DA power | EUR/MWh |

### Interactive Charts (Chart.js)
- **TTF vs EUA** — Dual-axis line chart, 30 days
- **Dark Spread vs Spark Spread** — Grouped bar chart, 20 days
- **EU Gas Storage** — Area chart with current fill vs 5-year average

### AI Desk Note
- Powered by Anthropic Claude (claude-sonnet-4-20250514)
- Three sections: GAS TIGHTNESS / CARBON SIGNAL / POWER CURVE IMPLICATION
- **⟳ Regenerate** streams the narrative token-by-token via Server-Sent Events
- Falls back to a template narrative if the API is unavailable

### Trading Signals Panel
Four key signals with color-coded badges and one-line rationales:
- Gas Tightness, Carbon Momentum, Spark Spread, Storage Balance

---

## Output Files

After each pipeline run, the following files are generated:

| File | Description |
|------|-------------|
| `outputs/charts/ttf_eua_30d.png` | TTF vs EUA dual-axis line chart |
| `outputs/charts/storage_vs_seasonal.png` | Gas storage fill vs 5-year average |
| `outputs/charts/dark_spread_spark_spread.png` | Dark spread vs spark spread bars |
| `outputs/desk_note_YYYY-MM-DD.md` | Markdown desk note |
| `outputs/desk_note_YYYY-MM-DD.pdf` | PDF desk note (requires system GTK libs) |
| `outputs/dashboard_YYYY-MM-DD.html` | Self-contained offline HTML dashboard |
| `outputs/prompts_log.jsonl` | JSONL audit log of all LLM calls |
| `outputs/run.log` | Pipeline execution log |

---

## Data Sources

All data sources are public and free:

| Source | Data | Auth Required |
|--------|------|---------------|
| [Yahoo Finance](https://finance.yahoo.com/) (via yfinance) | TTF gas, EUA carbon prices | No |
| [AGSI+](https://agsi.gie.eu/) | EU gas storage levels | No |
| [ENTSO-E](https://transparency.entsoe.eu/) | German/French power DA prices | Free registration |
| [Ember](https://ember-climate.org/) | Power/carbon fallback data | No |
| [GIE ALSI](https://alsi.gie.eu/) | LNG sendout proxy | No |

> **ENTSO-E API Key:** Register for free at https://transparency.entsoe.eu/ to get live power price data. Without it, the system falls back to Ember, then cache, then mock data.

---

## Configuration

All configuration is in `config.py` and can be overridden via `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(empty)* | Anthropic API key for Claude narrative |
| `ENTSOE_API_KEY` | *(empty)* | ENTSO-E Transparency Platform key |
| `ANALYST_NAME` | European Risk Desk | Name in desk note header |
| `ANALYST_EMAIL` | risk@example.com | Email in desk note header |
| `SERVER_PORT` | 5050 | Flask server port |
| `SERVER_HOST` | 127.0.0.1 | Flask server host |
| `AUTO_OPEN_BROWSER` | true | Auto-open browser on server start |

---

## Project Structure

```
euro_risk_pack/
├── server.py                 # Flask web server — primary entry point
├── main.py                   # CLI entry point
├── config.py                 # All configuration, thresholds, design tokens
├── models.py                 # TypedDict/dataclass definitions
├── data/
│   ├── ingest.py             # Multi-source ingestion with fallback chain
│   ├── sources.py            # Data source registry
│   ├── cache.py              # Local CSV cache layer
│   └── mock.py               # Seeded synthetic data generator
├── metrics/
│   ├── calculator.py         # 7 metric calculators + orchestrator
│   └── definitions.py        # Metric names, formulas, trading relevance
├── charts/
│   └── generator.py          # 3 Matplotlib PNG chart generators
├── narrative/
│   ├── prompt_builder.py     # Structured Claude prompt construction
│   ├── llm_client.py         # Anthropic API client (batch + streaming)
│   └── logger.py             # JSONL prompt audit logger
├── report/
│   └── builder.py            # Markdown + PDF desk note builder
├── dashboard/
│   ├── builder.py            # Dashboard data payload assembler
│   └── template.py           # Self-contained HTML template
├── static/
│   ├── dashboard.css         # Dark terminal theme CSS
│   └── dashboard.js          # Chart.js, refresh, SSE streaming
├── templates/
│   └── index.html            # Flask Jinja2 dashboard template
├── requirements.txt
└── README.md
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Yahoo Fin   │     │   AGSI+      │     │  ENTSO-E    │
│  (TTF, EUA)  │     │  (Storage)   │     │  (Power)    │
└──────┬───────┘     └──────┬───────┘     └──────┬──────┘
       │                    │                    │
       └────────────┬───────┴────────────────────┘
                    │
            ┌───────▼────────┐
            │  Data Ingest   │ ← fallback: cache → mock
            │  (ingest.py)   │
            └───────┬────────┘
                    │
            ┌───────▼────────┐
            │  7 Metrics     │
            │  (calculator)  │
            └───┬───────┬────┘
                │       │
        ┌───────▼──┐ ┌──▼──────────┐
        │  Charts  │ │  Claude API │ ← fallback: template
        │  (3 PNG) │ │  (narrative)│
        └───────┬──┘ └──┬──────────┘
                │       │
            ┌───▼───────▼────┐
            │  Flask Server  │
            │  (server.py)   │
            └───────┬────────┘
                    │
            ┌───────▼────────┐
            │  Dashboard     │ ← Chart.js + SSE streaming
            │  (browser)     │
            └────────────────┘
```

---

## License

MIT
