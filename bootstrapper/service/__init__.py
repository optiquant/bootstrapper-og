"""HTTP service layer.

A thin FastAPI app that exposes the read-only run artifacts produced by the engine over HTTP,
so any non-Python client (a web UI, a notebook in another language, a teammate's dashboard) can
consume them without importing the SDK. Like the Streamlit app, it is **read-only**: it never
builds an index. It depends on the engine, never the reverse.

Requires the ``api`` extra::

    pip install "bootstrapper-og[api]"
    bootstrapper-api            # or: uvicorn bootstrapper.service.app:app --reload
"""
