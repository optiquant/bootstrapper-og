"""SearchIndex: build an index over documents and retrieve provenance-pinned passages."""

from __future__ import annotations

from bootstrapper.core.embeddings import HashingEmbeddingProvider
from bootstrapper.core.search import SearchIndex
from bootstrapper.datasets.base import Document


def _docs() -> list[Document]:
    return [
        Document(doc_id="finance.txt", pages=["quarterly revenue grew on strong cloud sales"]),
        Document(doc_id="weather.txt", pages=["heavy rainfall and thunderstorms are forecast"]),
    ]


def test_search_ranks_relevant_doc_first() -> None:
    index = SearchIndex.build(_docs(), HashingEmbeddingProvider(dim=256), index_family="flat")
    assert index.n_chunks > 0
    assert index.n_documents == 2

    hits = index.search("how did cloud revenue do this quarter?", k=2)
    assert hits, "expected at least one hit"
    top = hits[0]
    assert top.doc_id == "finance.txt"
    assert top.rank == 0
    # provenance points back to the exact source span
    assert top.text == "quarterly revenue grew on strong cloud sales"[top.char_start : top.char_end]
    assert top.page == 0


def test_empty_corpus_returns_no_hits() -> None:
    index = SearchIndex.build([], HashingEmbeddingProvider(dim=64))
    assert index.n_chunks == 0
    assert index.search("anything", k=5) == []


def test_k_bounds_results() -> None:
    index = SearchIndex.build(_docs(), HashingEmbeddingProvider(dim=128))
    assert len(index.search("rain", k=1)) == 1
