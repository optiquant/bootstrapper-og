"use strict";

// The UI is a thin client of the read-only run API. It never imports the engine; it only reads
// what `bootstrapper run` froze and `bootstrapper.service` (or the bundled fixtures) serves.
//
// Two data sources, same logical resources:
//   * "bundled" -> static JSON committed under ./data (so GitHub Pages works standalone)
//   * "live"    -> a running FastAPI service (GET /runs, /runs/{id}, /runs/{id}/metrics)

const BUNDLED = {
  runs: () => "./data/runs.json",
  run: (id) => `./data/${encodeURIComponent(id)}.json`,
  metrics: (id) => `./data/${encodeURIComponent(id)}.metrics.json`,
};

function liveResolver(base) {
  const root = base.replace(/\/+$/, "");
  return {
    runs: () => `${root}/runs`,
    run: (id) => `${root}/runs/${encodeURIComponent(id)}`,
    metrics: (id) => `${root}/runs/${encodeURIComponent(id)}/metrics`,
  };
}

const state = {
  resolver: BUNDLED,
  runs: [],
  activeId: null,
};

const el = (id) => document.getElementById(id);

async function getJSON(url) {
  const resp = await fetch(url, { headers: { Accept: "application/json" } });
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText} for ${url}`);
  return resp.json();
}

// ---- rendering -------------------------------------------------------------------------------

function fmtPct(x) {
  return (x * 100).toFixed(1) + "%";
}

function renderRuns(runs) {
  const list = el("runs-list");
  list.innerHTML = "";
  if (!runs.length) {
    el("runs-status").textContent = "No runs found.";
    return;
  }
  el("runs-status").textContent = `${runs.length} run${runs.length === 1 ? "" : "s"}`;
  for (const m of runs) {
    const li = document.createElement("li");
    li.className = "run-item";
    li.dataset.runId = m.run_id;
    li.innerHTML =
      `<div class="rid">${m.run_id}</div>` +
      `<div class="meta">${m.dataset_id} · ${m.grid?.name ?? "?"} · ` +
      `${m.n_chunks} chunks · ${m.n_queries} queries</div>`;
    li.addEventListener("click", () => selectRun(m.run_id));
    list.appendChild(li);
  }
}

function setActive(id) {
  state.activeId = id;
  for (const li of document.querySelectorAll(".run-item")) {
    li.classList.toggle("active", li.dataset.runId === id);
  }
}

async function selectRun(id) {
  setActive(id);
  const detail = el("detail");
  detail.className = "";
  detail.innerHTML = `<div class="status">Loading ${id}…</div>`;
  try {
    const [manifest, metrics] = await Promise.all([
      getJSON(state.resolver.run(id)),
      getJSON(state.resolver.metrics(id)),
    ]);
    detail.innerHTML = renderDetail(manifest, metrics);
  } catch (err) {
    detail.innerHTML = `<div class="source-hint error">Could not load run: ${err.message}</div>`;
  }
}

function fact(k, v) {
  return `<div class="fact"><span class="k">${k}</span><span class="v">${v}</span></div>`;
}

function renderDetail(m, metrics) {
  const coverageBadge =
    m.coverage >= 1
      ? `<span class="badge clean">resolver ${fmtPct(m.coverage)} clean</span>`
      : `<span class="badge warn">resolver ${fmtPct(m.coverage)}</span>`;

  const facts =
    fact("dataset", m.dataset_id) +
    fact("grid", m.grid?.name ?? "?") +
    fact("embeddings", (m.embedding_ids || []).join(", ")) +
    fact("documents", m.n_documents) +
    fact("chunks", m.n_chunks) +
    fact("queries", m.n_queries) +
    fact("created", (m.created_at || "").slice(0, 19).replace("T", " "));

  return (
    `<h3>${m.run_id} ${coverageBadge}</h3>` +
    `<div class="facts">${facts}</div>` +
    `<div class="section-label">Retrieval quality <span class="ci">(mean over ${m.n_queries} queries)</span></div>` +
    renderQuality(metrics) +
    `<div class="section-label">Cost</div>` +
    renderCost(metrics) +
    (m.latency_illustrative
      ? `<p class="note">⚠ Latency is <strong>illustrative</strong> on a labeled corpus — trust the frontier shape from a scale corpus, not absolute deltas.</p>`
      : "") +
    (m.notes ? `<p class="note">${m.notes}</p>` : "")
  );
}

// ---- metric aggregation (client-side, mirrors the engine) ------------------------------------

function families(metrics) {
  return [...new Set(metrics.map((r) => r.index_family))];
}

function perQuery(metrics, family, metricName, k) {
  return metrics
    .filter((r) => r.index_family === family && r.metric_name === metricName && r.k === k)
    .map((r) => r.metric_value);
}

function mean(xs) {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN;
}

// Deterministic LCG so the bootstrap band does not flicker on reload.
function lcg(seed) {
  let s = seed >>> 0;
  return () => {
    s = (1664525 * s + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function bootstrapCI(xs, B = 1000) {
  if (xs.length < 2) return null;
  const rng = lcg(12345);
  const means = [];
  for (let b = 0; b < B; b++) {
    let acc = 0;
    for (let i = 0; i < xs.length; i++) acc += xs[Math.floor(rng() * xs.length)];
    means.push(acc / xs.length);
  }
  means.sort((a, b) => a - b);
  const lo = means[Math.floor(0.025 * B)];
  const hi = means[Math.floor(0.975 * B)];
  return [lo, hi];
}

function renderQuality(metrics) {
  const fams = families(metrics);
  const rows = fams
    .map((f) => {
      const r1 = mean(perQuery(metrics, f, "recall", 1));
      const r5 = mean(perQuery(metrics, f, "recall", 5));
      const r10series = perQuery(metrics, f, "recall", 10);
      const r10 = mean(r10series);
      const ci = bootstrapCI(r10series);
      const nd = mean(perQuery(metrics, f, "ndcg", 10));
      const mr = mean(perQuery(metrics, f, "mrr", 10));
      const ciText = ci ? `<div class="ci">[${fmtPct(ci[0])}, ${fmtPct(ci[1])}]</div>` : "";
      return (
        `<tr><td>${f}</td>` +
        `<td>${fmtPct(r1)}</td><td>${fmtPct(r5)}</td>` +
        `<td>${fmtPct(r10)}${ciText}</td>` +
        `<td>${fmtPct(nd)}</td><td>${fmtPct(mr)}</td></tr>`
      );
    })
    .join("");
  return (
    `<table><thead><tr><th>index</th><th>recall@1</th><th>recall@5</th>` +
    `<th>recall@10</th><th>nDCG@10</th><th>MRR@10</th></tr></thead><tbody>${rows}</tbody></table>`
  );
}

function renderCost(metrics) {
  const fams = families(metrics);
  const rows = fams
    .map((f) => {
      const rs = metrics.filter((r) => r.index_family === f);
      const build = rs.length ? rs[0].build_time_s * 1000 : NaN;
      const mem = rs.length ? rs[0].memory_bytes / (1024 * 1024) : NaN;
      const lat = mean(rs.map((r) => r.latency_ms));
      return (
        `<tr><td>${f}</td>` +
        `<td>${build.toFixed(1)} ms</td>` +
        `<td>${mem.toFixed(2)} MB</td>` +
        `<td>${lat.toFixed(3)} ms</td></tr>`
      );
    })
    .join("");
  return (
    `<table><thead><tr><th>index</th><th>build</th><th>index memory</th>` +
    `<th>mean latency</th></tr></thead><tbody>${rows}</tbody></table>`
  );
}

// ---- data source control ---------------------------------------------------------------------

async function load() {
  el("runs-status").textContent = "Loading…";
  el("runs-list").innerHTML = "";
  el("detail").className = "detail-empty";
  el("detail").textContent = "Select a run to see its results.";
  try {
    const runs = await getJSON(state.resolver.runs());
    state.runs = runs;
    renderRuns(runs);
    if (runs.length) selectRun(runs[0].run_id);
  } catch (err) {
    el("runs-status").textContent = "";
    const hint = el("source-hint");
    hint.className = "source-hint error";
    hint.innerHTML =
      `Could not reach the data source (${err.message}). ` +
      `If you chose <strong>Live API</strong>, make sure <code>bootstrapper-api</code> is running ` +
      `and reachable (CORS-enabled), or switch back to <strong>Bundled sample</strong>.`;
  }
}

function wireControls() {
  const apiBase = el("api-base");
  for (const radio of document.querySelectorAll('input[name="src"]')) {
    radio.addEventListener("change", () => {
      const live = radio.value === "live" && radio.checked;
      if (radio.value === "live") apiBase.disabled = !radio.checked;
      if (radio.value === "bundled" && radio.checked) {
        apiBase.disabled = true;
        const hint = el("source-hint");
        hint.className = "source-hint";
        hint.innerHTML =
          `Showing the sample run committed to the repository. To point at your own data, run ` +
          `<code>bootstrapper-api</code> locally (or deploy it) and switch to <strong>Live API</strong>.`;
      }
      if (live) {
        const hint = el("source-hint");
        hint.className = "source-hint";
        hint.innerHTML =
          `Enter the base URL of a running <code>bootstrapper-api</code> service, then press Load.`;
      }
    });
  }

  el("reload").addEventListener("click", () => {
    const live = document.querySelector('input[name="src"]:checked').value === "live";
    if (live) {
      const base = apiBase.value.trim();
      if (!base) {
        const hint = el("source-hint");
        hint.className = "source-hint error";
        hint.textContent = "Enter an API base URL first.";
        return;
      }
      state.resolver = liveResolver(base);
    } else {
      state.resolver = BUNDLED;
    }
    load();
  });
}

wireControls();
load();
