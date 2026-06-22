<p align="center">
  <img src="assets/logo.svg" alt="bootstrapper-og" width="520">
</p>

<p align="center">
  <em>A library-first, auditable engine for measuring ANN retrieval over documents — importable as a Python package, served over an HTTP API, with frontends on top.</em>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/License-Apache_2.0-4f46e5.svg"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-4f46e5.svg">
  <img alt="status: perpetual beta" src="https://img.shields.io/badge/status-perpetual%20beta-f59e0b.svg">
</p>

<p align="center">
  <a href="https://optiquant.github.io/bootstrapper-og/"><img alt="Live: run explorer" src="https://img.shields.io/badge/%E2%96%B6%20live-run%20explorer-4f46e5.svg"></a>
</p>

<p align="center">
  <strong><a href="https://optiquant.github.io/bootstrapper-og/">🔎 Open the run explorer →</a></strong>
  &nbsp;·&nbsp; a browser-based UI for the results, no install required
</p>

## In plain terms

When you search a pile of documents — or ask an AI assistant a question about them — something has
to find the handful of passages most likely to hold the answer. The modern way to do that is
**approximate nearest-neighbour (ANN) search** over text embeddings. There are many ways to build
that index, and they trade **accuracy** for **speed** and **memory** in ways that are easy to get
wrong and hard to see.

**bootstrapper-og measures those trade-offs honestly, on real data, and then teaches you the ideas
behind them using your own results.** Point it at a set of documents and questions; it tries
different embedding models and index types and tells you — with proper error bars — how often each
one actually found the right passage, how fast it was, and how much memory it used. Every result it
returns is traceable back to the exact source text it came from.

It exists to make its operator an ANN expert by *forcing measurement* instead of hand-waving — and
then teaching each concept (Voronoi cells, product quantization, HNSW graphs, the bootstrap) against
the numbers you just produced.

> 💝 **A gift to the community.** Free and open source under the **Apache 2.0** license — use it,
> fork it, teach with it, build on it. Contributions and ideas are welcome.

---

### For the technically inclined

bootstrapper-og is a **library first**. At its core is an **auditable retrieval-evaluation
engine** for ANN search over documents: ingest a corpus, sweep a grid of *embedding models × ANN
index families × retrievers*, and report retrieval quality (recall@k, nDCG@k, MRR) with
**bootstrap confidence intervals**, alongside latency, index memory and build time. Every
retrieved chunk is pinned to an immutable, content-hashed source artifact for reproducible audit.
The engine is **dataset-agnostic**; finance is the first loaded dataset.

That engine is consumed three ways, and it never depends on any of them:

- **As a Python package** — `import bootstrapper` and call the curated API (below). This is the
  surface technical teams build on.
- **Over HTTP** — a thin, read-only **FastAPI service** (`bootstrapper.service`) exposes frozen
  runs as JSON, so any non-Python client can consume them.
- **Through frontends** — a read-only **Streamlit dashboard** for the operator, and (in progress)
  a **public UI** for non-technical users that talks to the HTTP API
  ([`web/`](web/) → [live run explorer](https://optiquant.github.io/bootstrapper-og/)).

> **Status: Gate 1 (vertical slice) complete.** FinanceBench mini → page-aware extraction →
> token-window chunking → content-addressed snapshots → cached embeddings → FAISS **Flat + HNSW**
> → dense retrieval → recall/nDCG/MRR + bootstrap CIs → immutable run artifact → read-only
> **Run Browser** and **Compare** tabs. Resolver coverage is **100% (clean)** on the mini corpus.

---

## Use it as a library

The engine installs as a normal Python package with a curated public API — prefer these
top-level names over deep module paths:

```bash
pip install bootstrapper-og          # engine + CLI, no UI dependencies
```

```python
from bootstrapper import (
    FinanceBenchAdapter, HashingEmbeddingProvider, RunStore, get_grid, run_sweep,
)

store = RunStore(".")                                  # artifact root (runs/, snapshots/, cache/)
result = run_sweep(
    adapter=FinanceBenchAdapter(subset="mini"),
    grid=get_grid("gate1-smoke"),                      # offline, deterministic encoder
    providers={"hashing-256": HashingEmbeddingProvider(dim=256)},
    store=store,
    cache_root="cache/embeddings",
    git_sha="unknown",
)
print(result.manifest.run_id, result.coverage.summary())

# read a frozen run back
manifest = store.load_manifest(result.manifest.run_id)
metrics = store.load_metrics(result.manifest.run_id)   # long-format pandas DataFrame
```

`from bootstrapper import *` (or `bootstrapper.__all__`) is the stable contract: the sweep entry
point (`run_sweep`, `SweepResult`), run persistence (`RunStore`, `RunManifest`), dataset types
(`Document`, `Query`, `Evidence`, `DatasetAdapter`, `FinanceBenchAdapter`), grids (`GridConfig`,
`get_grid`), embedding providers, index/retriever builders, metrics and the snapshot store. The
subpackages `bootstrapper.core`, `bootstrapper.datasets` and `bootstrapper.config` each expose
their own curated `__all__`.

---

## Architecture: engine → service → frontends

bootstrapper-og follows the **library-first / API-first** pattern used by tools like **MLflow**
(Python API + tracking server UI), **dbt** (`dbt-core` + dbt Cloud), **Great Expectations** (core
library + GX Cloud) and **LangChain** (`langchain-core` + LangServe + LangSmith): a pure engine,
a thin HTTP boundary, and frontends that depend *downward only*.

```
┌─────────────────────────────────────────────────────────────┐
│  bootstrapper.core / datasets / config   — the engine (SDK)  │  pure Python, no UI deps
└─────────────────────────────────────────────────────────────┘
                 ▲                         ▲
   imports       │                         │  imports
┌────────────────┴───────────┐   ┌─────────┴───────────────────┐
│ bootstrapper.cli           │   │ bootstrapper.service        │  FastAPI, `api` extra
│ (runs sweeps, freezes runs)│   │ (read-only HTTP over runs)  │
└────────────────────────────┘   └─────────┬───────────────────┘
                 ▲                          │  HTTP (JSON)
   imports       │                ┌─────────┴───────────────────┐
┌────────────────┴───────────┐    │ web/  — public UI (Pages)   │  non-technical users
│ bootstrapper.app (Streamlit)│   └─────────────────────────────┘
│ internal dashboard, `app`  │
└────────────────────────────┘
```

The engine carries **no UI dependency**: a base `pip install bootstrapper-og` pulls neither
Streamlit nor FastAPI. Each frontend is an **optional extra**, and the non-technical UI consumes
the engine over HTTP rather than importing it — so it can be any stack and deploy independently.

## Architecture principles (non-negotiable)

1. **Library-first, UI-agnostic engine.** `bootstrapper/core/` imports nothing finance-specific
   **and nothing UI-specific**. Streamlit and FastAPI live behind the `app` / `api` extras;
   `import bootstrapper` never pulls a frontend.
2. **Precomputed-run model.** A run = (corpus × config-grid × query-set), executed offline by the
   CLI and frozen as immutable artifacts. **The Streamlit app and the HTTP service are read-only**
   and import nothing that builds an index.
3. **Embedding cache** keyed by `(embedding_model_id, chunk_id)` — sweeping indices never
   re-embeds.
4. **Content-addressed snapshots.** Every chunk is stored under `sha256(text)` with its source
   locus; a run references chunk hashes only.
5. **Span-level ground truth, resolved late.** Labels (evidence text + page) are immutable and
   resolved to chunk-ids *at eval time* against the active chunker. Empty resolution **fails
   loudly** — that would measure the resolver, not the index.
6. **Real vs synthetic** ground truth are sliced separately, never pooled.
7. **FAISS-first.** v0 uses FAISS only.

## Module layout

```
bootstrapper/
  core/        chunking · snapshot · embeddings · indices · retrievers · labeling · metrics · sweep · run · search
  datasets/    base (DatasetAdapter protocol + dataclasses) · financebench · folder (local/Box corpus)
  config/      grids (named config grids, incl. the offline smoke grid)
  service/     app (read-only HTTP over frozen runs) · local (local runner: index + search your docs)
  app/         streamlit_app + views/ (run_browser, compare) — internal dashboard (`app` extra)
  cli.py       `bootstrapper run ...`
  __init__.py  curated public API (re-exports + __all__)
web/           static UI on GitHub Pages: run explorer (index.html) + search (search.html)
tests/         metrics · labeling · chunking · snapshot · embeddings · indices · sweep · search · folder
```

## Getting started

To *produce* runs you use the **`bootstrapper` command-line tool**: you run it in a terminal
(Terminal on macOS/Linux, or PowerShell on Windows) — not inside Python or a frontend. The
`bootstrapper` command only exists *after* you install the project, and it must run inside the
virtual environment you installed it into. Look for `(.venv)` at the start of your prompt; if you
open a fresh terminal later, re-activate first. (To *consume* runs from your own code, see
[Use it as a library](#use-it-as-a-library) above.)

Run everything from the repository folder: the CLI writes its output (`runs/`, `snapshots/`,
`cache/`, `data/`) into the current directory, and the frontends read from there.

### Install extras

| extra | adds | for |
|-------|------|-----|
| *(base)* | engine + `bootstrapper` CLI | importing the SDK, running sweeps |
| `embed` | `sentence-transformers` | the `bge-small` default embedding (needs a HF download) |
| `app` | `streamlit`, `plotly` | the internal read-only dashboard |
| `api` | `fastapi`, `uvicorn` | the HTTP service layer (`bootstrapper-api`) |
| `sparse` | `rank-bm25` | Gate 3 sparse / hybrid retrieval |
| `edu` | `networkx` | Gate 4 education-layer toy graphs |
| `dev` | `pytest`, `mypy`, `ruff` (+ `app`, `api`) | development & CI |

### Quick start (bash — macOS / Linux)

```bash
# 1. Get the code and enter the folder
git clone https://github.com/optiquant/bootstrapper-og
cd bootstrapper-og

# 2. Create and activate a virtual environment — your prompt should then show "(.venv)"
python -m venv .venv
source .venv/bin/activate

# 3. Install — base is engine + CLI; add the extras you need
pip install -e ".[dev,embed]"     # dev (incl. app + api) + sentence-transformers for bge-small
# pip install -e ".[app]"         # lighter: engine + CLI + Streamlit dashboard only
# pip install -e .                # lightest: engine + CLI only (consume the SDK / offline grid)

# 4. Run a sweep (the heavy work; offline after the first PDF fetch)
bootstrapper run --dataset financebench-mini --grid gate1          # real bge-small (needs internet + "embed")
# bootstrapper run --dataset financebench-mini --grid gate1-smoke  # deterministic offline encoder, no download

# 5a. Browse the results in the internal dashboard (read-only; needs the "app" extra)
bootstrapper list-runs
streamlit run bootstrapper/app/streamlit_app.py

# 5b. ...or serve them over HTTP for any client (read-only; needs the "api" extra)
bootstrapper-api                  # http://127.0.0.1:8000  (interactive docs at /docs)
```

### Windows (PowerShell)

Identical, except activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

### Notes

- **`(.venv)` must be showing.** That means the environment is active and `bootstrapper` is on your
  PATH. Opened a new terminal? Re-run `source .venv/bin/activate` (or the PowerShell line) first, or
  you'll get `command not found`.
- **`gate1` vs `gate1-smoke`.** `gate1` downloads the `bge-small` model from Hugging Face on first
  use (needs internet and the `embed` extra). `gate1-smoke` uses a deterministic offline encoder —
  no download — and is perfect for a quick smoke test.
- **Fallback.** If `bootstrapper` isn't found but the install succeeded, the same command works as
  `python -m bootstrapper.cli run --dataset financebench-mini --grid gate1`.
- **Artifact location.** Both frontends read runs from the current directory by default; point
  them elsewhere with the `BOOTSTRAPPER_ROOT` env var, e.g.
  `BOOTSTRAPPER_ROOT=/path/to/artifacts streamlit run bootstrapper/app/streamlit_app.py` or
  `BOOTSTRAPPER_ROOT=/path/to/artifacts bootstrapper-api`.
- **API host/port.** `bootstrapper-api` binds `127.0.0.1:8000`; override with
  `BOOTSTRAPPER_API_HOST` / `BOOTSTRAPPER_API_PORT`, or run `uvicorn bootstrapper.service.app:app`
  directly for autoreload and worker options.
- Requires **Python 3.11+**.

### Embedding providers

| id            | provider                                   | notes                                            |
|---------------|--------------------------------------------|--------------------------------------------------|
| `bge-small`   | `BAAI/bge-small-en-v1.5` (sentence-transf.) | **documented v0 default**; needs a HF model download |
| `hashing-256` | deterministic char-ngram hashing encoder    | offline, dependency-free; **lexical, not semantic** |

> **Note on the committed sample run.** It uses `hashing-256` because this build environment has
> no egress to `huggingface.co`. The hashing encoder is a signed `HashingVectorizer` (word + char
> n-grams): genuinely lexical, but **not** a semantic model. Its recall is therefore a weak
> lexical baseline (see below), exactly the kind of result that motivates real embeddings. Swap to
> `--grid gate1` in any networked environment to measure `bge-small`. The swap path to
> `bge-base/large` and `voyage-finance-2` is a one-line change in `cli.py` / a new grid.

## Sample Gate-1 results (`financebench-mini`, `gate1-smoke`, n=25 queries)

5 filings, 1,391 unique chunks, 100% resolver coverage. Mean over queries, 95% percentile
bootstrap CI (B=1000):

| index | recall@1 | recall@5 | recall@10 | build | memory |
|-------|----------|----------|-----------|-------|--------|
| flat (exact) | 0.020 | 0.073 | 0.127 `[0.027, 0.273]` | 0.3 ms | 1.42 MB |
| hnsw (efSearch=64) | 0.020 | 0.073 | 0.127 `[0.027, 0.273]` | 43 ms | 1.80 MB |

Flat is exact by construction. HNSW reproduces it exactly at this scale (≈1.4k vectors), so the
recall gap is the *embedding's* (here a lexical hash), not the index's. Latency on a labeled
corpus is **illustrative only** — the recall/latency/memory frontier is measured on the scale
corpus in Gate 2. With only 25 queries the CIs are wide; trust frontier shape over absolute
deltas.

## Reproducibility & artifacts

```
runs/<run_id>/manifest.json   run_id, dataset, chunker, embeddings, full grid, k, B, git_sha, timestamps
runs/<run_id>/metrics.parquet long format, one row per (config, embedding, index, search, retriever, query, gt_source, k, metric)
snapshots/<chunk_id>.json     content-addressed {text, locus}, shared across runs
runs/registry.sqlite          convenience index for the Run Browser (rebuildable from manifests)
```

`data/` (fetched PDFs + extracted pages), `cache/` (embeddings), `snapshots/` and the sqlite
registry are git-ignored and regenerated by `bootstrapper run`. A tiny sample run (`manifest.json`
+ `metrics.parquet`) **is** committed so the frontends are demonstrable on a fresh clone.

## HTTP API

The `api` extra adds a thin, read-only **FastAPI** service (`bootstrapper.service.app`) over the
frozen runs — the boundary the public UI consumes, and a language-agnostic way for any team to
read results. It never builds an index.

```bash
pip install -e ".[api]"
bootstrapper-api            # http://127.0.0.1:8000  · interactive docs at /docs
```

| method & path | returns |
|---------------|---------|
| `GET /health` | liveness + the resolved artifact root |
| `GET /runs` | list run manifests (newest first) |
| `GET /runs/{run_id}` | one run manifest |
| `GET /runs/{run_id}/metrics` | that run's long-format metrics as JSON records |

The public, non-technical UI lives under [`web/`](web/) — a static site published to GitHub
Pages at **<https://optiquant.github.io/bootstrapper-og/>** — and talks to these endpoints. It is
a client of the HTTP service, never an importer of the engine, and ships with a bundled sample so
it works standalone before any live API exists.

## Search your own documents (local runner)

The `api` extra also ships a **local runner** (`bootstrapper.service.local`) that does the one
thing the read-only API deliberately won't: ingest your own documents and **run retrieval over
them, on your machine**. Point it at any folder — a Box Drive (or other cloud-drive) mount is
just a local path — and it chunks, embeds and indexes the corpus in memory, then answers
free-text queries with ranked, provenance-pinned passages. Nothing is uploaded; nothing is
frozen. It is a *separate* app from the published API on purpose, so the public surface never
gains a doc-ingesting endpoint.

```bash
pip install -e ".[api]"            # add ".[embed]" for the semantic bge-small encoder
bootstrapper-search                # http://127.0.0.1:8011 · interactive docs at /docs
```

Then open the **Search your docs** page of the run explorer
([`web/search.html`](web/search.html)), point it at `http://127.0.0.1:8011`, give it a folder,
and search. Because the runner is on your machine, the GitHub Pages UI can call it from your
browser directly (CORS is enabled).

| method & path | does |
|---------------|------|
| `POST /sessions` | ingest a folder → build an in-memory index, returns a `session_id` |
| `GET /sessions` | list active sessions |
| `POST /sessions/{id}/search` | rank passages for a query (text + source locus + cosine score) |
| `DELETE /sessions/{id}` | drop a session |

Or drive it straight from Python — no service required:

```python
from bootstrapper import LocalFolderAdapter, HashingEmbeddingProvider, SearchIndex

adapter = LocalFolderAdapter("~/Documents/filings")          # local or Box Drive path
index = SearchIndex.build(adapter.documents(), HashingEmbeddingProvider(256), chunker=adapter.chunker)
for hit in index.search("what was annual revenue?", k=5):
    print(f"{hit.score:.3f}  {hit.doc_id} p{hit.page}: {hit.text[:80]}")
```

> **Search vs. evaluation.** This is interactive *retrieval* — it needs no ground truth. Turning
> it into a *measured* evaluation (recall/nDCG/MRR) over your own corpus needs a labeled query
> set; auto-generating one is the **synthetic query generator** on the Gate 3 roadmap, the next
> step for "evaluate my own docs".

## Development

```bash
pip install -e ".[dev]"     # engine + CLI + both frontends + pytest/mypy/ruff
pytest                      # metrics & labeling vs hand-computed cases; end-to-end sweep smoke test
mypy bootstrapper tests     # strict, clean
ruff check bootstrapper tests
```

## Roadmap (gated; review at each gate)

- **Gate 1 — done.** Vertical slice above.
- **Gate 2.** IVF + IVFPQ; efSearch/nprobe sweeps; EDGAR scale corpus (≥10⁵ chunks) for
  latency/memory; recall-vs-latency Pareto + memory-vs-recall; Drill-down tab (hash-verified).
- **Gate 3.** BM25 + hybrid RRF; synthetic query generator; real/synthetic slicing everywhere.
- **Gate 4.** Education layer: the canonical TEACHING grid + toy illustrators + run-wired
  explorers + the Learn tab over an ordered ANN syllabus.
- **Gate 5.** Hardening + production deploy to `bootstrapper-og.com`.

**In parallel (frontends track).** The engine + HTTP API are the load-bearing product surface for
technical teams; the read-only Streamlit dashboard and the public UI (`web/`, on GitHub Pages) are
optional frontends layered on top. Expanding the API (auth, pagination, run drill-down) and
building the public UI proceed alongside the gates above.

## References & further reading

Every concept this project measures and teaches, linked to its canonical source. The Learn tab
(Gate 4) will walk through these against your own runs — this list is the syllabus's bibliography.

**Foundations**

- **Why high dimensions are weird** — Beyer, Goldstein, Ramakrishnan & Shaft, *When Is "Nearest
  Neighbor" Meaningful?* (ICDT 1999). [doi:10.1007/3-540-49257-7_15](https://doi.org/10.1007/3-540-49257-7_15)
- **The bootstrap** (confidence intervals as a metric's sampling distribution over queries) —
  Efron, *Bootstrap Methods: Another Look at the Jackknife* (Annals of Statistics, 1979).
  [doi:10.1214/aos/1176344552](https://doi.org/10.1214/aos/1176344552)
- **nDCG** (ranking evaluation) — Järvelin & Kekäläinen, *Cumulated Gain-based Evaluation of IR
  Techniques* (ACM TOIS, 2002). [doi:10.1145/582415.582418](https://doi.org/10.1145/582415.582418)

**ANN index families**

- **Faiss** (the engine v0 builds on) — Douze et al., *The Faiss library* (2024).
  [arXiv:2401.08281](https://arxiv.org/abs/2401.08281); GPU foundations in Johnson, Douze &
  Jégou, *Billion-scale similarity search with GPUs* (2017). [arXiv:1702.08734](https://arxiv.org/abs/1702.08734)
- **IVF + Product Quantization** (and IVFADC = IVFPQ) — Jégou, Douze & Schmid, *Product
  Quantization for Nearest Neighbor Search* (IEEE TPAMI, 2011).
  [doi:10.1109/TPAMI.2010.57](https://doi.org/10.1109/TPAMI.2010.57)
- **HNSW** proximity graphs — Malkov & Yashunin, *Efficient and Robust Approximate Nearest
  Neighbor Search Using Hierarchical Navigable Small World Graphs* (2016/2018).
  [arXiv:1603.09320](https://arxiv.org/abs/1603.09320)

**Retrieval & embeddings**

- **BM25** (sparse lexical baseline) — Robertson & Zaragoza, *The Probabilistic Relevance
  Framework: BM25 and Beyond* (2009). [doi:10.1561/1500000019](https://doi.org/10.1561/1500000019)
- **Reciprocal Rank Fusion** (hybrid retrieval) — Cormack, Clarke & Büttcher, *Reciprocal Rank
  Fusion Outperforms Condorcet and Individual Rank Learning Methods* (SIGIR 2009).
  [doi:10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114)
- **Dense passage retrieval** — Karpukhin et al., *Dense Passage Retrieval for Open-Domain
  Question Answering* (2020). [arXiv:2004.04906](https://arxiv.org/abs/2004.04906)
- **Sentence embeddings** — Reimers & Gurevych, *Sentence-BERT* (2019).
  [arXiv:1908.10084](https://arxiv.org/abs/1908.10084)
- **BGE** (the default embedding model, `bge-small-en-v1.5`) — Xiao, Liu, Zhang & Muennighoff,
  *C-Pack: Packaged Resources to Advance General Text Embedding* (2023).
  [arXiv:2309.07597](https://arxiv.org/abs/2309.07597)

**Context & dataset**

- **Retrieval-augmented generation** (why any of this matters for LLMs) — Lewis et al.,
  *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (2020).
  [arXiv:2005.11401](https://arxiv.org/abs/2005.11401)
- **FinanceBench** (the first loaded dataset) — Islam et al., *FinanceBench: A New Benchmark for
  Financial Question Answering* (2023). [arXiv:2311.11944](https://arxiv.org/abs/2311.11944)

## Contributing

Issues, ideas and pull requests are welcome — whether that's a new index family, a dataset
adapter, an API endpoint, a sharper explainer for the Learn tab, or just a question. Keep the
engine in `bootstrapper/core/` dataset-agnostic **and free of any UI/service dependency**, keep
the Streamlit app and the HTTP service read-only, and run `pytest`, `mypy` and `ruff` before
opening a PR.

## License

Released under the [Apache License 2.0](LICENSE) — © 2026 Viren Desai. A gift to the community:
free to use, modify and build upon, with patent protection and attribution. Enjoy, and build
something good with it.
