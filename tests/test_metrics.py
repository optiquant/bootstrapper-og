"""Metrics checked against hand-computed cases; bootstrap against a fixed-seed fixture."""

from __future__ import annotations

import math

import numpy as np
import pytest

from bootstrapper.core.metrics import bootstrap_ci, mrr, ndcg_at_k, recall_at_k


def test_recall_at_k_hand_computed() -> None:
    retrieved = ["a", "b", "c", "d"]
    gold = {"b", "d"}
    assert recall_at_k(retrieved, gold, 1) == 0.0  # {a}
    assert recall_at_k(retrieved, gold, 2) == 0.5  # {a,b} -> b
    assert recall_at_k(retrieved, gold, 3) == 0.5  # {a,b,c} -> b
    assert recall_at_k(retrieved, gold, 4) == 1.0  # all gold found


def test_recall_perfect_and_miss() -> None:
    assert recall_at_k(["g1", "g2"], {"g1", "g2"}, 2) == 1.0
    assert recall_at_k(["x", "y"], {"z"}, 2) == 0.0


def test_ndcg_at_k_hand_computed() -> None:
    # relevant at ranks 2 and 4 (1-indexed): positions i=1 and i=3 (0-indexed).
    retrieved = ["a", "b", "c", "d"]
    gold = {"b", "d"}
    dcg = 1.0 / math.log2(1 + 2) + 1.0 / math.log2(3 + 2)
    idcg = 1.0 / math.log2(0 + 2) + 1.0 / math.log2(1 + 2)
    assert ndcg_at_k(retrieved, gold, 4) == pytest.approx(dcg / idcg)
    # perfect ordering -> 1.0
    assert ndcg_at_k(["b", "d", "a"], {"b", "d"}, 3) == pytest.approx(1.0)
    # nothing relevant in top-k -> 0.0
    assert ndcg_at_k(["x", "y"], {"z"}, 2) == 0.0


def test_mrr_hand_computed() -> None:
    assert mrr(["a", "b", "c", "d"], {"b", "d"}) == pytest.approx(0.5)  # first hit at rank 2
    assert mrr(["g", "x"], {"g"}) == pytest.approx(1.0)  # first hit at rank 1
    assert mrr(["x", "y"], {"z"}) == 0.0  # no hit


def test_metrics_reject_empty_gold() -> None:
    for fn in (recall_at_k, ndcg_at_k):
        with pytest.raises(ValueError):
            fn(["a"], set(), 1)
    with pytest.raises(ValueError):
        mrr(["a"], set())


def test_bootstrap_ci_constant_is_degenerate() -> None:
    mean, lo, hi = bootstrap_ci(np.full(20, 0.7), b=500, seed=0)
    assert mean == pytest.approx(0.7)
    assert lo == pytest.approx(0.7)
    assert hi == pytest.approx(0.7)


def test_bootstrap_ci_single_observation() -> None:
    mean, lo, hi = bootstrap_ci(np.array([0.4]), b=100, seed=0)
    assert mean == lo == hi == pytest.approx(0.4)


def test_bootstrap_ci_mean_and_bounds_and_determinism() -> None:
    per_query = np.array([1.0, 0.0] * 5)  # mean 0.5
    a = bootstrap_ci(per_query, b=1000, seed=0)
    b = bootstrap_ci(per_query, b=1000, seed=0)
    assert a == b  # fixed seed -> fully reproducible
    mean, lo, hi = a
    assert mean == pytest.approx(0.5)
    assert 0.0 <= lo < mean < hi <= 1.0


def test_bootstrap_ci_requires_data() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci(np.array([]), b=10)
