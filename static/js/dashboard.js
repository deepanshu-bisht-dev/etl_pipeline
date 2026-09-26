(() => {
  "use strict";

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const state = {
    view: "overview",
    running: false,
    lastStatus: null,
    logsSeenIds: new Set(),
    activeRunId: null,
    tables: [],
    previewMode: "clean",
    currentTable: null,
  };

  // ---------------------------------------------------------------------
  // Navigation
  // ---------------------------------------------------------------------

  const TITLES = {
    overview: ["Overview", "Three raw sources, cleaned and loaded into the warehouse on schedule."],
    runs: ["Run history", "Every pipeline execution, with per-source stage timing."],
    data: ["Data explorer", "Browse what actually landed in the warehouse, and what got rejected."],
    sources: ["Sources", "Where each run pulls its raw data from."],
    logs: ["Activity log", "A running trace of what the pipeline is doing, stage by stage."],
  };

  function setView(view) {
    state.view = view;
    $$(".rail__link").forEach(btn => btn.classList.toggle("is-active", btn.dataset.view === view));
    $$(".view").forEach(sec => sec.classList.toggle("is-active", sec.id === `view-${view}`));
    const [title, sub] = TITLES[view];
    $("#pageTitle").textContent = title;
    $("#pageSub").textContent = sub;

    if (view === "runs") loadAllRuns();
    if (view === "data") loadTables();
    if (view === "logs") loadLogs(true);
  }

  $$(".rail__link").forEach(btn => btn.addEventListener("click", () => setView(btn.dataset.view)));

  // ---------------------------------------------------------------------
  // Formatting helpers
  // ---------------------------------------------------------------------

  const fmtInt = n => (n ?? 0).toLocaleString("en-IN");
  const fmtMs = n => n == null ? "—" : n < 1000 ? `${n} ms` : `${(n / 1000).toFixed(2)} s`;
  const fmtTime = iso => {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  };

  function statusBadge(status) {
    const cls = status === "success" ? "success" : status === "failed" ? "failed" : "running";
    const label = status === "running" ? "running" : status;
    return `<span class="badge badge--${cls}">${label}</span>`;
  }

  // ---------------------------------------------------------------------
  // Status polling + schematic + gauges
  // ---------------------------------------------------------------------

  async function pollStatus() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      state.running = data.running;
      state.lastStatus = data.stats;
      renderStatusPill(data);
      renderGauges(data.stats);
      renderSchematic(data);
    } catch (e) { /* server may be mid-restart; ignore and retry next tick */ }
  }

  function renderStatusPill(data) {
    const pill = $("#statusPill");
    const text = $("#statusText");
    pill.classList.remove("is-idle", "is-running", "is-failed");
    if (data.running) {
      pill.classList.add("is-running");
      text.textContent = "running";
    } else if (data.stats.last_run && data.stats.last_run.status === "failed") {
      pill.classList.add("is-failed");
      text.textContent = "last run failed";
    } else {
      pill.classList.add("is-idle");
      text.textContent = "idle";
    }
    $("#runBtn").disabled = data.running;
  }

  function renderGauges(stats) {
    if (!stats) return;
    $("#statRuns").textContent = fmtInt(stats.total_runs);
    $("#statSuccess").textContent = stats.success_rate;
    $("#statSuccessBar").style.width = `${stats.success_rate}%`;
    $("#statRows").textContent = fmtInt(stats.total_rows_loaded);
    $("#statDuration").textContent = fmtInt(stats.avg_duration_ms);

    const bar = $("#gaugeSuccess");
    bar.classList.toggle("gauge--bad", stats.success_rate < 60);
    bar.classList.toggle("gauge--warn", stats.success_rate >= 60 && stats.success_rate < 90);
  }

  function renderSchematic(data) {
    const running = data.running;
    $$(".flow-dot").forEach(d => d.classList.toggle("is-running", running));
    $$(".stage-node .node").forEach(n => n.classList.toggle("is-active", running));
    $("#warehouseTank .tank").classList.toggle("is-active", !running && data.stats.last_run && data.stats.last_run.status === "success");

    const lr = data.stats.last_run;
    if (lr) {
      $("#sub-extract").textContent = `${fmtInt(lr.rows_extracted)} rows`;
      $("#sub-load").textContent = `${fmtInt(lr.rows_loaded)} loaded`;
      $("#sub-validate").textContent = lr.rows_rejected ? `${fmtInt(lr.rows_rejected)} rejected` : "all valid";
      $("#sub-transform").textContent = "cleaned";
      $("#sub-warehouse").textContent = `${fmtInt(lr.rows_loaded)} rows`;

      $$(".stage-node .node").forEach(n => n.classList.toggle("is-error", !running && lr.status === "failed"));
    }
  }

  // ---------------------------------------------------------------------
  // Trigger a run
  // ---------------------------------------------------------------------

  $("#runBtn").addEventListener("click", async () => {
    $("#runBtn").disabled = true;
    await fetch("/api/run", { method: "POST" });
    pollStatus();
  });

  // ---------------------------------------------------------------------
  // Trend sparkline (SVG, hand-drawn — no chart library needed)
  // ---------------------------------------------------------------------

  async function loadTrend() {
    const res = await fetch("/api/history?limit=20");
    const points = await res.json();
    const svgW = 900, svgH = 64, pad = 6;
    const line = $("#trendLine"), fill = $("#trendFill");

    if (!points.length) {
      line.setAttribute("d", "");
      fill.setAttribute("d", "");
      return;
    }

    const max = Math.max(...points.map(p => p.rows_loaded), 1);
    const stepX = points.length > 1 ? (svgW - pad * 2) / (points.length - 1) : 0;
    const coords = points.map((p, i) => {
      const x = pad + i * stepX;
      const y = svgH - pad - (p.rows_loaded / max) * (svgH - pad * 2);
      return { x, y, status: p.status };
    });

    const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");
    const fillPath = `${linePath} L${coords[coords.length - 1].x.toFixed(1)},${svgH} L${coords[0].x.toFixed(1)},${svgH} Z`;

    line.setAttribute("d", linePath);
    fill.setAttribute("d", fillPath);

    // remove old dots, draw new ones
    $$(".trend-dot-el").forEach(el => el.remove());
    const svg = $("#trendSvg");
    coords.forEach(c => {
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", c.x);
      dot.setAttribute("cy", c.y);
      dot.setAttribute("r", 2.6);
      dot.setAttribute("class", `trend-dot trend-dot-el ${c.status === "failed" ? "is-fail" : ""}`);
      svg.appendChild(dot);
    });

    $("#trendRange").textContent = `last ${points.length} run${points.length === 1 ? "" : "s"}`;
  }

  // ---------------------------------------------------------------------
  // Recent runs (overview) + all runs (run history view)
  // ---------------------------------------------------------------------

  function runRowHtml(r) {
    return `<td>#${r.id}</td><td>${fmtTime(r.started_at)}</td><td>${r.trigger}</td>` +
           `<td>${statusBadge(r.status)}</td><td>${fmtInt(r.rows_loaded)}</td>` +
           `<td>${fmtInt(r.rows_rejected)}</td><td>${fmtMs(r.duration_ms)}</td>`;
  }

  async function loadRecentRuns() {
    const res = await fetch("/api/runs?limit=8");
    const runs = await res.json();
    const body = $("#recentRunsBody");
    body.innerHTML = runs.length
      ? runs.map(r => `<tr>${runRowHtml(r)}</tr>`).join("")
      : `<tr><td colspan="7"><div class="empty-state">No runs yet — click "Run pipeline" to start one.</div></td></tr>`;
  }

  async function loadAllRuns() {
    const res = await fetch("/api/runs?limit=100");
    const runs = await res.json();
    $("#runsCount").textContent = `${runs.length} run${runs.length === 1 ? "" : "s"}`;
    const body = $("#allRunsBody");
    if (!runs.length) {
      body.innerHTML = `<tr><td colspan="10"><div class="empty-state">No runs yet.</div></td></tr>`;
      return;
    }
    body.innerHTML = runs.map(r => `
      <tr class="is-clickable" data-run-id="${r.id}">
        <td>▸</td><td>#${r.id}</td><td>${fmtTime(r.started_at)}</td><td>${fmtTime(r.finished_at)}</td>
        <td>${r.trigger}</td><td>${statusBadge(r.status)}</td>
        <td>${fmtInt(r.rows_extracted)}</td><td>${fmtInt(r.rows_loaded)}</td>
        <td>${fmtInt(r.rows_rejected)}</td><td>${fmtMs(r.duration_ms)}</td>
      </tr>
      <tr class="stage-row" data-stage-for="${r.id}"><td colspan="10"></td></tr>
    `).join("");

    $$("#allRunsBody tr.is-clickable").forEach(row => {
      row.addEventListener("click", () => toggleStageRow(row.dataset.runId));
    });
  }

  async function toggleStageRow(runId) {
    const stageRow = $(`tr.stage-row[data-stage-for="${runId}"]`);
    const isOpen = stageRow.classList.contains("is-open");
    $$("tr.stage-row").forEach(r => r.classList.remove("is-open"));
    if (isOpen) return;

    const cell = $("td", stageRow);
    cell.innerHTML = `<div class="empty-state">Loading stage detail…</div>`;
    stageRow.classList.add("is-open");

    const res = await fetch(`/api/runs/${runId}`);
    const run = await res.json();
    if (!run.stages || !run.stages.length) {
      cell.innerHTML = `<div class="empty-state">No stage detail recorded for this run.</div>`;
      return;
    }
    cell.innerHTML = `<div class="stage-strip">${run.stages.map(s => `
      <div class="stage-chip ${s.status}">
        <div class="stage-chip__top">
          <span class="stage-chip__stage">${s.stage}</span>
          <span class="stage-chip__ms">${fmtMs(s.duration_ms)}</span>
        </div>
        <div class="stage-chip__source">${s.source_name}</div>
        <div class="stage-chip__rows">${fmtInt(s.rows_in)} in → ${fmtInt(s.rows_out)} out</div>
        <div class="stage-chip__detail">${s.detail ?? ""}</div>
      </div>`).join("")}</div>`;
  }

  // ---------------------------------------------------------------------
  // Data explorer
  // ---------------------------------------------------------------------

  async function loadTables() {
    if (state.tables.length) return renderTableOptions();
    const res = await fetch("/api/tables");
    state.tables = await res.json();
    renderTableOptions();
  }

  function renderTableOptions() {
    const sel = $("#tableSelect");
    sel.innerHTML = state.tables.map(t => `<option value="${t.source}">${t.source}</option>`).join("");
    state.currentTable = state.tables[0]?.source ?? null;
    loadPreview();
  }

  $("#tableSelect").addEventListener("change", e => {
    state.currentTable = e.target.value;
    loadPreview();
  });

  $("#cleanRejectToggle").addEventListener("click", e => {
    const btn = e.target.closest("button");
    if (!btn) return;
    $$("#cleanRejectToggle button").forEach(b => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    state.previewMode = btn.dataset.mode;
    loadPreview();
  });

  async function loadPreview() {
    if (!state.currentTable) return;
    const meta = state.tables.find(t => t.source === state.currentTable);
    const tableName = state.previewMode === "clean" ? meta.table : meta.rejects_table;

    const res = await fetch(`/api/preview/${tableName}?limit=50`);
    const data = await res.json();

    const head = $("#previewHead");
    const body = $("#previewBody");
    if (!data.columns.length) {
      head.innerHTML = "";
      body.innerHTML = `<tr><td><div class="empty-state">No data yet — run the pipeline first.</div></td></tr>`;
      $("#previewCount").textContent = "";
      return;
    }

    head.innerHTML = `<tr>${data.columns.map(c => `<th>${c}</th>`).join("")}</tr>`;
    body.innerHTML = data.rows.map(row => `<tr>${row.map(v => `<td>${v ?? ""}</td>`).join("")}</tr>`).join("")
      || `<tr><td colspan="${data.columns.length}"><div class="empty-state">Empty table.</div></td></tr>`;
    $("#previewCount").textContent = `${fmtInt(data.row_count)} row${data.row_count === 1 ? "" : "s"} total, showing ${data.rows.length}`;
  }

  // ---------------------------------------------------------------------
  // Sources — drag/drop & click-to-upload
  // ---------------------------------------------------------------------

  $$('#sourcesGrid input[type="file"]').forEach(input => {
    input.addEventListener("change", async () => {
      const file = input.files[0];
      if (!file) return;
      const source = input.dataset.source;
      const statusEl = $(`#status-${source}`);
      statusEl.textContent = "Uploading…";
      statusEl.style.color = "var(--ink-faint)";

      const form = new FormData();
      form.append("file", file);
      try {
        const res = await fetch(`/api/upload/${source}`, { method: "POST", body: form });
        const data = await res.json();
        if (res.ok) {
          statusEl.textContent = `Saved. Run the pipeline to pick up "${file.name}".`;
          statusEl.style.color = "var(--sage)";
        } else {
          statusEl.textContent = data.error || "Upload failed.";
          statusEl.style.color = "var(--rust)";
        }
      } catch (e) {
        statusEl.textContent = "Upload failed — is the server running?";
        statusEl.style.color = "var(--rust)";
      }
    });
  });

  // ---------------------------------------------------------------------
  // Activity log (polling terminal)
  // ---------------------------------------------------------------------

  async function loadLogs(replace = false) {
    const res = await fetch("/api/logs?limit=150");
    const logs = await res.json();
    const term = $("#terminal");

    if (replace) {
      term.innerHTML = "";
      state.logsSeenIds.clear();
    }

    const fresh = logs.filter(l => !state.logsSeenIds.has(l.id));
    fresh.forEach(l => {
      state.logsSeenIds.add(l.id);
      const line = document.createElement("div");
      line.className = `log-line ${l.level}`;
      const time = new Date(l.ts).toLocaleTimeString();
      line.innerHTML = `<span class="log-line__ts">${time}</span><span class="log-line__lvl">${l.level}</span><span class="log-line__msg">${escapeHtml(l.message)}</span>`;
      term.appendChild(line);
    });

    if (!logs.length) {
      term.innerHTML = `<div class="empty-state">No activity yet.</div>`;
    } else if (fresh.length) {
      term.scrollTop = term.scrollHeight;
    }
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------

  function refreshAll() {
    pollStatus();
    loadTrend();
    loadRecentRuns();
    if (state.view === "runs") loadAllRuns();
    if (state.view === "logs") loadLogs();
  }

  refreshAll();
  setInterval(refreshAll, 3000);
})();
