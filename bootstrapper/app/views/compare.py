"""Compare tab: aggregate per-config metrics with bootstrap CIs over the same parquet.

Real and synthetic ground truth are sliced separately and never pooled. The bootstrap CI is
recomputed here from the per-query rows (B from the manifest), so the slider/selection always
reflects the operator's own measured data.
"""

from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from bootstrapper.core.metrics import bootstrap_ci
from bootstrapper.core.run import RunManifest, RunStore


def _config_label(embedding_id: str, family: str, search_params_json: str) -> str:
    params = json.loads(search_params_json) if search_params_json else {}
    suffix = ""
    if params:
        suffix = " (" + ", ".join(f"{k}={v}" for k, v in sorted(params.items())) + ")"
    return f"{embedding_id} · {family}{suffix}"


def _aggregate(df: pd.DataFrame, b: int) -> pd.DataFrame:
    group_cols = ["config_id", "embedding_id", "index_family", "search_params", "k", "metric_name"]
    rows: list[dict[str, object]] = []
    for keys, grp in df.groupby(group_cols, sort=True):
        config_id, embedding_id, family, search_params, k, metric_name = keys
        values = grp["metric_value"].to_numpy(dtype=float)
        mean, lo, hi = bootstrap_ci(values, b=b)
        rows.append(
            {
                "config": _config_label(str(embedding_id), str(family), str(search_params)),
                "config_id": config_id,
                "family": family,
                "k": int(k),
                "metric_name": metric_name,
                "mean": mean,
                "lo": lo,
                "hi": hi,
                "err_hi": hi - mean,
                "err_lo": mean - lo,
                "n": len(values),
            }
        )
    return pd.DataFrame(rows)


def _resource_table(df: pd.DataFrame) -> pd.DataFrame:
    res = (
        df.groupby(["config_id", "embedding_id", "index_family", "search_params"], sort=True)
        .agg(
            build_time_s=("build_time_s", "first"),
            memory_bytes=("memory_bytes", "first"),
            latency_ms_p50=("latency_ms", "median"),
            latency_ms_p95=("latency_ms", lambda s: s.quantile(0.95)),
        )
        .reset_index()
    )
    res["config"] = [
        _config_label(e, f, s)
        for e, f, s in zip(
            res["embedding_id"], res["index_family"], res["search_params"], strict=True
        )
    ]
    res["memory_MB"] = res["memory_bytes"] / 1e6
    return res


def render(store: RunStore, runs: list[RunManifest]) -> None:
    st.subheader("Compare")
    if not runs:
        st.info("No runs to compare yet.")
        return

    run_ids = [m.run_id for m in runs]
    selected = st.selectbox("Run", run_ids, key="cmp_run")
    manifest = next(m for m in runs if m.run_id == selected)
    df = store.load_metrics(selected)

    sources = sorted(df["gt_source"].unique())
    if len(sources) > 1:
        src = st.radio("Ground-truth slice", sources, horizontal=True, key="cmp_src")
    else:
        src = sources[0]
        st.caption(f"ground-truth slice: **{src}** (the only slice in this run)")
    df = df[df["gt_source"] == src].copy()

    agg = _aggregate(df, manifest.bootstrap_b)
    n_queries = int(agg["n"].max()) if not agg.empty else 0

    metric = st.selectbox("Metric", ["recall", "ndcg", "mrr"], index=0, key="cmp_metric")
    sub = agg[agg["metric_name"] == metric].copy()
    sub["k"] = sub["k"].astype(str)

    fig = px.bar(
        sub,
        x="config",
        y="mean",
        color="k",
        barmode="group",
        error_y="err_hi",
        error_y_minus="err_lo",
        labels={"mean": f"{metric}@k", "config": "configuration", "k": "k"},
        title=(
            f"{metric}@k by configuration — mean ± 95% bootstrap CI "
            f"(B={manifest.bootstrap_b}, n={n_queries} queries)"
        ),
    )
    fig.update_yaxes(range=[0, 1.05])
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Flat is exact (recall@k = 1.0 by construction) — the baseline every approximate index "
        "is measured against. With few queries CIs are wide; trust frontier shape over absolute "
        "deltas."
    )

    st.markdown("**Metric detail** (mean [lo, hi])")
    detail = agg.copy()
    detail["value"] = detail.apply(
        lambda r: f"{r['mean']:.3f} [{r['lo']:.3f}, {r['hi']:.3f}]", axis=1
    )
    pivot = detail.pivot_table(
        index=["config", "metric_name"], columns="k", values="value", aggfunc="first"
    )
    st.dataframe(pivot, width="stretch")

    st.markdown("**Resources per configuration**")
    res = _resource_table(df)
    st.dataframe(
        res[["config", "build_time_s", "memory_MB", "latency_ms_p50", "latency_ms_p95"]],
        hide_index=True,
        width="stretch",
        column_config={
            "build_time_s": st.column_config.NumberColumn(format="%.4f s"),
            "memory_MB": st.column_config.NumberColumn(format="%.2f MB"),
            "latency_ms_p50": st.column_config.NumberColumn("latency p50 (ms)", format="%.3f"),
            "latency_ms_p95": st.column_config.NumberColumn("latency p95 (ms)", format="%.3f"),
        },
    )
    if manifest.latency_illustrative:
        st.caption(
            "⚠️ Latency is **illustrative** on this labeled corpus. The recall/latency/memory "
            "frontier is measured on the scale corpus (Gate 2)."
        )
