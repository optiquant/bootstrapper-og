"""The dataset-agnostic retrieval-evaluation engine.

This subpackage is the heart of the SDK: chunking, content-addressed snapshots, embeddings,
ANN indices, retrievers, span-level labeling, metrics, and the sweep that ties them into an
immutable run artifact. It imports nothing dataset-specific.
"""

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
from bootstrapper.core.search import SearchHit, SearchIndex
from bootstrapper.core.snapshot import (
    SnapshotRecord,
    SnapshotStore,
    SourceLocus,
    content_hash,
)
from bootstrapper.core.sweep import SweepResult, run_sweep

__all__ = [
    "Chunk",
    "Chunker",
    "CoverageReport",
    "DenseRetriever",
    "EmbeddingCache",
    "EmbeddingProvider",
    "EmptyGoldError",
    "FlatIndex",
    "HNSWIndex",
    "HashingEmbeddingProvider",
    "Index",
    "Retriever",
    "RunManifest",
    "RunStore",
    "SearchHit",
    "SearchIndex",
    "SentenceTransformerProvider",
    "SnapshotRecord",
    "SnapshotStore",
    "SourceLocus",
    "SweepResult",
    "TokenWindowChunker",
    "aggregate_metric",
    "bootstrap_ci",
    "content_hash",
    "make_index",
    "mrr",
    "ndcg_at_k",
    "new_run_id",
    "now_iso",
    "recall_at_k",
    "resolve_labels",
    "run_sweep",
]
