"""``bootstrapper`` command-line interface.

The CLI runs all heavy work (ingest, embed, build, query, score) offline and freezes the result
as an immutable run artifact. The Streamlit app only ever reads those artifacts.

Examples
--------
    bootstrapper run --dataset financebench-mini --grid gate1
    bootstrapper run --dataset financebench-mini --grid gate1-smoke   # offline, no HF download
    bootstrapper list-runs
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from bootstrapper.config.grids import get_grid
from bootstrapper.core.embeddings import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
    SentenceTransformerProvider,
)
from bootstrapper.core.run import RunStore
from bootstrapper.core.sweep import run_sweep
from bootstrapper.datasets.base import DatasetAdapter
from bootstrapper.datasets.financebench import FinanceBenchAdapter


def _git_sha(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:  # absence of git must not block a run
        return "unknown"


def _make_adapter(dataset_id: str, data_root: Path) -> DatasetAdapter:
    if dataset_id == "financebench-mini":
        return FinanceBenchAdapter(subset="mini", data_root=data_root)
    if dataset_id == "financebench-all":
        return FinanceBenchAdapter(subset="all", data_root=data_root)
    raise SystemExit(f"unknown dataset {dataset_id!r} (try: financebench-mini, financebench-all)")


def _make_provider(embedding_id: str) -> EmbeddingProvider:
    if embedding_id == "hashing-256":
        return HashingEmbeddingProvider(dim=256)
    if embedding_id == "bge-small":
        # Lazy: imports sentence_transformers and downloads the model only when first used.
        return SentenceTransformerProvider()
    raise SystemExit(f"unknown embedding id {embedding_id!r} (try: bge-small, hashing-256)")


def _cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    grid = get_grid(args.grid)
    adapter = _make_adapter(args.dataset, Path(args.data_root))
    providers = {eid: _make_provider(eid) for eid in grid.embedding_ids}
    store = RunStore(root)
    cache_root = root / "cache" / "embeddings"

    print(f"running grid '{grid.name}' on dataset '{adapter.id}' ...", file=sys.stderr)
    result = run_sweep(
        adapter=adapter,
        grid=grid,
        providers=providers,
        store=store,
        cache_root=cache_root,
        git_sha=_git_sha(root),
        allow_unresolved=args.allow_unresolved,
        notes=args.notes,
    )
    m = result.manifest
    print(f"\nrun_id     : {m.run_id}")
    print(f"dataset    : {m.dataset_id} (labeled={m.labeled})")
    print(f"embeddings : {', '.join(m.embedding_ids)}")
    print(f"corpus     : {m.n_documents} docs, {m.n_chunks} unique chunks")
    print(f"queries    : {m.n_queries}")
    print(f"resolver   : {result.coverage.summary()}")
    print(f"artifact   : {result.run_dir}")
    if m.latency_illustrative:
        print("note       : latency is ILLUSTRATIVE on a labeled corpus (use scale corpus for real)")
    if not result.coverage.clean:
        print("WARNING    : some queries did not resolve; metrics omit them", file=sys.stderr)
    return 0


def _cmd_list_runs(args: argparse.Namespace) -> int:
    store = RunStore(Path(args.root))
    runs = store.list_runs()
    if not runs:
        print("no runs found; create one with `bootstrapper run ...`")
        return 0
    print(f"{'run_id':<22}{'dataset':<20}{'grid':<14}{'chunks':>8}{'queries':>9}{'cover':>8}")
    for m in runs:
        print(
            f"{m.run_id:<22}{m.dataset_id:<20}{m.grid.name:<14}"
            f"{m.n_chunks:>8}{m.n_queries:>9}{m.coverage:>7.0%}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bootstrapper", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="execute a sweep and freeze a run artifact")
    run_p.add_argument("--dataset", default="financebench-mini")
    run_p.add_argument("--grid", default="gate1")
    run_p.add_argument("--root", default=".", help="artifact root (runs/, snapshots/, cache/)")
    run_p.add_argument("--data-root", default="data/financebench")
    run_p.add_argument("--allow-unresolved", action="store_true")
    run_p.add_argument("--notes", default="")
    run_p.set_defaults(func=_cmd_run)

    list_p = sub.add_parser("list-runs", help="list runs in the registry")
    list_p.add_argument("--root", default=".")
    list_p.set_defaults(func=_cmd_list_runs)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = args.func
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
