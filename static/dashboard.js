/* ═══════════════════════════════════════════════════════════════════════
   European Cross-Commodity Risk Pack — Dashboard JavaScript
   Chart.js initialization, refresh logic, SSE streaming
   ═══════════════════════════════════════════════════════════════════════ */

/* --- Globals --- */
let chartTtfEua = null;
let chartSpreads = null;
let chartStorage = null;
const GRID_COLOR = 'rgba(255,255,255,0.06)';
const TICK_COLOR = '#6e7681';
const FONT_MONO = "'IBM Plex Mono', 'Courier New', monospace";

/* --- Signal color map --- */
const SIGNAL_COLORS = {
  BULLISH: '#3fb950', BEARISH: '#f85149',
  NEUTRAL: '#6e7681', ALERT: '#f0883e'
};
const SIGNAL_ARROWS = {
  BULLISH: '↑', BEARISH: '↓', NEUTRAL: '→', ALERT: '⚠'
};
const SIGNAL_BG = {
  BULLISH: 'bullish', BEARISH: 'bearish', NEUTRAL: '', ALERT: 'alert'
};

/* ═══ Initialization ═══ */
document.addEventListener('DOMContentLoaded', function() {
  const D = window.DASHBOARD_DATA || {};

  // Set header info
  const dateEl = document.getElementById('header-date');
  if (dateEl && D.last_run) {
    dateEl.textContent = D.last_run.split('T')[0] || new Date().toISOString().split('T')[0];
  } else if (dateEl) {
    dateEl.textContent = new Date().toISOString().split('T')[0];
  }
  updateTimestamp(D.last_run);
  updateFooter(D);

  // Render metric cards
  if (D.metrics && D.metrics.length) {
    renderMetricCards(D.metrics);
  }

  // Render signals
  renderSignals(D.metrics);

  // Render narrative
  if (D.narrative) {
    renderNarrative(D.narrative);
  }

  // Render prompt log
  if (D.prompt_log) {
    renderPromptLog(D.prompt_log);
  }

  // Initialize charts
  initCharts(D.chart_data || {});

  // Auto-status check every 60s
  setInterval(checkStatus, 60000);
});

/* ═══ Chart Initialization ═══ */
function initCharts(cd) {
  if (typeof Chart === 'undefined') return;

  Chart.defaults.color = TICK_COLOR;
  Chart.defaults.font.family = FONT_MONO;
  Chart.defaults.font.size = 11;
  Chart.defaults.plugins.legend.display = false;

  // TTF vs EUA dual-axis line
  const ctxTtf = document.getElementById('chart-ttf-eua');
  if (ctxTtf && cd.ttf_series) {
    chartTtfEua = new Chart(ctxTtf, {
      type: 'line',
      data: {
        labels: cd.dates_ttf || [],
        datasets: [
          { label: 'TTF', data: cd.ttf_series, borderColor: '#58a6ff', backgroundColor: 'rgba(88,166,255,0.08)', borderWidth: 2, pointRadius: 0, tension: 0.3, yAxisID: 'y' },
          { label: 'EUA', data: cd.eua_series, borderColor: '#f0883e', backgroundColor: 'rgba(240,136,62,0.08)', borderWidth: 2, pointRadius: 0, tension: 0.3, yAxisID: 'y1' }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { color: GRID_COLOR }, ticks: { maxRotation: 45, maxTicksLimit: 8 } },
          y: { position: 'left', grid: { color: GRID_COLOR }, title: { display: true, text: 'TTF EUR/MWh', color: '#58a6ff' } },
          y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'EUA EUR/tCO\u2082', color: '#f0883e' } }
        }
      }
    });
  }

  // Spread grouped bar
  const ctxSpr = document.getElementById('chart-spreads');
  if (ctxSpr && cd.spread_series) {
    chartSpreads = new Chart(ctxSpr, {
      type: 'bar',
      data: {
        labels: cd.dates_spread || [],
        datasets: [
          { label: 'Dark Spread', data: cd.spread_series.dark || [], backgroundColor: 'rgba(88,166,255,0.7)', borderRadius: 0 },
          { label: 'Spark Spread', data: cd.spread_series.spark || [], backgroundColor: 'rgba(63,185,80,0.7)', borderRadius: 0 }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { color: GRID_COLOR }, ticks: { maxRotation: 45, maxTicksLimit: 10 } },
          y: { grid: { color: GRID_COLOR }, title: { display: true, text: 'EUR/MWh', color: TICK_COLOR } }
        }
      }
    });
  }

  // Storage area chart
  const ctxSto = document.getElementById('chart-storage');
  if (ctxSto && cd.storage_series) {
    chartStorage = new Chart(ctxSto, {
      type: 'line',
      data: {
        labels: cd.dates_storage || [],
        datasets: [
          { label: 'Current', data: cd.storage_series, borderColor: '#3fb950', backgroundColor: 'rgba(63,185,80,0.12)', borderWidth: 2, pointRadius: 0, tension: 0.3, fill: true },
          { label: '5yr Avg', data: cd.storage_avg || [], borderColor: 'rgba(110,118,129,0.5)', backgroundColor: 'rgba(110,118,129,0.06)', borderWidth: 1.5, pointRadius: 0, tension: 0.3, borderDash: [4, 4], fill: true }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { color: GRID_COLOR }, ticks: { maxRotation: 45, maxTicksLimit: 8 } },
          y: { grid: { color: GRID_COLOR }, title: { display: true, text: 'Fill %', color: TICK_COLOR }, min: 0, max: 100 }
        }
      }
    });
  }
}

/* ═══ Metric Cards ═══ */
function renderMetricCards(metrics) {
  const container = document.getElementById('metric-cards');
  if (!container) return;
  container.innerHTML = '';
  metrics.forEach(function(m, i) {
    const sig = (m.signal || 'NEUTRAL').toUpperCase();
    const bgCls = SIGNAL_BG[sig] || '';
    const color = SIGNAL_COLORS[sig] || SIGNAL_COLORS.NEUTRAL;
    const arrow = SIGNAL_ARROWS[sig] || '→';
    const card = document.createElement('div');
    card.className = 'metric-card ' + bgCls;
    card.dataset.index = i;
    card.innerHTML =
      '<button class="metric-card-refresh" onclick="refreshPrices()" title="Refresh">⟳</button>' +
      '<div class="metric-card-label">' + (m.label || '') + '</div>' +
      '<div class="metric-card-value" style="color:' + color + '">' + arrow + ' ' + (m.value || '—') + '</div>' +
      '<div class="metric-card-unit">' + (m.unit || '') + '</div>' +
      '<div class="metric-card-signal" style="color:' + color + '">' + sig + '</div>';
    container.appendChild(card);
  });
}

function updateMetricCards(metrics) {
  renderMetricCards(metrics);
  // Pulse animation
  document.querySelectorAll('.metric-card-value').forEach(function(el) {
    el.classList.add('pulse');
    setTimeout(function() { el.classList.remove('pulse'); }, 300);
  });
}

/* ═══ Trading Signals ═══ */
function renderSignals(metrics) {
  const container = document.getElementById('signal-pills');
  if (!container || !metrics) return;
  container.innerHTML = '';

  const signalMap = [
    { key: 'TTF SPREAD', label: 'GAS TIGHTNESS', idx: 0 },
    { key: 'EUA MOM', label: 'CARBON MOMENTUM', idx: 1 },
    { key: 'SPARK SPRD', label: 'SPARK SPREAD', idx: 4 },
    { key: 'STORAGE', label: 'STORAGE BALANCE', idx: 2 }
  ];

  signalMap.forEach(function(s) {
    const m = metrics[s.idx];
    if (!m) return;
    const sig = (m.signal || 'NEUTRAL').toUpperCase();
    const color = SIGNAL_COLORS[sig] || SIGNAL_COLORS.NEUTRAL;
    const pill = document.createElement('div');
    pill.className = 'signal-pill ' + (SIGNAL_BG[sig] || 'neutral');
    pill.innerHTML =
      '<span class="signal-pill-label">' + s.label + '</span>' +
      '<span class="signal-pill-badge ' + sig.toLowerCase() + '">' + sig + '</span>' +
      '<span class="signal-pill-rationale">' + (m.value || '') + ' ' + (m.unit || '') + '</span>';
    container.appendChild(pill);
  });
}

/* ═══ Narrative Rendering ═══ */
function renderNarrative(text) {
  if (!text) return;
  const sections = parseNarrativeSections(text);
  const gasEl = document.getElementById('narrative-gas');
  const carbonEl = document.getElementById('narrative-carbon');
  const powerEl = document.getElementById('narrative-power');
  if (gasEl) gasEl.textContent = sections.gas;
  if (carbonEl) carbonEl.textContent = sections.carbon;
  if (powerEl) powerEl.textContent = sections.power;
}

function parseNarrativeSections(text) {
  const result = { gas: '', carbon: '', power: '' };
  const lower = text.toLowerCase();
  const gasIdx = lower.indexOf('gas tightness');
  const carbonIdx = lower.indexOf('carbon signal');
  const powerIdx = lower.indexOf('power curve implication');

  if (gasIdx >= 0 && carbonIdx >= 0 && powerIdx >= 0) {
    result.gas = text.substring(gasIdx + 'gas tightness'.length, carbonIdx).replace(/^[:\s\-]+/, '').trim();
    result.carbon = text.substring(carbonIdx + 'carbon signal'.length, powerIdx).replace(/^[:\s\-]+/, '').trim();
    result.power = text.substring(powerIdx + 'power curve implication'.length).replace(/^[:\s\-]+/, '').trim();
  } else {
    // Can't parse sections — put everything in gas
    result.gas = text.replace(/^\[FALLBACK MODE\]\s*/i, '').trim();
  }
  return result;
}

/* ═══ Prompt Log ═══ */
function renderPromptLog(log) {
  const el = document.getElementById('prompt-log-content');
  if (!el || !log) return;
  el.textContent = JSON.stringify(log, null, 2);
}

function togglePromptLog() {
  const el = document.getElementById('prompt-log-content');
  const toggle = document.getElementById('prompt-log-toggle');
  if (!el) return;
  if (el.classList.contains('hidden')) {
    el.classList.remove('hidden');
    toggle.textContent = '▾ PROMPT LOG';
  } else {
    el.classList.add('hidden');
    toggle.textContent = '▸ PROMPT LOG';
  }
}

/* ═══ Timestamp & Footer ═══ */
function updateTimestamp(ts) {
  const el = document.getElementById('header-timestamp');
  if (el) el.textContent = ts ? 'LAST RUN ' + ts : '—';
  const ft = document.getElementById('footer-timestamp');
  if (ft) ft.textContent = ts ? 'Generated ' + ts : '';
}

function updateFooter(D) {
  const el = document.getElementById('footer-meta');
  if (!el) return;
  const name = (D && D.analyst_name) || 'European Risk Desk';
  const email = (D && D.analyst_email) || '';
  const version = (D && D.version) || '';
  el.innerHTML = name + (email ? ' &lt;' + email + '&gt;' : '') + '<br>EURO RISK PACK v' + version;
}

/* ═══ Dropdown ═══ */
function toggleDropdown() {
  document.getElementById('download-dropdown').classList.toggle('open');
}
document.addEventListener('click', function(e) {
  const dd = document.getElementById('download-dropdown');
  if (dd && !dd.contains(e.target)) dd.classList.remove('open');
});

/* ═══ Progress Bar ═══ */
function showProgress(pct) {
  const bar = document.getElementById('progress-bar');
  if (!bar) return;
  if (pct < 0) {
    bar.style.width = '0%';
    bar.classList.remove('indeterminate');
  } else if (pct === 0) {
    bar.classList.add('indeterminate');
  } else {
    bar.classList.remove('indeterminate');
    bar.style.width = Math.min(pct, 100) + '%';
  }
}

function setButtonsDisabled(disabled) {
  ['btn-mock', 'btn-refresh-all'].forEach(function(id) {
    const el = document.getElementById(id);
    if (el) el.disabled = disabled;
  });
}

/* ═══ Refresh Functions ═══ */
async function refreshPrices() {
  try {
    showProgress(0);
    setButtonsDisabled(true);
    const resp = await fetch('/api/refresh/prices', { method: 'POST' });
    const data = await resp.json();
    if (data.metrics) updateMetricCards(data.metrics);
    if (data.metrics) renderSignals(data.metrics);
    if (data.chart_data) updateCharts(data.chart_data);
    updateTimestamp(data.timestamp);
  } catch (e) {
    console.error('refreshPrices failed:', e);
  } finally {
    showProgress(-1);
    setButtonsDisabled(false);
  }
}

async function refreshStorage() {
  try {
    showProgress(0);
    const resp = await fetch('/api/refresh/storage', { method: 'POST' });
    const data = await resp.json();
    if (chartStorage && data.storage_series) {
      chartStorage.data.labels = data.dates_storage || [];
      chartStorage.data.datasets[0].data = data.storage_series;
      chartStorage.data.datasets[1].data = data.storage_avg || [];
      chartStorage.update();
    }
  } catch (e) {
    console.error('refreshStorage failed:', e);
  } finally {
    showProgress(-1);
  }
}

async function refreshCharts() {
  try {
    showProgress(0);
    const resp = await fetch('/api/refresh/charts', { method: 'POST' });
    const data = await resp.json();
    // Charts are PNGs — but we use Chart.js so just refresh data
    if (data.status === 'ok') {
      await refreshPrices(); // re-fetch data to update Chart.js
    }
  } catch (e) {
    console.error('refreshCharts failed:', e);
  } finally {
    showProgress(-1);
  }
}

function updateCharts(cd) {
  if (chartTtfEua && cd.ttf_series) {
    chartTtfEua.data.labels = cd.dates_ttf || [];
    chartTtfEua.data.datasets[0].data = cd.ttf_series;
    chartTtfEua.data.datasets[1].data = cd.eua_series;
    chartTtfEua.update();
  }
  if (chartSpreads && cd.spread_series) {
    chartSpreads.data.labels = cd.dates_spread || [];
    chartSpreads.data.datasets[0].data = cd.spread_series.dark || [];
    chartSpreads.data.datasets[1].data = cd.spread_series.spark || [];
    chartSpreads.update();
  }
  if (chartStorage && cd.storage_series) {
    chartStorage.data.labels = cd.dates_storage || [];
    chartStorage.data.datasets[0].data = cd.storage_series;
    chartStorage.data.datasets[1].data = cd.storage_avg || [];
    chartStorage.update();
  }
}

/* ═══ SSE: Refresh All / Run Mock ═══ */
function refreshAll() { runPipeline('/api/refresh/all'); }
function runMock() { runPipeline('/api/run/mock'); }

function runPipeline(url) {
  showProgress(0);
  setButtonsDisabled(true);

  fetch(url, { method: 'POST' }).then(function(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    function read() {
      reader.read().then(function(result) {
        if (result.done) {
          showProgress(-1);
          setButtonsDisabled(false);
          return;
        }
        buffer += decoder.decode(result.value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line

        lines.forEach(function(line) {
          if (line.startsWith('data: ')) {
            try {
              const evt = JSON.parse(line.substring(6));
              handlePipelineEvent(evt);
            } catch (e) { /* ignore parse errors */ }
          }
        });
        read();
      });
    }
    read();
  }).catch(function(e) {
    console.error('Pipeline SSE failed:', e);
    showProgress(-1);
    setButtonsDisabled(false);
  });
}

function handlePipelineEvent(evt) {
  const steps = ['ingest', 'metrics', 'charts', 'narrative'];
  const idx = steps.indexOf(evt.step);
  if (idx >= 0 && evt.status === 'done') {
    showProgress(((idx + 1) / steps.length) * 100);
  }
  if (evt.step === 'complete' && evt.dashboard_data) {
    const D = evt.dashboard_data;
    if (D.metrics) { updateMetricCards(D.metrics); renderSignals(D.metrics); }
    if (D.chart_data) updateCharts(D.chart_data);
    if (D.narrative) renderNarrative(D.narrative);
    if (D.prompt_log) renderPromptLog(D.prompt_log);
    updateTimestamp(D.last_run);
    showProgress(100);
    setTimeout(function() { showProgress(-1); }, 500);
    setButtonsDisabled(false);
  }
  if (evt.step === 'error') {
    showProgress(-1);
    setButtonsDisabled(false);
    console.error('Pipeline error:', evt.message);
  }
}

/* ═══ SSE: Streaming Narrative ═══ */
function streamNarrative() {
  const gasEl = document.getElementById('narrative-gas');
  const carbonEl = document.getElementById('narrative-carbon');
  const powerEl = document.getElementById('narrative-power');
  if (!gasEl || !carbonEl || !powerEl) return;

  // Fade existing text
  [gasEl, carbonEl, powerEl].forEach(function(el) { el.classList.add('faded'); });

  setTimeout(function() {
    gasEl.innerHTML = '<span class="cursor"></span>';
    carbonEl.innerHTML = '';
    powerEl.innerHTML = '';
    [gasEl, carbonEl, powerEl].forEach(function(el) { el.classList.remove('faded'); });

    let fullText = '';
    let currentSection = 'gas';

    fetch('/api/refresh/narrative', { method: 'POST' }).then(function(response) {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      function read() {
        reader.read().then(function(result) {
          if (result.done) return;
          buffer += decoder.decode(result.value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          lines.forEach(function(line) {
            if (line.startsWith('data: ')) {
              try {
                const evt = JSON.parse(line.substring(6));
                if (evt.token) {
                  fullText += evt.token;
                  // Detect section switches
                  const lower = fullText.toLowerCase();
                  if (lower.includes('carbon signal') && currentSection === 'gas') {
                    currentSection = 'carbon';
                    carbonEl.innerHTML = '<span class="cursor"></span>';
                  } else if (lower.includes('power curve implication') && currentSection !== 'power') {
                    currentSection = 'power';
                    powerEl.innerHTML = '<span class="cursor"></span>';
                  }
                  // Append token to current section
                  const targetEl = currentSection === 'gas' ? gasEl : currentSection === 'carbon' ? carbonEl : powerEl;
                  // Remove cursor, add text, re-add cursor
                  const cursor = targetEl.querySelector('.cursor');
                  if (cursor) cursor.remove();
                  targetEl.appendChild(document.createTextNode(evt.token));
                  const newCursor = document.createElement('span');
                  newCursor.className = 'cursor';
                  targetEl.appendChild(newCursor);
                }
                if (evt.done) {
                  // Remove all cursors
                  document.querySelectorAll('.cursor').forEach(function(c) { c.remove(); });
                  updateTimestamp(evt.timestamp);
                  // Re-render cleanly
                  renderNarrative(fullText);
                }
                if (evt.error) {
                  document.querySelectorAll('.cursor').forEach(function(c) { c.remove(); });
                  gasEl.textContent = '[FALLBACK MODE] ' + evt.error;
                }
              } catch (e) { /* ignore */ }
            }
          });
          read();
        });
      }
      read();
    }).catch(function(e) {
      document.querySelectorAll('.cursor').forEach(function(c) { c.remove(); });
      gasEl.textContent = '[ERROR] ' + e.message;
    });
  }, 300);
}

/* ═══ Auto-Status Check ═══ */
async function checkStatus() {
  try {
    const resp = await fetch('/api/status');
    const data = await resp.json();
    const dot = document.getElementById('status-dot');
    if (!dot) return;
    dot.className = 'status-dot';
    if (data.error) dot.classList.add('error');
    else if (data.has_data) dot.classList.add('fresh');
    else dot.classList.add('stale');
  } catch (e) {
    const dot = document.getElementById('status-dot');
    if (dot) { dot.className = 'status-dot error'; }
  }
}
