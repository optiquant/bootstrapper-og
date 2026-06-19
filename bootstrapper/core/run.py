"""Run manifests and persistence.

A run is an immutable bundle on disk:

* ``runs/<run_id>/manifest.json`` -- everything needed to reproduce it.
* ``runs/<run_id>/metrics.parquet`` -- long format, one row per
  (config, embedding, index, search params, retriever, query, gt_source, k, metric).
* ``snapshots/<chunk_id>.json`` -- content-addressed, shared across runs.
* ``runs/registry.sqlite`` -- a convenience index for the Run Browser.

This module is import-light on purpose (no faiss / no embeddings): the read-only Streamlit app
imports it freely. The registry is treated as a rebuildable cache; the source of truth for the
Run Browser is the manifests on disk.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from bootstrapper.config.grids import GridConfig

METRICS_FILENAME = "metrics.parquet"
MANIFEST_FILENAME = "manifest.json"
REGISTRY_FILENAME = "registry.sqlite"


class RunManifest(BaseModel):
    run_id: str
    dataset_id: str
    labeled: bool
    chunker_id: str
    embedding_ids: list[str]
    grid: GridConfig
    k_values: list[int]
    bootstrap_b: int
    git_sha: str
    created_at: str
    n_documents: int
    n_chunks: int
    n_queries: int
    coverage: float
    mean_gold_per_query: float
    # Latency on a labeled corpus is illustrative only; the scale corpus measures it for real.
    latency_illustrative: bool
    notes: str = ""


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_run_id(created_at: str | None = None) -> str:
    stamp = (created_at or now_iso())
    digits = "".join(ch for ch in stamp if ch.isdigit())[:14]
    return f"run-{digits}"


class RunStore:
    """Filesystem layout + sqlite registry for runs."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.runs_dir = self.root / "runs"
        self.snapshots_dir = self.root / "snapshots"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    @property
    def registry_path(self) -> Path:
        return self.runs_dir / REGISTRY_FILENAME

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    # ---- writing -------------------------------------------------------------------------
    def write_run(self, manifest: RunManifest, metrics: pd.DataFrame) -> Path:
        rdir = self.run_dir(manifest.run_id)
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / MANIFEST_FILENAME).write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        metrics.to_parquet(rdir / METRICS_FILENAME, index=False)
        self._register(manifest)
        return rdir

    def _register(self, manifest: RunManifest) -> None:
        con = sqlite3.connect(self.registry_path)
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    dataset_id TEXT,
                    labeled INTEGER,
                    chunker_id TEXT,
                    embedding_ids TEXT,
                    grid_name TEXT,
                    git_sha TEXT,
                    created_at TEXT,
                    n_documents INTEGER,
                    n_chunks INTEGER,
                    n_queries INTEGER,
                    coverage REAL
                )
                """
            )
            con.execute(
                "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    manifest.run_id,
                    manifest.dataset_id,
                    int(manifest.labeled),
                    manifest.chunker_id,
                    ",".join(manifest.embedding_ids),
                    manifest.grid.name,
                    manifest.git_sha,
                    manifest.created_at,
                    manifest.n_documents,
                    manifest.n_chunks,
                    manifest.n_queries,
                    manifest.coverage,
                ),
            )
            con.commit()
        finally:
            con.close()

    # ---- reading -------------------------------------------------------------------------
    def load_manifest(self, run_id: str) -> RunManifest:
        path = self.run_dir(run_id) / MANIFEST_FILENAME
        return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def load_metrics(self, run_id: str) -> pd.DataFrame:
        return pd.read_parquet(self.run_dir(run_id) / METRICS_FILENAME)

    def list_runs(self) -> list[RunManifest]:
        """List runs by scanning manifests on disk (the authoritative source)."""

        manifests: list[RunManifest] = []
        for mpath in sorted(self.runs_dir.glob(f"*/{MANIFEST_FILENAME}")):
            try:
                manifests.append(RunManifest.model_validate_json(mpath.read_text(encoding="utf-8")))
            except Exception:  # a malformed manifest must not hide the rest
                continue
        manifests.sort(key=lambda m: m.created_at, reverse=True)
        return manifests
