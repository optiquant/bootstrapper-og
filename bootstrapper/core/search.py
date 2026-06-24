"""Interactive retrieval over an in-memory corpus.

The sweep in :mod:`bootstrapper.core.sweep` *measures* retrieval quality against labeled ground
truth and freezes an immutable run. This module is the unlabeled, interactive sibling: build an
index over a set of documents once, then answer free-text queries with ranked, provenance-pinned
passages. No queries, no gold, no run artifact -- it powers the "search your own docs" path.

Like the rest of ``core`` it is dataset-agnostic: it consumes anything shaped like a
:class:`~bootstrapper.datasets.base.Document` and never imports a concrete adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from bootstrapper.core.chunking import Chunk, TokenWindowChunker
from bootstrapper.core.indices import make_index

if TYPE_CHECKING:  # keep core free of a runtime dependency on datasets / a tokenizer model
    from collections.abc import Iterable

    from bootstrapper.core.chunking import Chunker
    from bootstrapper.core.embeddings import EmbeddingProvider
    from bootstrapper.datasets.base import Document


@dataclass(frozen=True)
class SearchHit:
    """One ranked, provenance-pinned passage."""

    rank: int
    score: float  # cosine similarity in [-1, 1]; higher is closer
    chunk_id: str
    text: str
    doc_id: str
    page: int
    char_start: int
    char_end: int


class SearchIndex:
    """A built ANN index over a corpus, queryable by free text.

    Construct with :meth:`build`, then call :meth:`search`. The corpus is chunked with the given
    chunker, embedded with the given provider, and indexed with the named FAISS family. Chunks
    are de-duplicated by content hash (the first-seen locus wins), mirroring the snapshot store.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        chunks: list[Chunk],
        index_family: str,
        search_params: dict[str, int] | None = None,
    ) -> None:
        self.provider = provider
        self.chunks = chunks
        self.index_family = index_family
        self.search_params = search_params or {}
        self._index = make_index(index_family)
        if chunks:
            vectors = provider.embed([c.text for c in chunks])
            self._index.build(vectors, {})
        self.n_documents = len({c.locus.doc_id for c in chunks})

    @classmethod
    def build(
        cls,
        documents: Iterable[Document],
        provider: EmbeddingProvider,
        index_family: str = "flat",
        chunker: Chunker | None = None,
        search_params: dict[str, int] | None = None,
    ) -> SearchIndex:
        chunker = chunker or TokenWindowChunker()
        seen: dict[str, Chunk] = {}
        for doc in documents:
            for chunk in chunker.chunk(doc):
                seen.setdefault(chunk.chunk_id, chunk)  # first-seen locus wins
        return cls(provider, list(seen.values()), index_family, search_params)

    @property
    def n_chunks(self) -> int:
        return len(self.chunks)

    def _embed_query(self, query: str) -> np.ndarray:
        # bge-style providers prefix queries with a retrieval instruction; use it when present.
        embed_query = getattr(self.provider, "embed_query", None)
        if callable(embed_query):
            return np.asarray(embed_query([query]), dtype=np.float32)
        return np.asarray(self.provider.embed([query]), dtype=np.float32)

    def search(self, query: str, k: int = 10) -> list[SearchHit]:
        if not self.chunks or k <= 0:
            return []
        qvec = self._embed_query(query)
        ids, distances = self._index.search(qvec, min(k, len(self.chunks)), self.search_params)
        hits: list[SearchHit] = []
        for rank, (i, dist) in enumerate(zip(ids[0], distances[0], strict=True)):
            if not 0 <= i < len(self.chunks):
                continue  # FAISS pads short result rows with -1
            chunk = self.chunks[int(i)]
            hits.append(
                SearchHit(
                    rank=rank,
                    score=_to_cosine(float(dist), self.index_family),
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    doc_id=chunk.locus.doc_id,
                    page=chunk.locus.page,
                    char_start=chunk.locus.char_start,
                    char_end=chunk.locus.char_end,
                )
            )
        return hits


def _to_cosine(distance: float, index_family: str) -> float:
    """Normalize a FAISS distance to cosine similarity (vectors are L2-normalized).

    ``flat`` uses inner product, which *is* cosine. ``hnsw`` uses squared L2, and for unit
    vectors ``||a - b||^2 = 2 - 2 cos``, so ``cos = 1 - d / 2``.
    """

    if index_family == "hnsw":
        return 1.0 - distance / 2.0
    return distance
