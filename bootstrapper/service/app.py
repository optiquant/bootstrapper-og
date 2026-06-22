"""Read-only HTTP API over frozen run artifacts.

This is the boundary the non-technical public UI talks to: it never imports faiss or builds an
index, it only serves what ``bootstrapper run`` already froze to disk. The artifact root is the
current working directory by default, overridable with the ``BOOTSTRAPPER_ROOT`` env var (the
same convention the Streamlit app uses).

Endpoints
---------
* ``GET /health``                  -- liveness + the resolved artifact root.
* ``GET /runs``                    -- list run manifests (newest first).
* ``GET /runs/{run_id}``           -- one run manifest.
* ``GET /runs/{run_id}/metrics``   -- that run's long-format metrics as JSON records.

Run it with::

    bootstrapper-api
    # or, with autoreload during development:
    uvicorn bootstrapper.service.app:app --reload
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from bootstrapper.core.run import RunManifest, RunStore

#: Where the public, non-technical UI is published (GitHub Pages for now).
UI_URL = "https://optiquant.github.io/bootstrapper-og/"

app = FastAPI(
    title="bootstrapper-og API",
    summary="Read-only HTTP access to frozen ANN retrieval-evaluation runs.",
    description=(
        "Read-only HTTP boundary over frozen runs produced by `bootstrapper run`.\n\n"
        f"A browser-based run explorer that consumes this API lives at <{UI_URL}>."
    ),
    version="0.1.0",
)

# The served data is public and read-only, so CORS is permissive by default to let the static UI
# (GitHub Pages or a future live URL) call the API from another origin. Restrict via the
# BOOTSTRAPPER_API_CORS env var (comma-separated origins) when you deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip() for o in os.environ.get("BOOTSTRAPPER_API_CORS", "*").split(",") if o.strip()
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _store() -> RunStore:
    """Resolve the artifact root the same way the Streamlit app does."""

    return RunStore(Path(os.environ.get("BOOTSTRAPPER_ROOT", ".")))


@app.get("/")
def root() -> dict[str, Any]:
    """Service banner: where the docs and the public UI live."""

    return {
        "service": "bootstrapper-og API",
        "ui": UI_URL,
        "docs": "/docs",
        "endpoints": ["/health", "/runs", "/runs/{run_id}", "/runs/{run_id}/metrics"],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    store = _store()
    return {"status": "ok", "root": str(store.root.resolve())}


@app.get("/runs", response_model=list[RunManifest])
def list_runs() -> list[RunManifest]:
    return _store().list_runs()


@app.get("/runs/{run_id}", response_model=RunManifest)
def get_run(run_id: str) -> RunManifest:
    store = _store()
    if not (store.run_dir(run_id) / "manifest.json").exists():
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    return store.load_manifest(run_id)


@app.get("/runs/{run_id}/metrics")
def get_run_metrics(run_id: str) -> list[dict[str, Any]]:
    store = _store()
    if not (store.run_dir(run_id) / "metrics.parquet").exists():
        raise HTTPException(status_code=404, detail=f"metrics for run {run_id!r} not found")
    df = store.load_metrics(run_id)
    records: list[dict[str, Any]] = df.to_dict(orient="records")
    return records


def run() -> None:
    """Console-script entry point (``bootstrapper-api``)."""

    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("BOOTSTRAPPER_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("BOOTSTRAPPER_API_PORT", "8000")),
    )


if __name__ == "__main__":
    run()
