"""Local-folder adapter: ingest a directory of documents as an unlabeled corpus.

Points the engine at any folder of PDFs / text / markdown on disk -- including a Box Drive (or
other cloud-drive) mount, which simply appears as a local path. It yields :class:`Document`
objects but no queries: there is no ground truth, so it drives interactive *search*
(:mod:`bootstrapper.core.search`), not the labeled evaluation sweep.

All file I/O lives here; the engine core stays dataset-agnostic.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from bootstrapper.core.chunking import Chunker, TokenWindowChunker
from bootstrapper.datasets.base import Document, Query

#: Extensions ingested by default. PDFs are page-segmented; text/markdown are single-"page".
DEFAULT_EXTENSIONS: tuple[str, ...] = (".pdf", ".txt", ".md", ".markdown")


class LocalFolderAdapter:
    """An unlabeled corpus read from a local directory tree.

    ``path`` is scanned recursively for files whose suffix is in ``extensions``. ``doc_id`` is the
    path relative to ``path`` (stable and human-readable). Decode/parse errors on a single file
    are skipped rather than failing the whole ingest.
    """

    labeled = False

    def __init__(
        self,
        path: Path | str,
        extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
        window: int = 256,
        overlap: int = 32,
    ) -> None:
        self.path = Path(path).expanduser()
        if not self.path.is_dir():
            raise NotADirectoryError(f"not a directory: {self.path}")
        self.extensions = tuple(e.lower() for e in extensions)
        self.id = f"local-folder:{self.path.name}"
        self._chunker = TokenWindowChunker(window=window, overlap=overlap)

    @property
    def chunker(self) -> Chunker:
        return self._chunker

    def _files(self) -> list[Path]:
        return sorted(
            p
            for p in self.path.rglob("*")
            if p.is_file() and p.suffix.lower() in self.extensions
        )

    def _pages(self, file: Path) -> list[str]:
        if file.suffix.lower() == ".pdf":
            # Lazy import: only a PDF in the folder pulls the PDF stack.
            from pypdf import PdfReader

            reader = PdfReader(str(file))
            return [(page.extract_text() or "") for page in reader.pages]
        return [file.read_text(encoding="utf-8", errors="replace")]

    def documents(self) -> Iterator[Document]:
        for file in self._files():
            try:
                pages = self._pages(file)
            except Exception:  # a single unreadable/corrupt file must not sink the whole ingest
                continue
            if not any(p.strip() for p in pages):
                continue
            rel = file.relative_to(self.path).as_posix()
            yield Document(
                doc_id=rel,
                pages=pages,
                meta={"source": "local-folder", "path": str(file), "suffix": file.suffix.lower()},
            )

    def queries(self) -> list[Query]:
        # Unlabeled corpus: no ground truth. Evaluation needs synthetic queries (Gate 3).
        return []
