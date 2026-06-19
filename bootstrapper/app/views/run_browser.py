"""Run Browser tab: list runs and inspect a run's manifest."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from bootstrapper.core.run import RunManifest, RunStore

_EMPTY_HINT = (
    "No runs found. Create one offline with:\n\n"
    "```\nbootstrapper run --dataset financebench-mini --grid gate1-smoke\n```"
)


def render(store: RunStore, runs: list[RunManifest]) -> None:
    st.subheader("Run Browser")
    if not runs:
        st.info(_EMPTY_HINT)
        return

    summary = pd.DataFrame(
        [
            {
                "run_id": m.run_id,
                "dataset": m.dataset_id,
                "grid": m.grid.name,
                "embeddings": ", ".join(m.embedding_ids),
                "docs": m.n_documents,
                "chunks": m.n_chunks,
                "queries": m.n_queries,
                "coverage": m.coverage,
                "created_at": m.created_at,
            }
            for m in runs
        ]
    )
    st.dataframe(
        summary,
        hide_index=True,
        width="stretch",
        column_config={"coverage": st.column_config.NumberColumn(format="%.0f%%")},
    )

    run_ids = [m.run_id for m in runs]
    selected = st.selectbox("Inspect run", run_ids, key="rb_run")
    manifest = next(m for m in runs if m.run_id == selected)

    col1, col2, col3 = st.columns(3)
    col1.metric("Documents", manifest.n_documents)
    col1.metric("Unique chunks", manifest.n_chunks)
    col2.metric("Queries", manifest.n_queries)
    col2.metric("Resolver coverage", f"{manifest.coverage:.0%}")
    col3.metric("Mean gold / query", f"{manifest.mean_gold_per_query:.2f}")
    col3.metric("Bootstrap B", manifest.bootstrap_b)

    if manifest.coverage < 1.0:
        st.warning(
            "Resolver coverage < 100%: some queries did not resolve to a gold chunk and were "
            "omitted from metrics. That measures the resolver, not the index."
        )
    if manifest.latency_illustrative:
        st.info(
            "This is a **labeled** corpus, so latency here is *illustrative only* — at small "
            "vector counts every index family returns in microseconds. Latency/memory are "
            "measured on the scale corpus (Gate 2)."
        )

    st.markdown("**Provenance**")
    st.write(
        {
            "dataset_id": manifest.dataset_id,
            "labeled": manifest.labeled,
            "chunker_id": manifest.chunker_id,
            "embedding_ids": manifest.embedding_ids,
            "k_values": manifest.k_values,
            "git_sha": manifest.git_sha,
            "created_at": manifest.created_at,
            "notes": manifest.notes or "(none)",
        }
    )

    st.markdown("**Config grid**")
    grid_rows = [
        {
            "family": spec.family,
            "build_params": json.dumps(spec.build_params),
            "search_params": json.dumps(spec.search_params),
        }
        for spec in manifest.grid.indices
    ]
    st.dataframe(pd.DataFrame(grid_rows), hide_index=True, width="stretch")
    st.caption(f"retrievers: {', '.join(manifest.grid.retrievers)}")
