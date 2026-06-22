# `web/` — public UI/UX (placeholder)

This directory is reserved for the **public, non-technical frontend** of bootstrapper-og: a UI
that a non-technical user can interact with to explore retrieval-evaluation runs without ever
touching Python or a terminal.

It is **not built yet** — this is the scaffolded boundary, not the implementation.

## How it fits the architecture

```
bootstrapper.core / datasets / config   ← the engine (pure Python SDK)
            │  imports
            ▼
bootstrapper.service  (FastAPI, the `api` extra)   ← HTTP boundary
            │  HTTP (JSON)
            ▼
web/  (this directory)                              ← public, non-technical UI
```

The public UI is a **client of the HTTP service layer**, not of the Python package. It speaks to
`bootstrapper.service.app` over HTTP/JSON and never imports the engine. That decoupling is
deliberate: the UI can be any stack (static + fetch, HTMX, React, …), deploy independently, and
be rewritten without touching the engine.

## Talking to the service

Start the API (from a checkout with artifacts in the working directory):

```bash
pip install -e ".[api]"
bootstrapper-api          # serves on http://127.0.0.1:8000
```

Then the UI consumes:

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | liveness + resolved artifact root |
| `GET /runs` | list run manifests (newest first) |
| `GET /runs/{run_id}` | one run manifest |
| `GET /runs/{run_id}/metrics` | that run's metrics as JSON records |

Interactive API docs are served at `http://127.0.0.1:8000/docs` once the service is running.

## Status

- [x] Service-layer boundary scaffolded (`bootstrapper/service/`)
- [ ] Choose the frontend stack
- [ ] Wire a minimal read-only run browser to `/runs`
- [ ] Deploy alongside the API
