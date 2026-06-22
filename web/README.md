# `web/` — public run explorer (GitHub Pages)

The **public, non-technical frontend** of bootstrapper-og: a static, browser-based run explorer
that anyone can open to browse retrieval-evaluation runs — recall, nDCG and MRR with bootstrap
confidence intervals, plus latency, build time and index memory — without touching Python or a
terminal.

**Live:** https://optiquant.github.io/bootstrapper-og/

It is a pure static site, deployed to GitHub Pages by
[`.github/workflows/pages.yml`](../.github/workflows/pages.yml) on every push to `main` that
touches `web/`. Two pages:

- **`index.html`** — the **run explorer**: browse frozen evaluation runs (read-only API or the
  bundled sample).
- **`search.html`** — **search your docs**: drives the local runner (`bootstrapper-search`) to
  index a folder on your machine and search it interactively. See
  [Search your own documents](../README.md#search-your-own-documents-local-runner).

## How it fits the architecture

```
bootstrapper.core / datasets / config   ← the engine (pure Python SDK)
            │  imports
            ▼
bootstrapper.service  (FastAPI, the `api` extra)   ← HTTP boundary
            │  HTTP (JSON)
            ▼
web/  (this directory, GitHub Pages)               ← public, non-technical UI
```

The UI is a **client of the HTTP service**, never an importer of the engine. It speaks the same
JSON shape as `bootstrapper.service.app` (`/runs`, `/runs/{id}`, `/runs/{id}/metrics`) and can
read from two interchangeable sources:

| source | what it reads | when |
|--------|---------------|------|
| **Bundled sample** (default) | static JSON under [`data/`](data/) | so the Pages site works standalone, with the run committed to the repo |
| **Live API** | a running `bootstrapper-api` (enter its base URL) | your own data, locally or once deployed to a live URL |

The bundled fixtures mirror the API exactly, so switching sources changes only the base path.

## Run it locally

It is just static files — open `web/index.html` directly, or serve the folder:

```bash
python -m http.server -d web 8080      # http://localhost:8080
```

To drive it from real data, start the API in another terminal and point the **Live API** field
at it:

```bash
pip install -e ".[api]"
bootstrapper-api                       # http://127.0.0.1:8000 (CORS-enabled)
```

## Regenerating the bundled fixtures

The fixtures under `data/` are derived from the runs in the working directory. Regenerate them
whenever you commit a new sample run:

```python
import json
from pathlib import Path
from bootstrapper.core.run import RunStore

store, out = RunStore("."), Path("web/data")
out.mkdir(parents=True, exist_ok=True)
manifests = store.list_runs()
(out / "runs.json").write_text(json.dumps([m.model_dump() for m in manifests], indent=2))
for m in manifests:
    (out / f"{m.run_id}.json").write_text(m.model_dump_json(indent=2))
    (out / f"{m.run_id}.metrics.json").write_text(
        json.dumps(store.load_metrics(m.run_id).to_dict(orient="records"))
    )
```

## Status

- [x] Service-layer boundary scaffolded (`bootstrapper/service/`)
- [x] Frontend stack chosen — dependency-free static site (HTML/CSS/JS)
- [x] Read-only run browser wired to the API shape, with bundled-sample fallback
- [x] Deployed to GitHub Pages
- [x] Search-your-docs page wired to the local runner (`search.html`)
- [ ] Point at the live API once it is deployed to a public URL
- [ ] Phase 2: measured evaluation over your own docs (synthetic queries, Gate 3)
