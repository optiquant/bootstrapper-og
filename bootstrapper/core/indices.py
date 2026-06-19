"""ANN index backends (FAISS).

All vectors are L2-normalized, so cosine, inner-product and (negated) squared-L2 rankings
coincide -- ``FlatIndex`` uses inner product to give an exact cosine ranking, while ``HNSW``
uses L2 (the metric its FAISS backend supports) and gets the same ordering approximately.

v0 / Gate 1 ships Flat and HNSW. IVF / IVFPQ land in Gate 2 behind the same ``Index`` protocol.
"""

from __future__ import annotations

import time
from typing import Protocol

import faiss
import numpy as np
from numpy.typing import NDArray

Vectors = NDArray[np.float32]
Ids = NDArray[np.int64]
Distances = NDArray[np.float32]


class Index(Protocol):
    family: str  # "flat" | "ivf" | "ivfpq" | "hnsw"
    build_time_s: float

    def build(self, vectors: Vectors, params: dict[str, int]) -> None: ...

    def search(
        self, q: Vectors, k: int, search_params: dict[str, int]
    ) -> tuple[Ids, Distances]: ...

    def memory_bytes(self) -> int: ...


def _as_2d(q: Vectors) -> Vectors:
    arr = np.ascontiguousarray(q, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr


class FlatIndex:
    """Exact search baseline. recall@k == 1.0 by construction; the latency/memory floor."""

    family = "flat"

    def __init__(self) -> None:
        self.build_time_s = 0.0
        self._index: faiss.Index | None = None

    def build(self, vectors: Vectors, params: dict[str, int]) -> None:
        dim = vectors.shape[1]
        index = faiss.IndexFlatIP(dim)
        t0 = time.perf_counter()
        index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        self.build_time_s = time.perf_counter() - t0
        self._index = index

    def search(self, q: Vectors, k: int, search_params: dict[str, int]) -> tuple[Ids, Distances]:
        assert self._index is not None, "index not built"
        distances, ids = self._index.search(_as_2d(q), k)
        return ids.astype(np.int64), distances.astype(np.float32)

    def memory_bytes(self) -> int:
        assert self._index is not None, "index not built"
        return int(faiss.serialize_index(self._index).nbytes)


class HNSWIndex:
    """Hierarchical Navigable Small World graph. Read-fast, memory-heavy, build-slow.

    Build params: ``M`` (graph degree, default 32), ``efConstruction`` (default 200).
    Search params: ``efSearch`` (default 64) -- the recall/latency knob explored in Gate 6.
    """

    family = "hnsw"

    def __init__(self) -> None:
        self.build_time_s = 0.0
        self._index: faiss.IndexHNSWFlat | None = None

    def build(self, vectors: Vectors, params: dict[str, int]) -> None:
        dim = vectors.shape[1]
        m = int(params.get("M", 32))
        ef_construction = int(params.get("efConstruction", 200))
        index = faiss.IndexHNSWFlat(dim, m, faiss.METRIC_L2)
        index.hnsw.efConstruction = ef_construction
        t0 = time.perf_counter()
        index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        self.build_time_s = time.perf_counter() - t0
        self._index = index

    def search(self, q: Vectors, k: int, search_params: dict[str, int]) -> tuple[Ids, Distances]:
        assert self._index is not None, "index not built"
        self._index.hnsw.efSearch = int(search_params.get("efSearch", 64))
        distances, ids = self._index.search(_as_2d(q), k)
        return ids.astype(np.int64), distances.astype(np.float32)

    def memory_bytes(self) -> int:
        assert self._index is not None, "index not built"
        return int(faiss.serialize_index(self._index).nbytes)


def make_index(family: str) -> Index:
    """Construct an empty index by family name."""

    if family == "flat":
        return FlatIndex()
    if family == "hnsw":
        return HNSWIndex()
    raise ValueError(f"unknown or not-yet-implemented index family: {family!r}")
