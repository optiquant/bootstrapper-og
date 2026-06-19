"""Late label resolution.

Span-level ground truth (evidence text + page) is immutable. It is resolved to chunk-ids at
eval time, against the active chunker: candidates are restricted to chunks on the evidence's
page, then matched by normalized token overlap.

A query that resolves to an *empty* gold set means the resolver -- not the index -- is being
measured, so resolution emits a coverage report and fails loudly unless explicitly allowed.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from bootstrapper.core.chunking import Chunk
from bootstrapper.datasets.base import Evidence, Query

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmptyGoldError(RuntimeError):
    """Raised when one or more queries cannot be resolved to any gold chunk."""


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _resolve_evidence(
    evidence: Evidence,
    page_chunks: list[Chunk],
    precision_thresh: float,
    recall_thresh: float,
) -> set[str]:
    """Chunks on the evidence page whose token overlap with the evidence clears a threshold.

    ``precision`` = |chunk ∩ evidence| / |chunk|  (the chunk lies inside the evidence span)
    ``recall``    = |chunk ∩ evidence| / |evidence|  (the chunk captures most of the evidence)

    A chunk is gold if either clears its threshold, which handles both evidence longer than one
    chunk (several high-precision chunks) and evidence shorter than one chunk (one high-recall
    chunk).
    """

    ev_tokens = _tokens(evidence.evidence_text)
    if not ev_tokens:
        return set()
    gold: set[str] = set()
    for chunk in page_chunks:
        c_tokens = _tokens(chunk.text)
        if not c_tokens:
            continue
        inter = len(c_tokens & ev_tokens)
        if inter == 0:
            continue
        precision = inter / len(c_tokens)
        recall = inter / len(ev_tokens)
        if precision >= precision_thresh or recall >= recall_thresh:
            gold.add(chunk.chunk_id)
    return gold


@dataclass(frozen=True)
class CoverageReport:
    chunker_id: str
    total_queries: int
    resolved_queries: int
    empty_query_ids: list[str]
    gold_counts: dict[str, int]  # query_id -> number of resolved gold chunks

    @property
    def coverage(self) -> float:
        return self.resolved_queries / self.total_queries if self.total_queries else 0.0

    @property
    def mean_gold_per_query(self) -> float:
        counts = [c for c in self.gold_counts.values() if c > 0]
        return sum(counts) / len(counts) if counts else 0.0

    @property
    def clean(self) -> bool:
        return len(self.empty_query_ids) == 0

    def assert_clean(self) -> None:
        if not self.clean:
            preview = ", ".join(self.empty_query_ids[:10])
            raise EmptyGoldError(
                f"{len(self.empty_query_ids)}/{self.total_queries} queries resolved to an empty "
                f"gold set under chunker '{self.chunker_id}' (the resolver, not the index, is "
                f"being measured): {preview}"
            )

    def summary(self) -> str:
        return (
            f"coverage={self.coverage:.1%} "
            f"({self.resolved_queries}/{self.total_queries} queries), "
            f"mean_gold/query={self.mean_gold_per_query:.2f}, "
            f"empty={len(self.empty_query_ids)}"
        )


@dataclass
class _ChunkIndex:
    """Chunks grouped by (doc_id, page) for page-scoped candidate restriction."""

    by_doc_page: dict[tuple[str, int], list[Chunk]] = field(default_factory=dict)

    @classmethod
    def build(cls, chunks: Iterable[Chunk]) -> _ChunkIndex:
        grouped: dict[tuple[str, int], list[Chunk]] = defaultdict(list)
        for chunk in chunks:
            grouped[(chunk.locus.doc_id, chunk.locus.page)].append(chunk)
        return cls(by_doc_page=dict(grouped))

    def page(self, doc_id: str, page: int) -> list[Chunk]:
        return self.by_doc_page.get((doc_id, page), [])


def resolve_labels(
    queries: list[Query],
    chunks: Iterable[Chunk],
    chunker_id: str,
    precision_thresh: float = 0.5,
    recall_thresh: float = 0.5,
) -> tuple[dict[str, set[str]], CoverageReport]:
    """Resolve every query's evidence to gold chunk-ids and report coverage.

    Returns ``(gold_map, report)`` where ``gold_map[query_id]`` is the set of gold chunk-ids.
    Call ``report.assert_clean()`` to enforce that no query is empty.
    """

    index = _ChunkIndex.build(chunks)
    gold_map: dict[str, set[str]] = {}
    gold_counts: dict[str, int] = {}
    empty_ids: list[str] = []
    for query in queries:
        gold: set[str] = set()
        for ev in query.gold:
            gold |= _resolve_evidence(
                ev, index.page(ev.doc_id, ev.page), precision_thresh, recall_thresh
            )
        gold_map[query.query_id] = gold
        gold_counts[query.query_id] = len(gold)
        if not gold:
            empty_ids.append(query.query_id)
    report = CoverageReport(
        chunker_id=chunker_id,
        total_queries=len(queries),
        resolved_queries=len(queries) - len(empty_ids),
        empty_query_ids=empty_ids,
        gold_counts=gold_counts,
    )
    return gold_map, report
