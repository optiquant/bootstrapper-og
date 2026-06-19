<p align="center">
  <img src="assets/logo.svg" alt="bootstrapper-og" width="520">
</p>

<p align="center">
  <em>An open lab for ANN retrieval over documents — measure it, then learn the theory against your own runs.</em>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/License-Apache_2.0-4f46e5.svg"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-4f46e5.svg">
  <img alt="status: perpetual beta" src="https://img.shields.io/badge/status-perpetual%20beta-f59e0b.svg">
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

An **auditable retrieval-evaluation harness** for ANN search over documents, paired with a
native-Streamlit, math-driven **education layer**. It ingests a corpus, sweeps a grid of *embedding
models × ANN index families × retrievers*, and reports retrieval quality (recall@k, nDCG@k, MRR)
with **bootstrap confidence intervals**, alongside latency, index memory and build time. Every
retrieved chunk is pinned to an immutable, content-hashed source artifact for reproducible audit.
The engine is **dataset-agnostic**; finance is the first loaded dataset.

> **Status: Gate 1 (vertical slice) complete.** FinanceBench mini → page-aware extraction →
> token-window chunking → content-addressed snapshots → cached embeddings → FAISS **Flat + HNSW**
> → dense retrieval → recall/nDCG/MRR + bootstrap CIs → immutable run artifact → read-only
> **Run Browser** and **Compare** tabs. Resolver coverage is **100% (clean)** on the mini corpus.

---

## Architecture principles (non-negotiable)

1. **Dataset-agnostic engine.** `bootstrapper/core/` imports nothing finance-specific. Finance
   lives entirely behind a `DatasetAdapter` in `bootstrapper/datasets/`.
2. **Precomputed-run model.** A run = (corpus × config-grid × query-set), executed offline by the
   CLI and frozen as immutable artifacts. **Streamlit is read-only** and imports nothing that
   builds an index.
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
  core/        chunking · snapshot · embeddings · indices · retrievers · labeling · metrics · sweep · run
  datasets/    base (DatasetAdapter protocol + dataclasses) · financebench
  config/      grids (named config grids, incl. the offline smoke grid)
  app/         streamlit_app + views/ (run_browser, compare)
  cli.py       `bootstrapper run ...`
tests/         metrics · labeling · chunking · snapshot · embeddings · indices · sweep (end-to-end)
```

## Install

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"          # engine + CLI + app + test/lint tooling
pip install -e ".[dev,embed]"    # additionally installs sentence-transformers (the bge-small default)
```

## Quickstart

```bash
# 1. Execute a run (heavy work; offline after the first PDF fetch).
bootstrapper run --dataset financebench-mini --grid gate1          # real bge-small embeddings
bootstrapper run --dataset financebench-mini --grid gate1-smoke    # deterministic offline encoder

bootstrapper list-runs

# 2. Browse the results (read-only).
streamlit run bootstrapper/app/streamlit_app.py
```

Point the app at an artifact root with `BOOTSTRAPPER_ROOT` (defaults to the current directory).

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
+ `metrics.parquet`) **is** committed so the app is demonstrable on a fresh clone.

## Development

```bash
pytest          # metrics & labeling vs hand-computed cases; end-to-end sweep smoke test
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
adapter, a sharper explainer for the Learn tab, or just a question. Keep the engine in
`bootstrapper/core/` dataset-agnostic, keep Streamlit read-only, and run `pytest`, `mypy` and
`ruff` before opening a PR.

## License

Released under the [Apache License 2.0](LICENSE) — © 2026 Viren Desai. A gift to the community:
free to use, modify and build upon, with patent protection and attribution. Enjoy, and build
something good with it.
