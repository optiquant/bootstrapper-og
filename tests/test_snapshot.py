"""Content-addressed snapshot store: hash roundtrip, idempotent writes, hash-verify."""

from __future__ import annotations

import json
from pathlib import Path

from bootstrapper.core.snapshot import SnapshotStore, SourceLocus, content_hash

_LOCUS = SourceLocus(doc_id="D1", page=2, char_start=0, char_end=10)


def test_put_get_roundtrip(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    text = "the cash flow statement"
    cid = store.put(text, _LOCUS)
    assert cid == content_hash(text)
    record = store.get(cid)
    assert record.text == text
    assert record.locus == _LOCUS


def test_put_is_idempotent(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    text = "idempotent"
    cid1 = store.put(text, _LOCUS)
    # A second locus for the same content must not overwrite the first-seen snapshot.
    cid2 = store.put(text, SourceLocus(doc_id="D2", page=9, char_start=5, char_end=99))
    assert cid1 == cid2
    assert store.get(cid1).locus == _LOCUS


def test_verify_detects_tampering(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    cid = store.put("authentic text", _LOCUS)
    assert store.verify(cid) is True
    assert store.verify("0" * 64) is False  # unknown id

    # Tamper: write a snapshot whose stored text no longer hashes to its filename.
    tampered = "deadbeef" * 8
    (tmp_path / f"{tampered}.json").write_text(
        json.dumps({"text": "not the original", "locus": _LOCUS.__dict__}),
        encoding="utf-8",
    )
    assert store.verify(tampered) is False
