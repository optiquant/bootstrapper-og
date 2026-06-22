"""FinanceBench labeled adapter.

FinanceBench (Patronus AI) pairs 10-K / 10-Q / earnings PDFs with span-level evidence labels
(``evidence_text`` + zero-indexed ``evidence_page_num``). This adapter fetches the metadata and
PDFs from the project's GitHub mirror, extracts page-segmented text with pypdf (preserving the
page index that the labels reference), and exposes documents + a labeled query set.

Network fetches are cached on disk under ``data_root``; a second run is offline. All
finance-specificity lives here -- the engine core never imports this module.
"""

from __future__ import annotations

import json
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from bootstrapper.core.chunking import Chunker, TokenWindowChunker
from bootstrapper.datasets.base import Document, Evidence, Query

_BASE = "https://raw.githubusercontent.com/patronus-ai/financebench/main"
_METADATA_URL = f"{_BASE}/data/financebench_open_source.jsonl"


def _pdf_url(doc_name: str) -> str:
    return f"{_BASE}/pdfs/{doc_name}.pdf"


def _http_get(url: str, timeout: int = 90, retries: int = 4) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data: bytes = resp.read()
                return data
        except Exception as exc:  # retry any transient network failure
            last = exc
            if attempt < retries - 1:
                time.sleep(2.0 * (2**attempt))
    raise RuntimeError(f"failed to fetch {url} after {retries} attempts: {last}")


class FinanceBenchAdapter:
    """Flagship labeled adapter.

    ``subset`` selects which documents are loaded: ``"mini"`` (a small, fast, well-resolving set
    for Gate 1), ``"all"`` (every document referenced by the metadata), or an explicit list of
    document names.
    """

    # A compact mini corpus (5 filings, 25 labeled questions) spanning an earnings release, a
    # 10-Q and three 10-Ks across sectors. Chosen for breadth + modest page count; all evidence
    # resolves at 100% coverage under the token-window chunker (verified, not assumed).
    MINI_DOCS: tuple[str, ...] = (
        "ULTABEAUTY_2023Q4_EARNINGS",
        "3M_2023Q2_10Q",
        "AMD_2022_10K",
        "AMCOR_2023_10K",
        "BOEING_2022_10K",
    )

    def __init__(
        self,
        subset: str | list[str] = "mini",
        data_root: Path | str = "data/financebench",
        window: int = 256,
        overlap: int = 32,
    ) -> None:
        self.data_root = Path(data_root)
        self._chunker = TokenWindowChunker(window=window, overlap=overlap)
        self.labeled = True
        self._records: list[dict[str, Any]] | None = None
        if subset == "mini":
            self.id = "financebench-mini"
            self._doc_names: list[str] | None = list(self.MINI_DOCS)
        elif subset == "all":
            self.id = "financebench-all"
            self._doc_names = None  # resolved from metadata
        elif isinstance(subset, list):
            self.id = "financebench-custom"
            self._doc_names = list(subset)
        else:
            raise ValueError(f"unknown subset {subset!r}")

    @property
    def chunker(self) -> Chunker:
        return self._chunker

    # ---- metadata ------------------------------------------------------------------------
    def _metadata_path(self) -> Path:
        return self.data_root / "financebench_open_source.jsonl"

    def _load_records(self) -> list[dict[str, Any]]:
        if self._records is None:
            path = self._metadata_path()
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(_http_get(_METADATA_URL))
            self._records = [
                json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line
            ]
        return self._records

    def _selected_doc_names(self) -> list[str]:
        if self._doc_names is not None:
            return self._doc_names
        seen: dict[str, None] = {}
        for rec in self._load_records():
            seen.setdefault(str(rec["doc_name"]), None)
        return list(seen)

    # ---- documents -----------------------------------------------------------------------
    def _pages(self, doc_name: str) -> list[str]:
        cache = self.data_root / "pages" / f"{doc_name}.json"
        if cache.exists():
            pages: list[str] = json.loads(cache.read_text(encoding="utf-8"))
            return pages
        pdf_path = self.data_root / "pdfs" / f"{doc_name}.pdf"
        if not pdf_path.exists():
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(_http_get(_pdf_url(doc_name)))
        # Lazy import: pypdf is only needed to extract PDF pages, so importing the adapter (and
        # thus the public SDK) stays light and never pulls a PDF stack until a corpus is read.
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        extracted = [(page.extract_text() or "") for page in reader.pages]
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(extracted, ensure_ascii=False), encoding="utf-8")
        return extracted

    def documents(self) -> Iterator[Document]:
        for doc_name in self._selected_doc_names():
            pages = self._pages(doc_name)
            yield Document(
                doc_id=doc_name,
                pages=pages,
                meta={"source": "financebench", "doc_name": doc_name},
            )

    # ---- queries -------------------------------------------------------------------------
    def queries(self) -> list[Query]:
        selected = set(self._selected_doc_names())
        out: list[Query] = []
        for rec in self._load_records():
            doc_name = str(rec["doc_name"])
            if doc_name not in selected:
                continue
            evidence: list[Evidence] = []
            for ev in rec.get("evidence", []) or []:
                page = ev.get("evidence_page_num")
                text = ev.get("evidence_text")
                if page is None or not text:
                    continue
                evidence.append(
                    Evidence(doc_id=doc_name, page=int(page), evidence_text=str(text))
                )
            if not evidence:
                continue
            out.append(
                Query(
                    query_id=str(rec["financebench_id"]),
                    text=str(rec["question"]),
                    gold=evidence,
                    gt_source="real",
                )
            )
        return out
