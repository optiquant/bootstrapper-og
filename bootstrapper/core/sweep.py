"""Sweep orchestrator.

Executes one run: ingest a corpus, chunk + snapshot it, embed once per model (cached), then
for every (embedding x index family/params x search params x retriever) build, query, score
and capture latency. Emits per-query rows and an immutable run artifact.

All heavy work happens here, offline, driven by the CLI. The Streamlit app never calls this.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from bootstrapper.config.grids import GridConfig
from bootstrapper.core.chunking import Chunk
from bootstrapper.core.embeddings import EmbeddingCache, EmbeddingProvider
from bootstrapper.core.indices import Index, make_index
from bootstrapper.core.labeling import CoverageReport, resolve_labels
from bootstrapper.core.metrics import METRIC_FNS
from bootstrapper.core.retrievers import DenseRetriever, Retriever
from bootstrapper.core.run import RunManifest, RunStore, new_run_id, now_iso
from bootstrapper.core.snapshot import SnapshotStore
from bootstrapper.datasets.base import DatasetAdapter

METRIC_NAMES = ("recall", "ndcg", "mrr")


def _config_id(
    embedding_id: str,
    family: str,
    build_params: dict[str, int],
    search_params: dict[str, int],
    retriever_id: str,
) -> str:
    payload = json.dumps(
        {
            "e": embedding_id,
            "f": family,
            "b": build_params,
            "s": search_params,
            "r": retriever_id,
        },
        sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _build_retriever(
    retriever_id: str, index: Index, id_map: list[str], search_params: dict[str, int]
) -> Retriever:
    if retriever_id == "dense":
        return DenseRetriever(index, id_map, search_params)
    raise ValueError(
        f"retriever {retriever_id!r} is not implemented in v0/Gate 1 (bm25/hybrid_rrf land in "
        f"Gate 3)"
    )


@dataclass
class SweepResult:
    manifest: RunManifest
    coverage: CoverageReport
    run_dir: Path


def run_sweep(
    adapter: DatasetAdapter,
    grid: GridConfig,
    providers: dict[str, EmbeddingProvider],
    store: RunStore,
    cache_root: Path | str,
    git_sha: str,
    *,
    allow_unresolved: bool = False,
    notes: str = "",
) -> SweepResult:
    chunker = adapter.chunker
    if chunker.id != grid.chunker_id:
        raise ValueError(
            f"grid chunker {grid.chunker_id!r} != adapter chunker {chunker.id!r}; labels are "
            f"resolved against the active chunker, so these must match"
        )

    # 1. Ingest -> chunk -> snapshot. Keep all chunk instances (for page-scoped labeling) and a
    #    de-duplicated, order-stable id list (one vector per unique content hash).
    snapshots = SnapshotStore(store.snapshots_dir)
    all_chunks: list[Chunk] = []
    n_documents = 0
    for doc in adapter.documents():
        n_documents += 1
        for chunk in chunker.chunk(doc):
            snapshots.put(chunk.text, chunk.locus)
            all_chunks.append(chunk)

    seen: set[str] = set()
    unique_ids: list[str] = []
    texts: list[str] = []
    for chunk in all_chunks:
        if chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            unique_ids.append(chunk.chunk_id)
            texts.append(chunk.text)

    if not unique_ids:
        raise ValueError("corpus produced no chunks")

    # 2. Resolve span-level labels against the active chunker.
    queries = adapter.queries()
    gold_map, coverage = resolve_labels(queries, all_chunks, chunker.id)
    if not allow_unresolved:
        coverage.assert_clean()

    # 3. Sweep.
    created_at = now_iso()
    run_id = new_run_id(created_at)
    rows: list[dict[str, object]] = []

    for embedding_id in grid.embedding_ids:
        if embedding_id not in providers:
            raise KeyError(f"no provider registered for embedding id {embedding_id!r}")
        provider = providers[embedding_id]
        cache = EmbeddingCache(cache_root, provider)
        vectors = cache.encode(list(zip(unique_ids, texts, strict=True)))

        query_texts = [q.text for q in queries]
        embed_query = getattr(provider, "embed_query", provider.embed)
        query_vecs = (
            embed_query(query_texts)
            if query_texts
            else np.zeros((0, provider.dim), dtype=np.float32)
        )

        for spec in grid.indices:
            index = make_index(spec.family)
            index.build(vectors, spec.build_params)
            build_time_s = index.build_time_s
            memory_bytes = index.memory_bytes()

            for search_params in spec.search_params:
                for retriever_id in grid.retrievers:
                    retriever = _build_retriever(
                        retriever_id, index, unique_ids, search_params
                    )
                    config_id = _config_id(
                        embedding_id, spec.family, spec.build_params, search_params, retriever_id
                    )
                    index_params_json = json.dumps(spec.build_params, sort_keys=True)
                    search_params_json = json.dumps(search_params, sort_keys=True)

                    for qi, query in enumerate(queries):
                        gold = gold_map[query.query_id]
                        if not gold:
                            # allow_unresolved path: skip; scoring this measures the resolver.
                            continue
                        qv = query_vecs[qi]
                        t0 = time.perf_counter()
                        retrieved = retriever.retrieve(qv, query.text, grid.max_k)
                        latency_ms = (time.perf_counter() - t0) * 1000.0
                        for k in grid.k_values:
                            for metric_name in METRIC_NAMES:
                                value = METRIC_FNS[metric_name](retrieved, gold, k)
                                rows.append(
                                    {
                                        "run_id": run_id,
                                        "config_id": config_id,
                                        "embedding_id": embedding_id,
                                        "index_family": spec.family,
                                        "index_params": index_params_json,
                                        "search_params": search_params_json,
                                        "retriever": retriever_id,
                                        "query_id": query.query_id,
                                        "gt_source": query.gt_source,
                                        "k": k,
                                        "metric_name": metric_name,
                                        "metric_value": value,
                                        "latency_ms": latency_ms,
                                        "build_time_s": build_time_s,
                                        "memory_bytes": memory_bytes,
                                    }
                                )

    metrics_df = pd.DataFrame(rows)

    manifest = RunManifest(
        run_id=run_id,
        dataset_id=adapter.id,
        labeled=adapter.labeled,
        chunker_id=chunker.id,
        embedding_ids=list(grid.embedding_ids),
        grid=grid,
        k_values=list(grid.k_values),
        bootstrap_b=grid.bootstrap_b,
        git_sha=git_sha,
        created_at=created_at,
        n_documents=n_documents,
        n_chunks=len(unique_ids),
        n_queries=len(queries),
        coverage=coverage.coverage,
        mean_gold_per_query=coverage.mean_gold_per_query,
        latency_illustrative=adapter.labeled,
        notes=notes,
    )
    run_dir = store.write_run(manifest, metrics_df)
    return SweepResult(manifest=manifest, coverage=coverage, run_dir=run_dir)
