"""Streamlit entrypoint.

Read-only. Imports only run artifacts and pure-numpy helpers -- never faiss, embeddings or the
sweep. Gate 1 ships the Run Browser and Compare tabs; Drill-down (Gate 2) and Learn (Gate 4)
join them later.

Run with:  streamlit run bootstrapper/app/streamlit_app.py
Point at artifacts via the BOOTSTRAPPER_ROOT env var (defaults to the current directory).
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from bootstrapper.app.views import compare, run_browser
from bootstrapper.core.run import RunStore


def main() -> None:
    st.set_page_config(page_title="bootstrapper-og", layout="wide")
    st.title("bootstrapper-og")
    st.caption(
        "Auditable ANN retrieval-evaluation harness. Read-only browser over precomputed runs. "
        "Perpetual beta."
    )

    root = Path(os.environ.get("BOOTSTRAPPER_ROOT", "."))
    store = RunStore(root)
    runs = store.list_runs()

    tab_browser, tab_compare = st.tabs(["Run Browser", "Compare"])
    with tab_browser:
        run_browser.render(store, runs)
    with tab_compare:
        compare.render(store, runs)


main()
