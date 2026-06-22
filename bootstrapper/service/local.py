"""Local runner: build an index over your own docs and search them, on your machine.

This is the **execution** counterpart to the read-only artifact API in
:mod:`bootstrapper.service.app`. It is meant to run **locally** (``bootstrapper-search``): it
ingests a folder you point it at -- including a Box Drive mount, which is just a local path --
chunks and embeds it in memory, and answers free-text queries with ranked, provenance-pinned
passages. Nothing is frozen to disk; sessions live in memory for the lifetime of the process.

It is deliberately a *separate* app from the public API so the published, read-only surface never
gains a doc-ingesting or index-building endpoint. Run it with the ``api`` extra::

    pip install "bootstrapper-og[api]"
    bootstrapper-search          # http://127.0.0.1:8011  (docs at /docs)
"""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bootstrapper.core.embeddings import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
    SentenceTransformerProvider,
)
from bootstrapper.core.search import SearchIndex
from bootstrapper.datasets.folder import DEFAULT_EXTENSIONS, LocalFolderAdapter

app = FastAPI(
    title="bootstrapper-og local runner",
    summary="Index a local folder of documents and search it interactively.",
    description=(
        "Runs the engine locally over your own documents. POST a folder path to build an "
        "in-memory index, then search it. Pair it with the static run explorer's *Search* page."
    ),
    version="0.1.0",
)

# Local, single-user, public-by-nature search results: permissive CORS so the static UI (served
# from GitHub Pages over https) can call this http://127.0.0.1 service from your browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip() for o in os.environ.get("BOOTSTRAPPER_API_CORS", "*").split(",") if o.strip()
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


class _Session:
    def __init__(self, index: SearchIndex, request: BuildRequest, path: str) -> None:
        self.index = index
        self.request = request
        self.path = path


_SESSIONS: dict[str, _Session] = {}


def _make_provider(embedding_id: str) -> EmbeddingProvider:
    if embedding_id == "hashing-256":
        return HashingEmbeddingProvider(dim=256)
    if embedding_id == "bge-small":
        return SentenceTransformerProvider()
    raise HTTPException(
        status_code=400,
        detail=f"unknown embedding id {embedding_id!r} (try: hashing-256, bge-small)",
    )


class BuildRequest(BaseModel):
    path: str = Field(description="Folder to ingest (recursively). A Box Drive mount works too.")
    embedding_id: str = "hashing-256"
    index_family: str = "flat"
    window: int = 256
    overlap: int = 32
    extensions: list[str] = Field(default_factory=lambda: list(DEFAULT_EXTENSIONS))


class SessionInfo(BaseModel):
    session_id: str
    path: str
    embedding_id: str
    index_family: str
    n_documents: int
    n_chunks: int


class SearchRequest(BaseModel):
    query: str
    k: int = 10


class Hit(BaseModel):
    rank: int
    score: float
    chunk_id: str
    text: str
    doc_id: str
    page: int
    char_start: int
    char_end: int


class SearchResponse(BaseModel):
    session_id: str
    query: str
    k: int
    hits: list[Hit]


def _info(session_id: str, s: _Session) -> SessionInfo:
    return SessionInfo(
        session_id=session_id,
        path=s.path,
        embedding_id=s.request.embedding_id,
        index_family=s.request.index_family,
        n_documents=s.index.n_documents,
        n_chunks=s.index.n_chunks,
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "sessions": len(_SESSIONS)}


@app.post("/sessions", response_model=SessionInfo)
def build_session(req: BuildRequest) -> SessionInfo:
    try:
        adapter = LocalFolderAdapter(
            req.path,
            extensions=tuple(req.extensions),
            window=req.window,
            overlap=req.overlap,
        )
    except (NotADirectoryError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    provider = _make_provider(req.embedding_id)
    index = SearchIndex.build(
        adapter.documents(),
        provider,
        index_family=req.index_family,
        chunker=adapter.chunker,
    )
    if index.n_chunks == 0:
        raise HTTPException(
            status_code=422,
            detail=f"no ingestable text found under {adapter.path} (extensions: {req.extensions})",
        )
    session_id = uuid.uuid4().hex[:12]
    session = _Session(index, req, str(adapter.path))
    _SESSIONS[session_id] = session
    return _info(session_id, session)


@app.get("/sessions", response_model=list[SessionInfo])
def list_sessions() -> list[SessionInfo]:
    return [_info(sid, s) for sid, s in _SESSIONS.items()]


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, str]:
    if _SESSIONS.pop(session_id, None) is None:
        raise HTTPException(status_code=404, detail=f"session {session_id!r} not found")
    return {"deleted": session_id}


@app.post("/sessions/{session_id}/search", response_model=SearchResponse)
def search(session_id: str, req: SearchRequest) -> SearchResponse:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"session {session_id!r} not found")
    hits = [Hit(**asdict(h)) for h in session.index.search(req.query, k=req.k)]
    return SearchResponse(session_id=session_id, query=req.query, k=req.k, hits=hits)


def run() -> None:
    """Console-script entry point (``bootstrapper-search``)."""

    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("BOOTSTRAPPER_SEARCH_HOST", "127.0.0.1"),
        port=int(os.environ.get("BOOTSTRAPPER_SEARCH_PORT", "8011")),
    )


if __name__ == "__main__":
    run()
