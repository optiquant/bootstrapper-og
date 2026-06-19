"""Chunking.

A ``Chunker`` turns a ``Document`` into content-addressed ``Chunk`` objects while preserving
page provenance. v0 ships a single token-window chunker.

The "token" unit here is a whitespace-delimited word, deliberately model-agnostic: the engine
core must not depend on any particular embedding model's tokenizer. Windows never cross page
boundaries, so every chunk has a well-defined ``SourceLocus.page``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from bootstrapper.core.snapshot import SourceLocus, content_hash

if TYPE_CHECKING:  # avoid a runtime core->datasets dependency; this keeps core dataset-agnostic
    from bootstrapper.datasets.base import Document

_TOKEN_RE = re.compile(r"\S+")


@dataclass(frozen=True)
class Chunk:
    """A content-addressed span of a document."""

    chunk_id: str  # = sha256(text)
    text: str
    locus: SourceLocus


class Chunker(Protocol):
    @property
    def id(self) -> str: ...

    def chunk(self, doc: Document) -> list[Chunk]: ...


@dataclass(frozen=True)
class TokenWindowChunker:
    """Sliding fixed-size token window, page-bounded.

    ``window`` tokens per chunk with ``overlap`` tokens shared between neighbours. Character
    offsets in the emitted ``SourceLocus`` index into the *page* text, so the original substring
    (including its internal whitespace) is exactly ``doc.pages[page][char_start:char_end]``.
    """

    window: int = 256
    overlap: int = 32

    @property
    def id(self) -> str:
        return f"tokenwindow-{self.window}-{self.overlap}"

    def __post_init__(self) -> None:
        if self.window <= 0:
            raise ValueError("window must be positive")
        if not 0 <= self.overlap < self.window:
            raise ValueError("overlap must satisfy 0 <= overlap < window")

    @property
    def _stride(self) -> int:
        return self.window - self.overlap

    def _chunk_page(self, doc_id: str, page: int, text: str) -> list[Chunk]:
        spans = [(m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]
        if not spans:
            return []
        chunks: list[Chunk] = []
        seen_end = -1
        for start_tok in range(0, len(spans), self._stride):
            window_spans = spans[start_tok : start_tok + self.window]
            char_start = window_spans[0][0]
            char_end = window_spans[-1][1]
            # The final short window can be fully contained in the previous one; skip dupes.
            if char_end <= seen_end:
                break
            seen_end = char_end
            chunk_text = text[char_start:char_end]
            locus = SourceLocus(
                doc_id=doc_id, page=page, char_start=char_start, char_end=char_end
            )
            chunks.append(
                Chunk(chunk_id=content_hash(chunk_text), text=chunk_text, locus=locus)
            )
            if start_tok + self.window >= len(spans):
                break
        return chunks

    def chunk(self, doc: Document) -> list[Chunk]:
        out: list[Chunk] = []
        for page_index, page_text in enumerate(doc.pages):
            out.extend(self._chunk_page(doc.doc_id, page_index, page_text))
        return out
