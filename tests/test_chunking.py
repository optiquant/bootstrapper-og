"""Token-window chunker: page-bounded, provenance-exact, deterministic."""

from __future__ import annotations

from bootstrapper.core.chunking import TokenWindowChunker
from bootstrapper.core.snapshot import content_hash
from bootstrapper.datasets.base import Document

_DOC = Document(
    doc_id="D",
    pages=[
        "one two three four five six seven eight nine ten eleven twelve",
        "short page here",
    ],
    meta={},
)


def test_chunks_are_page_bounded_and_provenance_exact() -> None:
    chunker = TokenWindowChunker(window=4, overlap=1)
    chunks = chunker.chunk(_DOC)
    assert chunks, "expected chunks"
    for chunk in chunks:
        page = _DOC.pages[chunk.locus.page]
        # The locus indexes into the page text and reproduces the chunk exactly.
        assert page[chunk.locus.char_start : chunk.locus.char_end] == chunk.text
        assert chunk.chunk_id == content_hash(chunk.text)
        assert chunk.locus.doc_id == "D"
        assert chunk.locus.page in (0, 1)


def test_short_page_yields_single_chunk() -> None:
    chunker = TokenWindowChunker(window=64, overlap=8)
    page1_chunks = [c for c in chunker.chunk(_DOC) if c.locus.page == 1]
    assert len(page1_chunks) == 1
    assert page1_chunks[0].text == "short page here"


def test_overlap_shares_tokens_between_neighbors() -> None:
    chunker = TokenWindowChunker(window=4, overlap=2)
    page0 = [c for c in chunker.chunk(_DOC) if c.locus.page == 0]
    assert len(page0) >= 2
    first_tokens = page0[0].text.split()
    second_tokens = page0[1].text.split()
    assert set(first_tokens) & set(second_tokens), "overlap should share tokens"


def test_deterministic_ids() -> None:
    chunker = TokenWindowChunker(window=4, overlap=1)
    a = [c.chunk_id for c in chunker.chunk(_DOC)]
    b = [c.chunk_id for c in chunker.chunk(_DOC)]
    assert a == b
