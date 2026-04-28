"""Self-contained HTML dashboard template for the European Cross-Commodity Risk Pack.

Defines :data:`DASHBOARD_TEMPLATE`, a complete HTML5 document string with all
CSS in ``<style>`` tags and all JavaScript in ``<script>`` tags.  The template
uses Python :class:`string.Template` ``$$``-syntax for placeholders (because
CSS curly braces conflict with ``.format()``).

The template loads Chart.js 4.4.1 from CDN and IBM Plex Mono/Sans from
Google Fonts, with monospace fallback for offline use.
"""

from __future__ import annotations

# The template is split into parts and joined to stay within line limits.
# All CSS is inline in <style>, all JS is inline in <script>.
# Placeholders use string.Template $-syntax.

_HEAD = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EURO RISK PACK — $date</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
"""

_CSS = r"""<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 14px; }
body {
  background: #0d1117; color: #c9d1d9;
  font-family: 'IBM Plex Sans', 'IBM Plex Mono', 'Courier New', monospace;
  line-height: 1.5; min-width: 1024px; padding: 0;
}
a { color: #58a6ff; text-decoration: none; }
a:hover { text-decoration: underline; }
.label-upper {
  font-family: 'IBM Plex Mono', 'Courier New', monospace;
  font-size: 10px; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: #6e7681;
}
.mono { font-family: 'IBM Plex Mono', 'Courier New', monospace; }
.container { max-width: 1440px; margin: 0 auto; padding: 0 24px; }

/* Header */
.header-bar { background: #161b22; border-bottom: 1px solid #30363d; padding: 16px 0; }
.header-inner { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.header-left { display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; }
.header-title { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 20px; font-weight: 700; color: #c9d1d9; letter-spacing: 0.04em; }
.header-date { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 14px; color: #58a6ff; }
.header-subtitle { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #6e7681; }
.header-right { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.header-timestamp { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 11px; color: #6e7681; }
.header-badge { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 9px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: #6e7681; background: #0d1117; border: 1px solid #30363d; border-radius: 3px; padding: 3px 8px; }

/* Metric Strip */
.metric-strip { padding: 20px 0; border-bottom: 1px solid #30363d; }
.metric-cards { display: grid; grid-template-columns: repeat(7, 1fr); gap: 12px; }
.metric-card { background: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 14px 12px; display: flex; flex-direction: column; gap: 6px; }
.metric-card.bullish { background: #1a2e1a; }
.metric-card.bearish { background: #2e1a1a; }
.metric-card-label { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #6e7681; }
.metric-card-value { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 22px; font-weight: 700; line-height: 1.1; }
.metric-card-unit { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 10px; color: #6e7681; }
.metric-card-signal { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }

/* Chart Row */
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 20px 0; border-bottom: 1px solid #30363d; }
.chart-panel { background: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 16px; }
.chart-panel-title { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #6e7681; margin-bottom: 12px; }
.chart-legend { display: flex; gap: 16px; margin-bottom: 10px; }
.chart-legend-item { display: flex; align-items: center; gap: 6px; font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 11px; color: #6e7681; }
.chart-legend-swatch { width: 12px; height: 3px; border-radius: 1px; }
.chart-container { position: relative; height: 260px; }

/* Storage + Signal Row */
.storage-signal-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 20px 0; border-bottom: 1px solid #30363d; }
.signal-panel { background: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 16px; }
.signal-panel-title { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #6e7681; margin-bottom: 16px; }
.signal-pills { display: flex; flex-direction: column; gap: 10px; }
.signal-pill { display: flex; justify-content: space-between; align-items: center; background: #0d1117; border: 1px solid #30363d; border-radius: 4px; padding: 10px 14px; }
.signal-pill-label { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 12px; color: #c9d1d9; }
.signal-pill-value { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 13px; font-weight: 700; }
.signal-pill-badge { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 9px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; padding: 2px 8px; border-radius: 3px; }
.signal-pill-badge.bullish { background: #1a2e1a; color: #3fb950; border: 1px solid #3fb950; }
.signal-pill-badge.bearish { background: #2e1a1a; color: #f85149; border: 1px solid #f85149; }
.signal-pill-badge.neutral { background: #161b22; color: #6e7681; border: 1px solid #30363d; }
.signal-pill-badge.alert { background: #2e2a1a; color: #f0883e; border: 1px solid #f0883e; }

/* AI Desk Note */
.desk-note { padding: 20px 0; border-bottom: 1px solid #30363d; }
.desk-note-panel { background: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 20px 24px; }
.desk-note-title { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #6e7681; margin-bottom: 16px; }
.desk-note-section { margin-bottom: 16px; }
.desk-note-section-title { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #58a6ff; margin-bottom: 6px; }
.desk-note-text { font-family: 'IBM Plex Sans', 'IBM Plex Mono', 'Courier New', monospace; font-size: 13px; color: #c9d1d9; line-height: 1.65; }
.prompt-log-toggle { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 11px; color: #6e7681; cursor: pointer; border: 1px solid #30363d; background: #0d1117; padding: 8px 14px; border-radius: 4px; margin-top: 16px; display: inline-block; }
.prompt-log-toggle:hover { border-color: #58a6ff; color: #58a6ff; }
.prompt-log-details { display: none; margin-top: 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 4px; padding: 14px; font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 11px; color: #6e7681; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; }
.prompt-log-details.open { display: block; }

/* Footer */
.footer-bar { padding: 20px 0; }
.footer-inner { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; }
.footer-sources { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 10px; color: #6e7681; }
.footer-meta { font-family: 'IBM Plex Mono', 'Courier New', monospace; font-size: 10px; color: #6e7681; text-align: right; }

/* Responsive */
@media (max-width: 1200px) {
  .metric-cards { grid-template-columns: repeat(4, 1fr); }
}
@media (max-width: 1024px) {
  .metric-cards { grid-template-columns: repeat(4, 1fr); }
  .chart-row, .storage-signal-row { grid-template-columns: 1fr; }
}
</style>
"""

_BODY_HEADER = r"""</head>
<body>

<!-- ═══ Section 1: Header Bar ═══ -->
<div class="header-bar">
  <div class="container header-inner">
    <div class="header-left">
      <span class="header-title">EURO RISK PACK</span>
      <span class="header-date">$date</span>
      <span class="header-subtitle">DAILY MONITOR</span>
    </div>
    <div class="header-right">
      <span class="header-timestamp">LAST RUN $run_timestamp</span>
      <span class="header-badge">SOURCE: AGSI / ENTSOE / YAHOO FINANCE</span>
    </div>
  </div>
</div>
"""

_BODY_METRIC_STRIP = r"""
<!-- ═══ Section 2: Metric Strip ═══ -->
<div class="metric-strip">
  <div class="container">
    <div class="metric-cards" id="metric-cards"></div>
  </div>
</div>
"""

_BODY_CHART_ROW = r"""
<!-- ═══ Section 3: Chart Row ═══ -->
<div class="chart-row container">
  <div class="chart-panel">
    <div class="chart-panel-title">TTF GAS vs EUA CARBON — 30 DAY</div>
    <div class="chart-legend">
      <div class="chart-legend-item"><span class="chart-legend-swatch" style="background:#58a6ff"></span> TTF (EUR/MWh)</div>
      <div class="chart-legend-item"><span class="chart-legend-swatch" style="background:#f0883e"></span> EUA (EUR/tCO₂)</div>
    </div>
    <div class="chart-container"><canvas id="chart-ttf-eua"></canvas></div>
  </div>
  <div class="chart-panel">
    <div class="chart-panel-title">DARK SPREAD vs SPARK SPREAD — DE</div>
    <div class="chart-legend">
      <div class="chart-legend-item"><span class="chart-legend-swatch" style="background:#58a6ff"></span> Dark Spread</div>
      <div class="chart-legend-item"><span class="chart-legend-swatch" style="background:#3fb950"></span> Spark Spread</div>
    </div>
    <div class="chart-container"><canvas id="chart-spreads"></canvas></div>
  </div>
</div>
"""

_BODY_STORAGE_SIGNAL = r"""
<!-- ═══ Section 4: Storage + Signal Row ═══ -->
<div class="storage-signal-row container">
  <div class="chart-panel">
    <div class="chart-panel-title">EU GAS STORAGE — FILL LEVEL</div>
    <div class="chart-legend">
      <div class="chart-legend-item"><span class="chart-legend-swatch" style="background:#3fb950"></span> Current</div>
      <div class="chart-legend-item"><span class="chart-legend-swatch" style="background:rgba(88,166,255,0.3)"></span> 5yr Avg</div>
    </div>
    <div class="chart-container"><canvas id="chart-storage"></canvas></div>
  </div>
  <div class="signal-panel">
    <div class="signal-panel-title">TRADING SIGNALS</div>
    <div class="signal-pills" id="signal-pills"></div>
  </div>
</div>
"""

_BODY_DESK_NOTE = r"""
<!-- ═══ Section 5: AI Desk Note ═══ -->
<div class="desk-note">
  <div class="container">
    <div class="desk-note-panel">
      <div class="desk-note-title">AI DESK NOTE — CLAUDE ANALYSIS</div>
      <div id="narrative-content">$narrative_html</div>
      <div class="prompt-log-toggle" onclick="togglePromptLog()">▸ PROMPT LOG</div>
      <div class="prompt-log-details" id="prompt-log-details"></div>
    </div>
  </div>
</div>
"""

_BODY_FOOTER = r"""
<!-- ═══ Section 6: Footer ═══ -->
<div class="footer-bar">
  <div class="container footer-inner">
    <div class="footer-sources">
      DATA SOURCES: Yahoo Finance · AGSI+ · ENTSO-E · Ember · GIE ALSI<br>
      Generated $run_timestamp
    </div>
    <div class="footer-meta">
      $analyst_name &lt;$analyst_email&gt;<br>
      EURO RISK PACK v$version
    </div>
  </div>
</div>
"""

_SCRIPT = r"""
<!-- ═══ Data Injection ═══ -->
<script>
const DASHBOARD_DATA = {
  metrics: $metrics_json,
  signals: $signals_json,
  ttfSeries: $ttf_series_json,
  euaSeries: $eua_series_json,
  datesTtf: $dates_ttf_json,
  datesEua: $dates_eua_json,
  storageSeries: $storage_series_json,
  storageAvg: $storage_avg_json,
  datesStorage: $dates_storage_json,
  spreadSeries: $spread_series_json,
  dateSpread: $dates_spread_json,
  promptLog: $prompt_log_json
};

/* ── Metric Cards ─────────────────────────────────────────────── */
(function renderMetricCards() {
  const container = document.getElementById('metric-cards');
  if (!container || !DASHBOARD_DATA.metrics) return;
  DASHBOARD_DATA.metrics.forEach(function(m) {
    var cls = 'metric-card';
    if (m.signal === 'BULLISH') cls += ' bullish';
    else if (m.signal === 'BEARISH') cls += ' bearish';
    var card = document.createElement('div');
    card.className = cls;
    card.innerHTML =
      '<div class="metric-card-label">' + m.label + '</div>' +
      '<div class="metric-card-value" style="color:' + m.color + '">' + m.arrow + ' ' + m.value + '</div>' +
      '<div class="metric-card-unit">' + m.unit + '</div>' +
      '<div class="metric-card-signal" style="color:' + m.color + '">' + m.signal + '</div>';
    container.appendChild(card);
  });
})();

/* ── Signal Pills ─────────────────────────────────────────────── */
(function renderSignalPills() {
  var container = document.getElementById('signal-pills');
  if (!container || !DASHBOARD_DATA.signals) return;
  DASHBOARD_DATA.signals.forEach(function(s) {
    var badgeCls = 'signal-pill-badge';
    if (s.signal === 'BULLISH') badgeCls += ' bullish';
    else if (s.signal === 'BEARISH') badgeCls += ' bearish';
    else if (s.signal === 'ALERT') badgeCls += ' alert';
    else badgeCls += ' neutral';
    var pill = document.createElement('div');
    pill.className = 'signal-pill';
    pill.innerHTML =
      '<span class="signal-pill-label">' + s.label + '</span>' +
      '<span class="signal-pill-value" style="color:' + s.color + '">' + s.value + '</span>' +
      '<span class="' + badgeCls + '">' + s.signal + '</span>';
    container.appendChild(pill);
  });
})();

/* ── Prompt Log Toggle ────────────────────────────────────────── */
function togglePromptLog() {
  var el = document.getElementById('prompt-log-details');
  var toggle = el.previousElementSibling;
  if (el.classList.contains('open')) {
    el.classList.remove('open');
    toggle.textContent = '\u25b8 PROMPT LOG';
  } else {
    el.classList.add('open');
    toggle.textContent = '\u25be PROMPT LOG';
    if (!el.dataset.loaded) {
      el.textContent = JSON.stringify(DASHBOARD_DATA.promptLog, null, 2);
      el.dataset.loaded = '1';
    }
  }
}

/* ── Chart.js Defaults ────────────────────────────────────────── */
if (typeof Chart !== 'undefined') {
  Chart.defaults.color = '#6e7681';
  Chart.defaults.font.family = "'IBM Plex Mono', 'Courier New', monospace";
  Chart.defaults.font.size = 11;
  Chart.defaults.plugins.legend.display = false;

  var gridColor = 'rgba(255,255,255,0.06)';

  /* ── TTF vs EUA Line Chart ──────────────────────────────────── */
  (function() {
    var ctx = document.getElementById('chart-ttf-eua');
    if (!ctx) return;
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: DASHBOARD_DATA.datesTtf,
        datasets: [
          {
            label: 'TTF',
            data: DASHBOARD_DATA.ttfSeries,
            borderColor: '#58a6ff',
            backgroundColor: 'rgba(88,166,255,0.08)',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            yAxisID: 'y'
          },
          {
            label: 'EUA',
            data: DASHBOARD_DATA.euaSeries,
            borderColor: '#f0883e',
            backgroundColor: 'rgba(240,136,62,0.08)',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { color: gridColor }, ticks: { maxRotation: 45, maxTicksLimit: 8 } },
          y: { position: 'left', grid: { color: gridColor }, title: { display: true, text: 'TTF EUR/MWh', color: '#58a6ff' } },
          y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'EUA EUR/tCO\u2082', color: '#f0883e' } }
        }
      }
    });
  })();

  /* ── Spread Grouped Bar Chart ───────────────────────────────── */
  (function() {
    var ctx = document.getElementById('chart-spreads');
    if (!ctx || !DASHBOARD_DATA.spreadSeries) return;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: DASHBOARD_DATA.dateSpread,
        datasets: [
          {
            label: 'Dark Spread',
            data: DASHBOARD_DATA.spreadSeries.dark,
            backgroundColor: '#58a6ff',
            borderRadius: 0
          },
          {
            label: 'Spark Spread',
            data: DASHBOARD_DATA.spreadSeries.spark,
            backgroundColor: '#3fb950',
            borderRadius: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { color: gridColor }, ticks: { maxRotation: 45, maxTicksLimit: 10 } },
          y: { grid: { color: gridColor }, title: { display: true, text: 'EUR/MWh', color: '#6e7681' } }
        }
      }
    });
  })();

  /* ── Storage Area Chart ─────────────────────────────────────── */
  (function() {
    var ctx = document.getElementById('chart-storage');
    if (!ctx) return;
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: DASHBOARD_DATA.datesStorage,
        datasets: [
          {
            label: 'Current',
            data: DASHBOARD_DATA.storageSeries,
            borderColor: '#3fb950',
            backgroundColor: 'rgba(63,185,80,0.12)',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: true
          },
          {
            label: '5yr Avg',
            data: DASHBOARD_DATA.storageAvg,
            borderColor: 'rgba(88,166,255,0.4)',
            backgroundColor: 'rgba(88,166,255,0.06)',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.3,
            borderDash: [4, 4],
            fill: true
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { color: gridColor }, ticks: { maxRotation: 45, maxTicksLimit: 8 } },
          y: { grid: { color: gridColor }, title: { display: true, text: 'Fill %', color: '#6e7681' }, min: 0, max: 100 }
        }
      }
    });
  })();
}
</script>
"""

_CLOSE = """</body>
</html>"""

DASHBOARD_TEMPLATE: str = (
    _HEAD + _CSS + _BODY_HEADER + _BODY_METRIC_STRIP + _BODY_CHART_ROW
    + _BODY_STORAGE_SIGNAL + _BODY_DESK_NOTE + _BODY_FOOTER + _SCRIPT + _CLOSE
)
