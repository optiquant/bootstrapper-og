"""Dataset adapter contract.

The engine is dataset-agnostic. A concrete dataset (FinanceBench, EDGAR, ...) implements
``DatasetAdapter`` and supplies documents, an optional labeled query set, and the chunker the
labels were authored against. Nothing finance-specific lives here.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:  # break the datasets<->core import cycle; resolved by mypy only
    from bootstrapper.core.chunking import Chunker

GroundTruthSource = Literal["real", "synthetic"]


@dataclass(frozen=True)
class Document:
    doc_id: str
    pages: list[str]  # page-segmented text; PDF extraction preserves the page index
    meta: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Evidence:
    doc_id: str
    page: int  # zero-indexed
    evidence_text: str  # gold string; resolved to chunk-ids by text containment


@dataclass(frozen=True)
class Query:
    query_id: str
    text: str
    gold: list[Evidence]
    gt_source: GroundTruthSource  # "real" and "synthetic" are sliced separately, never pooled


class DatasetAdapter(Protocol):
    id: str
    labeled: bool  # True -> has queries+gold; False -> scale corpus, latency only

    def documents(self) -> Iterator[Document]: ...

    def queries(self) -> list[Query]: ...  # empty for scale corpora

    @property
    def chunker(self) -> Chunker: ...
