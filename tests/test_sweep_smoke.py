"""End-to-end sweep on a tiny in-memory corpus: the whole Gate-1 slice, offline."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from bootstrapper.config.grids import GridConfig, IndexSpec
from bootstrapper.core.chunking import Chunker, TokenWindowChunker
from bootstrapper.core.embeddings import HashingEmbeddingProvider
from bootstrapper.core.run import RunStore
from bootstrapper.core.sweep import run_sweep
from bootstrapper.datasets.base import Document, Evidence, Query

# Each page is short (< window) so it becomes exactly one chunk equal to the page text.
_PAGES = {
    "DOC_A": ["the quick brown fox jumps over", "lazy dogs sleep all day long"],
    "DOC_B": ["financial revenue grew strongly this year", "net income declined sharply last quarter"],
}


class _FakeAdapter:
    id = "fake"
    labeled = True

    def __init__(self) -> None:
        self._chunker = TokenWindowChunker(window=64, overlap=8)

    @property
    def chunker(self) -> Chunker:
        return self._chunker

    def documents(self) -> Iterator[Document]:
        for doc_id, pages in _PAGES.items():
            yield Document(doc_id=doc_id, pages=pages, meta={})

    def queries(self) -> list[Query]:
        # Query text == gold page text => the gold chunk is the exact nearest neighbour.
        out: list[Query] = []
        for doc_id, pages in _PAGES.items():
            for page_idx, page_text in enumerate(pages):
                out.append(
                    Query(
                        query_id=f"{doc_id}-{page_idx}",
                        text=page_text,
                        gold=[Evidence(doc_id=doc_id, page=page_idx, evidence_text=page_text)],
                        gt_source="real",
                    )
                )
        return out


def _grid() -> GridConfig:
    return GridConfig(
        name="smoke",
        embedding_ids=["hashing-256"],
        chunker_id="tokenwindow-64-8",
        indices=[
            IndexSpec(family="flat"),
            IndexSpec(
                family="hnsw",
                build_params={"M": 16, "efConstruction": 100},
                search_params=[{"efSearch": 64}],
            ),
        ],
        retrievers=["dense"],
        k_values=[1, 2],
        bootstrap_b=50,
    )


def test_sweep_produces_valid_run_artifact(tmp_path: Path) -> None:
    adapter = _FakeAdapter()
    store = RunStore(tmp_path)
    result = run_sweep(
        adapter=adapter,
        grid=_grid(),
        providers={"hashing-256": HashingEmbeddingProvider(256)},
        store=store,
        cache_root=tmp_path / "cache",
        git_sha="test-sha",
    )

    m = result.manifest
    assert result.coverage.clean
    assert m.coverage == 1.0
    assert m.n_documents == 2
    assert m.n_chunks == 4
    assert m.n_queries == 4
    assert m.embedding_ids == ["hashing-256"]
    assert m.git_sha == "test-sha"
    assert m.latency_illustrative is True

    # Artifacts on disk.
    assert (result.run_dir / "manifest.json").exists()
    assert (result.run_dir / "metrics.parquet").exists()
    assert store.snapshots_dir.exists()

    df = store.load_metrics(m.run_id)
    expected_cols = {
        "run_id", "config_id", "embedding_id", "index_family", "index_params",
        "search_params", "retriever", "query_id", "gt_source", "k", "metric_name",
        "metric_value", "latency_ms", "build_time_s", "memory_bytes",
    }
    assert expected_cols <= set(df.columns)
    assert set(df["index_family"].unique()) == {"flat", "hnsw"}

    # Flat is exact and each query's gold is its own text => recall@1 == 1.0 everywhere.
    flat_recall1 = df[
        (df["index_family"] == "flat")
        & (df["metric_name"] == "recall")
        & (df["k"] == 1)
    ]["metric_value"]
    assert (flat_recall1 == 1.0).all()

    # The registry lists the run and the manifest round-trips.
    listed = {r.run_id for r in store.list_runs()}
    assert m.run_id in listed
