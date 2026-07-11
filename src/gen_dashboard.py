# -*- coding: utf-8 -*-
"""
gen_dashboard.py
Reads test_results.jsonl and generates a self-contained dashboard.html
that can be opened directly in any browser (no server needed).
"""

import json, os, sys

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH  = os.path.join(BASE_DIR, "test_results.jsonl")
OUTPUT_PATH = os.path.join(BASE_DIR, "dashboard.html")

if not os.path.exists(INPUT_PATH):
    print(f"[ERROR] {INPUT_PATH} not found.")
    print("Run:  venv\\Scripts\\python src\\classify.py test_log.jsonl test_results.jsonl")
    sys.exit(1)

events = []
with open(INPUT_PATH, "r") as f:
    for line in f:
        if line.strip():
            events.append(json.loads(line))

data_json = json.dumps(events)
print(f"Loaded {len(events):,} classified events")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DLP ML Incident Classifier — PoC Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg:          #0a0d14;
    --surface:     #111827;
    --surface2:    #1a2235;
    --border:      rgba(255,255,255,0.07);
    --text:        #e2e8f0;
    --muted:       #64748b;
    --critical:    #ef4444;
    --critical-bg: rgba(239,68,68,0.12);
    --high:        #f59e0b;
    --high-bg:     rgba(245,158,11,0.12);
    --medium:      #22c55e;
    --medium-bg:   rgba(34,197,94,0.12);
    --accent:      #6366f1;
    --accent-bg:   rgba(99,102,241,0.15);
  }}

  body {{
    font-family: 'Inter', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 0;
  }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
    border-bottom: 1px solid var(--border);
    padding: 24px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(10px);
  }}
  .header-left h1 {{
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    background: linear-gradient(90deg, #a5b4fc, #e879f9);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .header-left p {{
    font-size: 0.78rem;
    color: var(--muted);
    margin-top: 3px;
  }}
  .header-badge {{
    background: var(--accent-bg);
    border: 1px solid rgba(99,102,241,0.3);
    color: #a5b4fc;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
  }}

  /* ── Main layout ── */
  .main {{
    padding: 32px 40px;
    max-width: 1600px;
    margin: 0 auto;
  }}

  /* ── Stat cards ── */
  .stats {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 20px;
    margin-bottom: 32px;
  }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    position: relative;
    overflow: hidden;
    transition: transform 0.2s, box-shadow 0.2s;
    cursor: default;
  }}
  .stat-card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.4);
  }}
  .stat-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 16px 16px 0 0;
  }}
  .stat-card.critical::before {{ background: var(--critical); }}
  .stat-card.high::before     {{ background: var(--high); }}
  .stat-card.medium::before   {{ background: var(--medium); }}
  .stat-card.total::before    {{ background: var(--accent); }}

  .stat-label {{
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 12px;
  }}
  .stat-num {{
    font-size: 2.6rem;
    font-weight: 700;
    letter-spacing: -0.04em;
    line-height: 1;
  }}
  .stat-card.critical .stat-num {{ color: var(--critical); }}
  .stat-card.high     .stat-num {{ color: var(--high); }}
  .stat-card.medium   .stat-num {{ color: var(--medium); }}
  .stat-card.total    .stat-num {{ color: #a5b4fc; }}
  .stat-sub {{
    font-size: 0.75rem;
    color: var(--muted);
    margin-top: 8px;
  }}

  /* ── Charts row ── */
  .charts {{
    display: grid;
    grid-template-columns: 300px 1fr 1fr;
    gap: 20px;
    margin-bottom: 32px;
  }}
  .chart-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
  }}
  .chart-title {{
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 20px;
  }}
  .chart-wrap {{
    position: relative;
    height: 200px;
  }}

  /* ── Filters ── */
  .filters {{
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }}
  .filter-btn {{
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 7px 16px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
  }}
  .filter-btn:hover, .filter-btn.active {{
    border-color: var(--accent);
    color: #a5b4fc;
    background: var(--accent-bg);
  }}
  .filter-btn.active-critical {{ border-color: var(--critical); color: var(--critical); background: var(--critical-bg); }}
  .filter-btn.active-high     {{ border-color: var(--high);     color: var(--high);     background: var(--high-bg); }}
  .filter-btn.active-medium   {{ border-color: var(--medium);   color: var(--medium);   background: var(--medium-bg); }}

  .search-box {{
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-family: inherit;
    width: 240px;
    outline: none;
    transition: border-color 0.15s;
  }}
  .search-box:focus {{
    border-color: var(--accent);
  }}
  .search-box::placeholder {{ color: var(--muted); }}

  .filter-label {{
    font-size: 0.75rem;
    color: var(--muted);
    margin-left: auto;
  }}

  /* ── Table ── */
  .table-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
  }}
  .table-header {{
    padding: 18px 24px;
    border-bottom: 1px solid var(--border);
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--muted);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }}
  thead th {{
    padding: 12px 16px;
    text-align: left;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    background: var(--surface2);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }}
  thead th:hover {{ color: var(--text); }}
  tbody tr {{
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
    cursor: pointer;
  }}
  tbody tr:last-child {{ border-bottom: none; }}
  tbody tr:hover {{ background: rgba(255,255,255,0.03); }}
  tbody tr.expanded {{ background: rgba(99,102,241,0.05); }}
  td {{
    padding: 12px 16px;
    vertical-align: middle;
    white-space: nowrap;
  }}
  .sender-cell {{
    font-family: 'Courier New', monospace;
    font-size: 0.78rem;
    color: #94a3b8;
  }}
  .receiver-cell {{
    font-family: 'Courier New', monospace;
    font-size: 0.78rem;
    color: #64748b;
  }}

  /* ── Severity pill ── */
  .pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }}
  .pill.CRITICAL {{ background: var(--critical-bg); color: var(--critical); border: 1px solid rgba(239,68,68,0.3); }}
  .pill.HIGH     {{ background: var(--high-bg);     color: var(--high);     border: 1px solid rgba(245,158,11,0.3); }}
  .pill.MEDIUM   {{ background: var(--medium-bg);   color: var(--medium);   border: 1px solid rgba(34,197,94,0.3); }}
  .pill::before {{
    content: '';
    width: 6px; height: 6px;
    border-radius: 50%;
    background: currentColor;
  }}
  .pill.CRITICAL::before {{ animation: pulse-red 1.5s infinite; }}

  @keyframes pulse-red {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50%       {{ opacity: 0.5; transform: scale(1.4); }}
  }}

  /* ── Action badge ── */
  .action {{
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--muted);
    letter-spacing: 0.03em;
  }}

  /* ── Confidence bar ── */
  .conf-cell {{
    min-width: 100px;
  }}
  .conf-bar-wrap {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .conf-bar {{
    flex: 1;
    height: 4px;
    background: rgba(255,255,255,0.08);
    border-radius: 2px;
    overflow: hidden;
  }}
  .conf-fill {{
    height: 100%;
    border-radius: 2px;
    background: linear-gradient(90deg, #6366f1, #a855f7);
  }}
  .conf-num {{
    font-size: 0.7rem;
    color: var(--muted);
    width: 36px;
    text-align: right;
  }}

  /* ── Expanded row ── */
  .expand-row td {{
    padding: 0;
    background: rgba(15,23,42,0.6);
  }}
  .expand-inner {{
    padding: 16px 24px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    border-top: 1px solid var(--border);
  }}
  .ctx-item {{
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
  }}
  .ctx-label {{
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--muted);
    margin-bottom: 6px;
  }}
  .ctx-val {{
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text);
  }}
  .ctx-val.warn {{ color: var(--high); }}
  .ctx-val.danger {{ color: var(--critical); }}
  .ctx-val.safe {{ color: var(--medium); }}

  /* ── Pagination ── */
  .pagination {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 16px 24px;
    border-top: 1px solid var(--border);
    justify-content: flex-end;
  }}
  .page-btn {{
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 0.75rem;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;
  }}
  .page-btn:hover {{ border-color: var(--accent); color: #a5b4fc; }}
  .page-btn.active {{ background: var(--accent-bg); border-color: var(--accent); color: #a5b4fc; }}
  .page-btn:disabled {{ opacity: 0.3; cursor: not-allowed; }}
  .page-info {{ font-size: 0.75rem; color: var(--muted); }}

  /* ── Scrollbar ── */
  ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
  ::-webkit-scrollbar-track {{ background: var(--bg); }}
  ::-webkit-scrollbar-thumb {{ background: var(--surface2); border-radius: 3px; }}

  /* ── Responsive ── */
  @media (max-width: 900px) {{
    .main {{ padding: 20px 16px; }}
    .charts {{ grid-template-columns: 1fr; }}
    .header {{ padding: 16px 20px; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>DLP ML Incident Classifier</h1>
    <p>Behavioral Baseline Engine — Phase 1 PoC &nbsp;·&nbsp; BIN_001 Email DLP</p>
  </div>
  <div class="header-badge">PROOF OF CONCEPT</div>
</div>

<div class="main">

  <!-- Stat Cards -->
  <div class="stats" id="stats"></div>

  <!-- Charts -->
  <div class="charts">
    <div class="chart-card">
      <div class="chart-title">Severity Distribution</div>
      <div class="chart-wrap"><canvas id="donutChart"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">Policy Mix by Severity</div>
      <div class="chart-wrap"><canvas id="policyChart"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">After-Hours vs Business Hours</div>
      <div class="chart-wrap"><canvas id="hoursChart"></canvas></div>
    </div>
  </div>

  <!-- Filters -->
  <div class="filters">
    <button class="filter-btn active" onclick="setFilter('ALL', this)">All</button>
    <button class="filter-btn" onclick="setFilter('CRITICAL', this)">🔴 Critical</button>
    <button class="filter-btn" onclick="setFilter('HIGH', this)">🟡 High</button>
    <button class="filter-btn" onclick="setFilter('MEDIUM', this)">🟢 Medium</button>
    <input class="search-box" id="searchBox" type="text" placeholder="Search sender / policy…" oninput="onSearch()">
    <span class="filter-label" id="filterLabel"></span>
  </div>

  <!-- Table -->
  <div class="table-card">
    <div class="table-header">Classified Events — click any row for behavioral context</div>
    <div style="overflow-x:auto">
      <table id="eventsTable">
        <thead>
          <tr>
            <th>#</th>
            <th onclick="sortBy('sender')">Sender ↕</th>
            <th onclick="sortBy('dlp_policy')">Policy ↕</th>
            <th onclick="sortBy('predicted_severity')">Severity ↕</th>
            <th>Confidence</th>
            <th onclick="sortBy('timestamp')">Timestamp ↕</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
    <div class="pagination" id="pagination"></div>
  </div>

</div>

<script>
const RAW = {data_json};

// ── State ──────────────────────────────────────────────────────────────────
let filtered  = [...RAW];
let sortKey   = 'timestamp';
let sortDir   = 1;
let page      = 1;
const PER_PAGE = 25;
let expandedRow = null;

// ── Severity counts ─────────────────────────────────────────────────────────
function counts(arr) {{
  return arr.reduce((acc, e) => {{
    acc[e.predicted_severity] = (acc[e.predicted_severity] || 0) + 1;
    return acc;
  }}, {{}});
}}

// ── Stat cards ───────────────────────────────────────────────────────────────
function renderStats() {{
  const c = counts(RAW);
  const total = RAW.length;
  const html = [
    ['total',    'Total Events',   total, `Across all severity levels`],
    ['critical', 'Critical',       c.CRITICAL||0, `Escalate immediately`],
    ['high',     'High',           c.HIGH||0,     `Human review required`],
    ['medium',   'Medium',         c.MEDIUM||0,   `Log and monitor`],
  ].map(([cls, lbl, num, sub]) => `
    <div class="stat-card ${{cls}}">
      <div class="stat-label">${{lbl}}</div>
      <div class="stat-num" id="stat-${{cls}}">0</div>
      <div class="stat-sub">${{sub}}</div>
    </div>
  `).join('');
  document.getElementById('stats').innerHTML = html;

  // Animate numbers
  [['stat-total', total], ['stat-critical', c.CRITICAL||0],
   ['stat-high', c.HIGH||0], ['stat-medium', c.MEDIUM||0]].forEach(([id, target]) => {{
    let v = 0;
    const step = Math.ceil(target / 40);
    const el = document.getElementById(id);
    const t = setInterval(() => {{
      v = Math.min(v + step, target);
      el.textContent = v.toLocaleString();
      if (v >= target) clearInterval(t);
    }}, 20);
  }});
}}

// ── Charts ───────────────────────────────────────────────────────────────────
function renderCharts() {{
  const c = counts(RAW);
  const chartDefaults = {{
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8', font: {{ family: 'Inter', size: 11 }} }} }} }},
    scales:  {{ x: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }} }},
  }};

  // Donut
  new Chart(document.getElementById('donutChart'), {{
    type: 'doughnut',
    data: {{
      labels: ['Critical', 'High', 'Medium'],
      datasets: [{{ data: [c.CRITICAL||0, c.HIGH||0, c.MEDIUM||0],
        backgroundColor: ['rgba(239,68,68,0.8)', 'rgba(245,158,11,0.8)', 'rgba(34,197,94,0.8)'],
        borderColor: ['#ef4444','#f59e0b','#22c55e'], borderWidth: 2, hoverOffset: 6 }}]
    }},
    options: {{ cutout: '70%', plugins: {{ legend: {{ position: 'bottom',
      labels: {{ color: '#94a3b8', font: {{ family: 'Inter', size: 11 }}, padding: 16 }} }} }},
      animation: {{ animateRotate: true, duration: 800 }} }}
  }});

  // Policy by severity
  const pols = ['PII_PAN','PII_AADHAAR','PII_DL'];
  const sevs = ['CRITICAL','HIGH','MEDIUM'];
  const polData = sevs.map(sev => pols.map(pol =>
    RAW.filter(e => e.predicted_severity === sev && e.dlp_policy === pol).length
  ));
  new Chart(document.getElementById('policyChart'), {{
    type: 'bar',
    data: {{
      labels: pols,
      datasets: sevs.map((sev, i) => ({{
        label: sev,
        data: polData[i],
        backgroundColor: ['rgba(239,68,68,0.7)','rgba(245,158,11,0.7)','rgba(34,197,94,0.7)'][i],
        borderRadius: 4,
      }}))
    }},
    options: {{ ...chartDefaults, responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#94a3b8',
        font: {{ family:'Inter', size:10 }}, padding: 12 }} }} }},
      scales: {{ x: {{ stacked: false, ticks: {{ color:'#64748b' }},
        grid: {{ color:'rgba(255,255,255,0.04)' }} }},
        y: {{ ticks: {{ color:'#64748b' }}, grid: {{ color:'rgba(255,255,255,0.04)' }} }} }} }}
  }});

  // After-hours
  const biz  = RAW.filter(e => {{ const h = parseInt(e.timestamp.split('T')[1]); return h >= 8 && h < 18; }});
  const aft  = RAW.filter(e => {{ const h = parseInt(e.timestamp.split('T')[1]); return h < 8 || h >= 18; }});
  const wknd = RAW.filter(e => {{ const d = new Date(e.timestamp).getDay(); return d===0||d===6; }});
  new Chart(document.getElementById('hoursChart'), {{
    type: 'bar',
    data: {{
      labels: ['Business Hours', 'After Hours', 'Weekend'],
      datasets: [
        {{ label: 'Critical', data: [
          biz.filter(e=>e.predicted_severity==='CRITICAL').length,
          aft.filter(e=>e.predicted_severity==='CRITICAL').length,
          wknd.filter(e=>e.predicted_severity==='CRITICAL').length],
          backgroundColor: 'rgba(239,68,68,0.7)', borderRadius: 4 }},
        {{ label: 'High', data: [
          biz.filter(e=>e.predicted_severity==='HIGH').length,
          aft.filter(e=>e.predicted_severity==='HIGH').length,
          wknd.filter(e=>e.predicted_severity==='HIGH').length],
          backgroundColor: 'rgba(245,158,11,0.7)', borderRadius: 4 }},
        {{ label: 'Medium', data: [
          biz.filter(e=>e.predicted_severity==='MEDIUM').length,
          aft.filter(e=>e.predicted_severity==='MEDIUM').length,
          wknd.filter(e=>e.predicted_severity==='MEDIUM').length],
          backgroundColor: 'rgba(34,197,94,0.7)', borderRadius: 4 }},
      ]
    }},
    options: {{ ...chartDefaults, responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'bottom', labels: {{ color:'#94a3b8',
        font:{{ family:'Inter', size:10 }}, padding:12 }} }} }},
      scales: {{ x: {{ stacked: true, ticks:{{color:'#64748b'}},
        grid:{{color:'rgba(255,255,255,0.04)'}} }},
        y: {{ stacked: true, ticks:{{color:'#64748b'}},
        grid:{{color:'rgba(255,255,255,0.04)'}} }} }} }}
  }});
}}

// ── Filter / search ──────────────────────────────────────────────────────────
let currentFilter = 'ALL';
let currentSearch = '';

function setFilter(f, btn) {{
  currentFilter = f;
  page = 1;
  document.querySelectorAll('.filter-btn').forEach(b => {{
    b.className = 'filter-btn';
  }});
  btn.className = 'filter-btn active' + (f !== 'ALL' ? ' active-' + f.toLowerCase() : '');
  applyFilters();
}}

function onSearch() {{
  currentSearch = document.getElementById('searchBox').value.toLowerCase();
  page = 1;
  applyFilters();
}}

function applyFilters() {{
  filtered = RAW.filter(e => {{
    const sevOk  = currentFilter === 'ALL' || e.predicted_severity === currentFilter;
    const srchOk = !currentSearch ||
      e.sender.toLowerCase().includes(currentSearch) ||
      e.dlp_policy.toLowerCase().includes(currentSearch) ||
      e.receiver.toLowerCase().includes(currentSearch);
    return sevOk && srchOk;
  }});
  document.getElementById('filterLabel').textContent =
    `Showing ${{filtered.length.toLocaleString()}} of ${{RAW.length.toLocaleString()}} events`;
  renderTable();
}}

// ── Sort ─────────────────────────────────────────────────────────────────────
function sortBy(key) {{
  if (sortKey === key) sortDir *= -1;
  else {{ sortKey = key; sortDir = 1; }}
  filtered.sort((a, b) => {{
    const av = a[key] || '';
    const bv = b[key] || '';
    return av < bv ? -sortDir : av > bv ? sortDir : 0;
  }});
  renderTable();
}}

// ── Table rendering ──────────────────────────────────────────────────────────
function renderTable() {{
  const start = (page - 1) * PER_PAGE;
  const slice = filtered.slice(start, start + PER_PAGE);
  const body  = document.getElementById('tableBody');

  body.innerHTML = slice.map((ev, idx) => {{
    const globalIdx = start + idx;
    const ctx = ev.behavioral_context || {{}};
    const ts  = ev.timestamp.replace('T', ' ');
    const conf = ev.confidence_pct || 0;

    const ctxColor = (val, warn, crit) =>
      val >= crit ? 'danger' : val >= warn ? 'warn' : 'safe';

    return `
      <tr onclick="toggleExpand(${{globalIdx}}, this)" id="row-${{globalIdx}}">
        <td style="color:var(--muted);font-size:0.7rem">${{globalIdx+1}}</td>
        <td class="sender-cell">${{ev.sender}}</td>
        <td><span style="font-size:0.75rem;color:#94a3b8">${{ev.dlp_policy}}</span></td>
        <td><span class="pill ${{ev.predicted_severity}}">${{ev.predicted_severity}}</span></td>
        <td class="conf-cell">
          <div class="conf-bar-wrap">
            <div class="conf-bar"><div class="conf-fill" style="width:${{conf}}%"></div></div>
            <span class="conf-num">${{conf}}%</span>
          </div>
        </td>
        <td style="font-size:0.75rem;color:var(--muted);font-family:'Courier New',monospace">${{ts}}</td>
        <td class="action">${{ev.recommended_action.replace(/_/g,' ')}}</td>
      </tr>
      <tr class="expand-row" id="expand-${{globalIdx}}" style="display:none">
        <td colspan="7">
          <div class="expand-inner">
            <div class="ctx-item">
              <div class="ctx-label">30-Day Violations</div>
              <div class="ctx-val ${{ctxColor(ctx.sender_30d_violations,5,15)}}">${{ctx.sender_30d_violations ?? '—'}}</div>
            </div>
            <div class="ctx-item">
              <div class="ctx-label">7-Day Violations</div>
              <div class="ctx-val ${{ctxColor(ctx.sender_7d_violations,3,7)}}">${{ctx.sender_7d_violations ?? '—'}}</div>
            </div>
            <div class="ctx-item">
              <div class="ctx-label">Days Since Last</div>
              <div class="ctx-val ${{ctx.days_since_last_violation > 30 ? 'safe' : ctx.days_since_last_violation < 1 ? 'danger' : 'warn'}}">${{ctx.days_since_last_violation ?? '—'}}</div>
            </div>
            <div class="ctx-item">
              <div class="ctx-label">Repeat Policy</div>
              <div class="ctx-val ${{ctx.is_repeat_policy ? 'warn' : 'safe'}}">${{ctx.is_repeat_policy ? 'YES' : 'NO'}}</div>
            </div>
            <div class="ctx-item">
              <div class="ctx-label">New Receiver</div>
              <div class="ctx-val ${{ctx.is_new_receiver ? 'warn' : 'safe'}}">${{ctx.is_new_receiver ? 'YES' : 'NO'}}</div>
            </div>
            <div class="ctx-item">
              <div class="ctx-label">After Hours</div>
              <div class="ctx-val ${{ctx.is_after_hours ? 'danger' : 'safe'}}">${{ctx.is_after_hours ? 'YES' : 'NO'}}</div>
            </div>
            <div class="ctx-item">
              <div class="ctx-label">Weekend</div>
              <div class="ctx-val ${{ctx.is_weekend ? 'warn' : 'safe'}}">${{ctx.is_weekend ? 'YES' : 'NO'}}</div>
            </div>
            <div class="ctx-item">
              <div class="ctx-label">Receiver</div>
              <div class="ctx-val" style="font-size:0.75rem;font-family:monospace">${{ev.receiver}}</div>
            </div>
          </div>
        </td>
      </tr>
    `;
  }}).join('');

  renderPagination();
}}

function toggleExpand(idx, row) {{
  const expandRow = document.getElementById('expand-' + idx);
  if (!expandRow) return;
  const isOpen = expandRow.style.display !== 'none';
  // Close all
  document.querySelectorAll('.expand-row').forEach(r => r.style.display = 'none');
  document.querySelectorAll('tbody tr').forEach(r => r.classList.remove('expanded'));
  if (!isOpen) {{
    expandRow.style.display = '';
    row.classList.add('expanded');
  }}
}}

// ── Pagination ───────────────────────────────────────────────────────────────
function renderPagination() {{
  const total = Math.ceil(filtered.length / PER_PAGE);
  const pg    = document.getElementById('pagination');
  if (total <= 1) {{ pg.innerHTML = ''; return; }}

  let html = `<span class="page-info">Page ${{page}} of ${{total}}</span>`;
  html += `<button class="page-btn" onclick="goPage(${{page-1}})" ${{page===1?'disabled':''}}>←</button>`;

  const range = [];
  for (let i = Math.max(1,page-2); i <= Math.min(total, page+2); i++) range.push(i);
  range.forEach(p => {{
    html += `<button class="page-btn ${{p===page?'active':''}}" onclick="goPage(${{p}})">${{p}}</button>`;
  }});

  html += `<button class="page-btn" onclick="goPage(${{page+1}})" ${{page===total?'disabled':''}}>→</button>`;
  pg.innerHTML = html;
}}

function goPage(p) {{
  page = p;
  renderTable();
  window.scrollTo(0, document.getElementById('eventsTable').offsetTop - 20);
}}

// ── Init ─────────────────────────────────────────────────────────────────────
window.onload = () => {{
  renderStats();
  renderCharts();
  applyFilters();
}};
</script>
</body>
</html>"""

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Dashboard -> {OUTPUT_PATH}")
print("Open dashboard.html in your browser.")
