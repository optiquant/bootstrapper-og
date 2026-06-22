"use strict";

// Drives the local runner (bootstrapper.service.local) from the browser. The runner is expected
// to run on the user's own machine, so http://127.0.0.1 is reachable and CORS-allowed even when
// this page is served over https from GitHub Pages.

const el = (id) => document.getElementById(id);
const state = { base: null, sessionId: null };

function base() {
  return el("runner-base").value.trim().replace(/\/+$/, "");
}

async function req(method, path, body) {
  const resp = await fetch(base() + path, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const j = await resp.json();
      if (j.detail) detail = j.detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return resp.json();
}

function setHint(id, msg, kind) {
  const node = el(id);
  node.className = "source-hint" + (kind ? " " + kind : "");
  node.innerHTML = msg;
}

// ---- 1. connect ------------------------------------------------------------------------------

async function ping() {
  try {
    const h = await req("GET", "/health");
    state.base = base();
    setHint("runner-hint", `Connected — ${h.sessions} active session(s).`, "");
    el("build-hint").textContent = "Enter a folder path and press Build.";
  } catch (err) {
    state.base = null;
    setHint(
      "runner-hint",
      `Can't reach the runner at <code>${base()}</code> (${err.message}). ` +
        `Start it with <code>bootstrapper-search</code> and check the URL.`,
      "error"
    );
  }
}

// ---- 2. build --------------------------------------------------------------------------------

async function build() {
  const path = el("path").value.trim();
  if (!path) {
    setHint("build-hint", "Enter a folder path first.", "error");
    return;
  }
  setHint("build-hint", "Building index… (large folders take a while)", "");
  try {
    const info = await req("POST", "/sessions", {
      path,
      embedding_id: el("embedding").value,
      index_family: el("index-family").value,
    });
    state.sessionId = info.session_id;
    setHint(
      "build-hint",
      `Indexed <strong>${info.n_documents}</strong> documents into ` +
        `<strong>${info.n_chunks}</strong> chunks (${info.embedding_id} · ${info.index_family}).`,
      ""
    );
    for (const id of ["query", "k", "search"]) el(id).disabled = false;
    el("results").innerHTML = "";
  } catch (err) {
    setHint("build-hint", `Build failed: ${err.message}`, "error");
  }
}

// ---- 3. search -------------------------------------------------------------------------------

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function renderHits(data) {
  if (!data.hits.length) {
    el("results").innerHTML = `<p class="source-hint">No matches for “${escapeHtml(data.query)}”.</p>`;
    return;
  }
  const rows = data.hits
    .map(
      (h) =>
        `<div class="hit">` +
        `<div class="hit-head">` +
        `<span class="hit-doc">${escapeHtml(h.doc_id)}</span>` +
        `<span class="ci">page ${h.page + 1} · score ${h.score.toFixed(3)}</span>` +
        `</div>` +
        `<p class="hit-text">${escapeHtml(h.text)}</p>` +
        `</div>`
    )
    .join("");
  el("results").innerHTML = `<div class="section-label">${data.hits.length} passage(s)</div>${rows}`;
}

async function search() {
  const query = el("query").value.trim();
  if (!query || !state.sessionId) return;
  el("results").innerHTML = `<p class="source-hint">Searching…</p>`;
  try {
    const data = await req("POST", `/sessions/${state.sessionId}/search`, {
      query,
      k: parseInt(el("k").value, 10) || 10,
    });
    renderHits(data);
  } catch (err) {
    el("results").innerHTML = `<p class="source-hint error">Search failed: ${err.message}</p>`;
  }
}

// ---- wiring ----------------------------------------------------------------------------------

el("ping").addEventListener("click", ping);
el("build").addEventListener("click", build);
el("search").addEventListener("click", search);
el("query").addEventListener("keydown", (e) => {
  if (e.key === "Enter") search();
});
ping();
