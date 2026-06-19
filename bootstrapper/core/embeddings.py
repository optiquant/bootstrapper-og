"""Embeddings and the on-disk embedding cache.

An ``EmbeddingProvider`` maps text to L2-normalized float32 vectors. The cache is keyed by
``(embedding_model_id, chunk_id)`` so that sweeping many index families over one corpus never
re-embeds: vectors are computed once per model and reused.

Two providers ship in v0:

* ``SentenceTransformerProvider`` -- the documented default ``BAAI/bge-small-en-v1.5``. It
  imports ``sentence_transformers`` lazily so that merely importing this module (e.g. from the
  read-only Streamlit app) never pulls in torch, and so the engine runs offline with the
  hashing provider when a model download is unavailable.
* ``HashingEmbeddingProvider`` -- a deterministic, dependency-free signed feature-hashing
  encoder. It carries genuine lexical signal (shared words raise cosine similarity), which makes
  it suitable both for fast unit tests and for fully reproducible offline runs.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

Vectors = NDArray[np.float32]

_WORD_RE = re.compile(r"[a-z0-9]+")
_CHAR_NGRAMS = (3, 4, 5)


@lru_cache(maxsize=1_000_000)
def _feature_hash(feature: str) -> int:
    """Stable (unsalted) hash of a feature string; memoized across the process."""

    return int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")


def _features(text: str) -> list[str]:
    """Word unigrams plus word-boundary character n-grams (a char_wb-style analyzer).

    Char n-grams let the encoder share signal across morphology, numbers and entity names, so a
    question and the passage that answers it overlap far more than under whole-word matching --
    while remaining purely lexical (no semantics).
    """

    words = _WORD_RE.findall(text.lower())
    feats: list[str] = list(words)
    for word in words:
        padded = f"#{word}#"
        for n in _CHAR_NGRAMS:
            if len(padded) >= n:
                feats.extend(padded[i : i + n] for i in range(len(padded) - n + 1))
    return feats


def _l2_normalize(matrix: Vectors) -> Vectors:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    normalized: Vectors = (matrix / norms).astype(np.float32)
    return normalized


class EmbeddingProvider(Protocol):
    id: str
    dim: int

    def embed(self, texts: list[str]) -> Vectors: ...  # (n, dim) float32, L2-normalized


class HashingEmbeddingProvider:
    """Deterministic signed feature hashing over words + char n-grams.

    Offline and dependency-free, equivalent to a signed ``HashingVectorizer`` with a char_wb
    analyzer. Feature counts are dampened with ``1 + log(tf)`` and hashed into ``dim`` buckets
    with a sign derived from a second hash bit, then the row is L2-normalized. Empty text maps to
    a fixed unit vector so no zero rows reach the index. This carries genuine lexical signal but
    no semantics -- it is the offline stand-in for the bge-small default, not a replacement.
    """

    def __init__(self, dim: int = 256) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim
        self.id = f"hashing-{dim}"

    def _embed_one(self, text: str) -> NDArray[np.float32]:
        vec = np.zeros(self.dim, dtype=np.float32)
        counts: dict[str, int] = {}
        for feat in _features(text):
            counts[feat] = counts.get(feat, 0) + 1
        if not counts:
            vec[0] = 1.0
            return vec
        for feat, tf in counts.items():
            h = _feature_hash(feat)
            bucket = h % self.dim
            sign = 1.0 if (h >> 1) & 1 else -1.0
            vec[bucket] += sign * (1.0 + float(np.log(tf)))
        return vec

    def embed(self, texts: list[str]) -> Vectors:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        matrix = np.vstack([self._embed_one(t) for t in texts]).astype(np.float32)
        return _l2_normalize(matrix)


class SentenceTransformerProvider:
    """The documented v0 default: a local sentence-transformers model (bge-small).

    bge models recommend prefixing *queries* (not passages) with a retrieval instruction; use
    :meth:`embed_query` for query text and :meth:`embed` for chunk text.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        provider_id: str = "bge-small",
        dim: int = 384,
        query_instruction: str = "Represent this sentence for searching relevant passages: ",
        batch_size: int = 64,
    ) -> None:
        self.model_name = model_name
        self.id = provider_id
        self.dim = dim
        self.query_instruction = query_instruction
        self.batch_size = batch_size
        self._model: object | None = None

    def _ensure_model(self) -> object:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _encode(self, texts: list[str]) -> Vectors:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        model = self._ensure_model()
        vectors = model.encode(  # type: ignore[attr-defined]
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    def embed(self, texts: list[str]) -> Vectors:
        return self._encode(texts)

    def embed_query(self, texts: list[str]) -> Vectors:
        return self._encode([self.query_instruction + t for t in texts])


class EmbeddingCache:
    """On-disk cache of chunk embeddings keyed by ``(provider.id, chunk_id)``.

    Layout: ``<root>/<provider.id>/{vectors.npy, index.json}``. ``encode`` returns vectors in
    the order requested, computing and persisting only the misses.
    """

    def __init__(self, root: Path | str, provider: EmbeddingProvider) -> None:
        self.provider = provider
        self.dir = Path(root) / provider.id
        self.dir.mkdir(parents=True, exist_ok=True)
        self._vectors_path = self.dir / "vectors.npy"
        self._index_path = self.dir / "index.json"
        self._index: dict[str, int] = {}
        self._vectors: Vectors = np.zeros((0, provider.dim), dtype=np.float32)
        self._load()

    def _load(self) -> None:
        if self._index_path.exists() and self._vectors_path.exists():
            self._index = json.loads(self._index_path.read_text(encoding="utf-8"))
            vectors = np.load(self._vectors_path)
            if vectors.shape[1] != self.provider.dim:
                raise ValueError(
                    f"cached dim {vectors.shape[1]} != provider dim {self.provider.dim} "
                    f"for '{self.provider.id}'"
                )
            self._vectors = vectors.astype(np.float32)

    def _persist(self) -> None:
        np.save(self._vectors_path, self._vectors)
        self._index_path.write_text(json.dumps(self._index), encoding="utf-8")

    def encode(self, items: list[tuple[str, str]]) -> Vectors:
        """Embed ``(chunk_id, text)`` pairs, returning an aligned ``(len(items), dim)`` matrix."""

        misses = [(cid, text) for cid, text in items if cid not in self._index]
        # De-duplicate misses while preserving order (identical content hashes appear once).
        unique_misses: dict[str, str] = {}
        for cid, text in misses:
            unique_misses.setdefault(cid, text)
        if unique_misses:
            new_vectors = self.provider.embed(list(unique_misses.values()))
            start = self._vectors.shape[0]
            self._vectors = np.vstack([self._vectors, new_vectors]).astype(np.float32)
            for offset, cid in enumerate(unique_misses):
                self._index[cid] = start + offset
            self._persist()
        rows = [self._index[cid] for cid, _ in items]
        if not rows:
            return np.zeros((0, self.provider.dim), dtype=np.float32)
        return self._vectors[rows].astype(np.float32)
