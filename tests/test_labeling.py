"""Labeling: known evidence resolves to the expected chunk; empty resolution fails loudly."""

from __future__ import annotations

import pytest

from bootstrapper.core.chunking import TokenWindowChunker
from bootstrapper.core.labeling import EmptyGoldError, resolve_labels
from bootstrapper.datasets.base import Document, Evidence, Query

# Distinct vocabulary per token so chunk overlap is controlled and predictable.
_PAGE = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi"


def _doc() -> Document:
    return Document(doc_id="D1", pages=[_PAGE], meta={})


def test_known_evidence_resolves_to_expected_chunk() -> None:
    chunker = TokenWindowChunker(window=4, overlap=1)
    chunks = chunker.chunk(_doc())
    target = chunks[1]  # an interior chunk

    query = Query(
        query_id="q1",
        text="irrelevant question text",
        gold=[Evidence(doc_id="D1", page=0, evidence_text=target.text)],
        gt_source="real",
    )
    gold_map, report = resolve_labels([query], chunks, chunker.id)

    assert gold_map["q1"] == {target.chunk_id}
    assert report.clean
    assert report.coverage == 1.0
    report.assert_clean()  # does not raise


def test_evidence_on_wrong_page_does_not_resolve() -> None:
    chunker = TokenWindowChunker(window=4, overlap=1)
    chunks = chunker.chunk(_doc())
    # Correct text, wrong page -> page-scoped candidate restriction yields nothing.
    query = Query(
        query_id="q_wrong_page",
        text="q",
        gold=[Evidence(doc_id="D1", page=7, evidence_text=chunks[0].text)],
        gt_source="real",
    )
    gold_map, report = resolve_labels([query], chunks, chunker.id)
    assert gold_map["q_wrong_page"] == set()
    assert not report.clean


def test_empty_resolution_fails_loudly() -> None:
    chunker = TokenWindowChunker(window=4, overlap=1)
    chunks = chunker.chunk(_doc())
    query = Query(
        query_id="q_nomatch",
        text="q",
        gold=[Evidence(doc_id="D1", page=0, evidence_text="zzzz qqqq wwww vvvv")],
        gt_source="real",
    )
    _, report = resolve_labels([query], chunks, chunker.id)

    assert "q_nomatch" in report.empty_query_ids
    assert not report.clean
    with pytest.raises(EmptyGoldError):
        report.assert_clean()


def test_long_evidence_spanning_multiple_chunks() -> None:
    # Evidence covering the whole page should mark several high-precision chunks gold.
    chunker = TokenWindowChunker(window=4, overlap=0)
    chunks = chunker.chunk(_doc())
    query = Query(
        query_id="q_span",
        text="q",
        gold=[Evidence(doc_id="D1", page=0, evidence_text=_PAGE)],
        gt_source="real",
    )
    gold_map, report = resolve_labels([query], chunks, chunker.id)
    assert len(gold_map["q_span"]) >= 2
    assert report.clean
