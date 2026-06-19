"""Retrievers.

A ``Retriever`` turns a query into a ranked list of chunk ids. v0 / Gate 1 ships ``dense``
(pure ANN over the embedding index). ``bm25`` and ``hybrid_rrf`` arrive in Gate 3 behind the
same protocol.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from bootstrapper.core.indices import Index

Vectors = NDArray[np.float32]


class Retriever(Protocol):
    id: str  # "dense" | "bm25" | "hybrid_rrf"

    def retrieve(self, query_vec: Vectors, query_text: str, k: int) -> list[str]: ...


class DenseRetriever:
    """Rank chunks purely by ANN similarity in the embedding space.

    Holds a built ``Index`` plus the row->chunk-id map for that index, and the search params to
    apply (e.g. ``{"efSearch": 64}`` for HNSW).
    """

    id = "dense"

    def __init__(
        self, index: Index, id_map: list[str], search_params: dict[str, int] | None = None
    ) -> None:
        self.index = index
        self.id_map = id_map
        self.search_params = search_params or {}

    def retrieve(self, query_vec: Vectors, query_text: str, k: int) -> list[str]:
        ids, _ = self.index.search(query_vec, k, self.search_params)
        row = ids[0]
        return [self.id_map[i] for i in row if 0 <= i < len(self.id_map)]
