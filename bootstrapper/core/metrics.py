"""Retrieval metrics and the bootstrap.

Relevance is binary (FinanceBench has no graded labels), so recall@k, nDCG@k and MRR
correlate; do not over-interpret their divergence. At small query counts confidence intervals
are wide -- surface the width, trust frontier shape over absolute deltas.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

import numpy as np
from numpy.typing import NDArray


def recall_at_k(retrieved: list[str], gold: set[str], k: int) -> float:
    """Fraction of gold chunks present in the top-``k`` retrieved ids."""

    if not gold:
        raise ValueError("recall_at_k requires a non-empty gold set")
    top = set(retrieved[:k])
    return len(top & gold) / len(gold)


def ndcg_at_k(retrieved: list[str], gold: set[str], k: int) -> float:
    """Binary-gain nDCG@k."""

    if not gold:
        raise ValueError("ndcg_at_k requires a non-empty gold set")
    dcg = 0.0
    for i, cid in enumerate(retrieved[:k]):
        if cid in gold:
            dcg += 1.0 / np.log2(i + 2)
    ideal_hits = min(len(gold), k)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def mrr(retrieved: list[str], gold: set[str]) -> float:
    """Reciprocal rank of the first relevant chunk (0.0 if none retrieved)."""

    if not gold:
        raise ValueError("mrr requires a non-empty gold set")
    for i, cid in enumerate(retrieved):
        if cid in gold:
            return 1.0 / (i + 1)
    return 0.0


def bootstrap_ci(
    per_query: NDArray[np.float64], b: int = 1000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float, float]:
    """Percentile bootstrap CI for the mean of a per-query metric.

    Returns ``(mean, lo, hi)``. The bootstrap is the sampling distribution of the metric over
    queries; with a fixed ``seed`` it is fully reproducible.
    """

    values = np.asarray(per_query, dtype=np.float64)
    if values.size == 0:
        raise ValueError("bootstrap_ci requires at least one observation")
    mean = float(values.mean())
    rng = np.random.default_rng(seed)
    n = values.size
    idx = rng.integers(0, n, size=(b, n))
    resampled_means = values[idx].mean(axis=1)
    lo = float(np.percentile(resampled_means, 100 * (alpha / 2)))
    hi = float(np.percentile(resampled_means, 100 * (1 - alpha / 2)))
    return mean, lo, hi


def measure_search_latency(
    search_fn: Callable[[], object],
    repeats: int = 50,
    warmup: int = 5,
) -> tuple[float, float]:
    """Warm the index, time ``repeats`` single-query searches, return ``(p50_ms, p95_ms)``.

    Latency is only meaningful on the scale corpus; on the labeled mini corpus it is
    illustrative (all index families return in microseconds at small vector counts).
    """

    for _ in range(warmup):
        search_fn()
    timings_ms: list[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        search_fn()
        timings_ms.append((time.perf_counter() - t0) * 1000.0)
    arr = np.asarray(timings_ms, dtype=np.float64)
    return float(np.percentile(arr, 50)), float(np.percentile(arr, 95))


def time_call_ms(fn: Callable[[], object]) -> tuple[object, float]:
    """Run ``fn`` once and return ``(result, elapsed_ms)``."""

    t0 = time.perf_counter()
    result = fn()
    return result, (time.perf_counter() - t0) * 1000.0


METRIC_FNS: dict[str, Callable[[list[str], set[str], int], float]] = {
    "recall": recall_at_k,
    "ndcg": ndcg_at_k,
    "mrr": lambda retrieved, gold, k: mrr(retrieved[:k], gold),
}


def aggregate_metric(per_query: Sequence[float]) -> float:
    """Mean of a per-query metric (convenience for views/tests)."""

    arr = np.asarray(per_query, dtype=np.float64)
    return float(arr.mean()) if arr.size else 0.0
