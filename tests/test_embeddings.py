"""Hashing provider determinism/normalization and the (model, chunk)-keyed cache."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from bootstrapper.core.embeddings import EmbeddingCache, HashingEmbeddingProvider, Vectors


def test_hashing_provider_shape_and_normalization() -> None:
    provider = HashingEmbeddingProvider(dim=64)
    vecs = provider.embed(["revenue grew", "net income declined", ""])
    assert vecs.shape == (3, 64)
    assert vecs.dtype == np.float32
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)  # every row L2-normalized, incl. empty text


def test_hashing_provider_is_deterministic_and_lexical() -> None:
    provider = HashingEmbeddingProvider(dim=256)
    a = provider.embed(["apple banana cherry"])
    b = provider.embed(["apple banana cherry"])
    assert np.array_equal(a, b)  # stable across calls/processes

    base = provider.embed(["apple banana cherry"])[0]
    near = provider.embed(["apple banana cherry date"])[0]
    far = provider.embed(["zebra xylophone quokka"])[0]
    assert float(base @ near) > float(base @ far)  # shared words -> higher cosine


class _CountingProvider:
    """Wraps a provider and counts how many texts it actually embeds."""

    def __init__(self, inner: HashingEmbeddingProvider) -> None:
        self._inner = inner
        self.id = inner.id
        self.dim = inner.dim
        self.embedded = 0

    def embed(self, texts: list[str]) -> Vectors:
        self.embedded += len(texts)
        return self._inner.embed(texts)


def test_cache_avoids_recompute(tmp_path: Path) -> None:
    provider = _CountingProvider(HashingEmbeddingProvider(dim=32))
    cache = EmbeddingCache(tmp_path, provider)
    items = [("id1", "alpha beta"), ("id2", "gamma delta"), ("id1", "alpha beta")]

    first = cache.encode(items)
    assert first.shape == (3, 32)
    assert provider.embedded == 2  # two unique ids embedded, the duplicate reused

    # Fresh cache instance reads from disk; no re-embedding.
    provider2 = _CountingProvider(HashingEmbeddingProvider(dim=32))
    cache2 = EmbeddingCache(tmp_path, provider2)
    second = cache2.encode([("id1", "alpha beta"), ("id2", "gamma delta")])
    assert provider2.embedded == 0
    assert np.allclose(second, first[:2])
