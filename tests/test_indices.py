"""FAISS backends: Flat is exact (recall 1.0); HNSW approximates it with high recall."""

from __future__ import annotations

import numpy as np

from bootstrapper.core.indices import FlatIndex, HNSWIndex


def _normalized(rng: np.random.Generator, n: int, d: int) -> np.ndarray:
    vecs = rng.standard_normal((n, d)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs


def _brute_force_topk(vectors: np.ndarray, query: np.ndarray, k: int) -> list[int]:
    sims = vectors @ query
    return list(np.argsort(-sims)[:k])


def test_flat_is_exact() -> None:
    rng = np.random.default_rng(0)
    vectors = _normalized(rng, 200, 32)
    index = FlatIndex()
    index.build(vectors, {})
    assert index.memory_bytes() > 0

    for _ in range(10):
        q = _normalized(rng, 1, 32)[0]
        ids, _ = index.search(q, 5, {})
        assert list(ids[0]) == _brute_force_topk(vectors, q, 5)


def test_hnsw_high_recall_against_flat() -> None:
    rng = np.random.default_rng(1)
    vectors = _normalized(rng, 500, 48)
    flat = FlatIndex()
    flat.build(vectors, {})
    hnsw = HNSWIndex()
    hnsw.build(vectors, {"M": 32, "efConstruction": 200})
    assert hnsw.build_time_s >= 0.0
    assert hnsw.memory_bytes() > 0

    hits = 0
    total = 0
    for _ in range(20):
        q = _normalized(rng, 1, 48)[0]
        exact, _ = flat.search(q, 10, {})
        approx, _ = hnsw.search(q, 10, {"efSearch": 200})
        hits += len(set(exact[0].tolist()) & set(approx[0].tolist()))
        total += 10
    assert hits / total >= 0.9  # recall@10 well above chance with generous efSearch
