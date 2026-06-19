"""Content-addressed snapshot store.

Every chunk of text is stored under ``sha256(text)`` together with its source locus, so a
run references chunk hashes only and any retrieved chunk can be pinned back to an immutable,
verifiable artifact. The store is dataset-agnostic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceLocus:
    """Provenance of a span of text within a source document."""

    doc_id: str
    page: int  # zero-indexed, matches FinanceBench
    char_start: int
    char_end: int


@dataclass(frozen=True)
class SnapshotRecord:
    """What the store persists for a chunk id: the text and its (first-seen) locus."""

    text: str
    locus: SourceLocus


def content_hash(text: str) -> str:
    """Return the content address of ``text`` (``sha256`` hex digest of its UTF-8 bytes)."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SnapshotStore:
    """A directory of ``<chunk_id>.json`` files, shared across runs.

    Writes are idempotent: a given content hash is written once. The store never imports a
    ``Chunk`` type so that :mod:`bootstrapper.core.chunking` may depend on it without a cycle.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, chunk_id: str) -> Path:
        return self.root / f"{chunk_id}.json"

    def put(self, text: str, locus: SourceLocus) -> str:
        """Store ``text`` under its content hash and return the chunk id.

        If a snapshot with the same hash already exists it is left untouched (the first-seen
        locus wins), preserving immutability and de-duplicating identical spans.
        """

        chunk_id = content_hash(text)
        path = self._path(chunk_id)
        if not path.exists():
            payload = {"text": text, "locus": asdict(locus)}
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        return chunk_id

    def exists(self, chunk_id: str) -> bool:
        return self._path(chunk_id).exists()

    def get(self, chunk_id: str) -> SnapshotRecord:
        """Load a snapshot. Raises ``KeyError`` if the chunk id is unknown."""

        path = self._path(chunk_id)
        if not path.exists():
            raise KeyError(chunk_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SnapshotRecord(text=payload["text"], locus=SourceLocus(**payload["locus"]))

    def verify(self, chunk_id: str) -> bool:
        """Return ``True`` iff the stored text still hashes to its content address.

        Used by the Drill-down tab to prove that a retrieved chunk is the immutable artifact
        it claims to be.
        """

        try:
            record = self.get(chunk_id)
        except KeyError:
            return False
        return content_hash(record.text) == chunk_id
