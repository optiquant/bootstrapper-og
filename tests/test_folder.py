"""LocalFolderAdapter: ingest a directory of text/markdown as an unlabeled corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrapper.datasets.folder import LocalFolderAdapter


def _corpus(root: Path) -> None:
    (root / "a.txt").write_text("the quick brown fox jumps over the lazy dog", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "b.md").write_text("# Title\n\nsphinx of black quartz", encoding="utf-8")
    (root / "ignore.csv").write_text("not,ingested", encoding="utf-8")  # extension not allowed
    (root / "empty.txt").write_text("   \n  ", encoding="utf-8")  # whitespace-only -> skipped


def test_ingests_text_and_markdown_recursively(tmp_path: Path) -> None:
    _corpus(tmp_path)
    adapter = LocalFolderAdapter(tmp_path)

    assert adapter.labeled is False
    assert adapter.queries() == []

    docs = list(adapter.documents())
    ids = {d.doc_id for d in docs}
    assert ids == {"a.txt", "sub/b.md"}  # .csv excluded, empty.txt dropped, posix relative ids
    for d in docs:
        assert d.meta["source"] == "local-folder"
        assert d.pages and any(p.strip() for p in d.pages)


def test_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        LocalFolderAdapter(tmp_path / "does-not-exist")
