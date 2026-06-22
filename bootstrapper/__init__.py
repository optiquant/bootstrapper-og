"""bootstrapper-og: an auditable retrieval-evaluation engine for ANN search over documents.

bootstrapper-og is a **library first**. The engine in :mod:`bootstrapper.core` is
dataset-agnostic; finance-specific loading lives behind a :class:`DatasetAdapter` in
:mod:`bootstrapper.datasets`. Two optional frontends consume that engine without it ever
depending on them:

* a read-only Streamlit dashboard (``bootstrapper.app``, the ``app`` extra), and
* an HTTP service layer (``bootstrapper.service``, the ``api`` extra) for any non-Python client.

This module is the **curated public API** — the stable surface technical teams import. Prefer
these top-level names over deep module paths; the deep modules remain available but are not part
of the import contract.

Example
-------
    from bootstrapper import FinanceBenchAdapter, get_grid, run_sweep, RunStore

    store = RunStore(".")
    result = run_sweep(
        adapter=FinanceBenchAdapter(subset="mini"),
        grid=get_grid("gate1-smoke"),
        providers={"hashing-256": HashingEmbeddingProvider(dim=256)},
        store=store,
        cache_root="cache/embeddings",
        git_sha="unknown",
    )
    print(result.manifest.run_id)
"""

from bootstrapper.config.grids import GridConfig, IndexSpec, get_grid
from bootstrapper.core.chunking import Chunk, Chunker, TokenWindowChunker
from bootstrapper.core.embeddings import (
    EmbeddingCache,
    EmbeddingProvider,
    HashingEmbeddingProvider,
    SentenceTransformerProvider,
)
from bootstrapper.core.indices import FlatIndex, HNSWIndex, Index, make_index
from bootstrapper.core.labeling import CoverageReport, EmptyGoldError, resolve_labels
from bootstrapper.core.metrics import (
    aggregate_metric,
    bootstrap_ci,
    mrr,
    ndcg_at_k,
    recall_at_k,
)
from bootstrapper.core.retrievers import DenseRetriever, Retriever
from bootstrapper.core.run import RunManifest, RunStore, new_run_id, now_iso
from bootstrapper.core.snapshot import (
    SnapshotRecord,
    SnapshotStore,
    SourceLocus,
    content_hash,
)
from bootstrapper.core.sweep import SweepResult, run_sweep
from bootstrapper.datasets.base import DatasetAdapter, Document, Evidence, Query
from bootstrapper.datasets.financebench import FinanceBenchAdapter

__version__ = "0.1.0"

__all__ = [
    "Chunk",
    "Chunker",
    "CoverageReport",
    "DatasetAdapter",
    "DenseRetriever",
    "Document",
    "EmbeddingCache",
    "EmbeddingProvider",
    "EmptyGoldError",
    "Evidence",
    "FinanceBenchAdapter",
    "FlatIndex",
    "GridConfig",
    "HNSWIndex",
    "HashingEmbeddingProvider",
    "Index",
    "IndexSpec",
    "Query",
    "Retriever",
    "RunManifest",
    "RunStore",
    "SentenceTransformerProvider",
    "SnapshotRecord",
    "SnapshotStore",
    "SourceLocus",
    "SweepResult",
    "TokenWindowChunker",
    "__version__",
    "aggregate_metric",
    "bootstrap_ci",
    "content_hash",
    "get_grid",
    "make_index",
    "mrr",
    "ndcg_at_k",
    "new_run_id",
    "now_iso",
    "recall_at_k",
    "resolve_labels",
    "run_sweep",
]
