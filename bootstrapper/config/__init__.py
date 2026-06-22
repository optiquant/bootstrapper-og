"""Named configuration grids.

A :class:`GridConfig` names a (chunker, embeddings, index families, search params, retrievers)
sweep. :func:`get_grid` resolves a built-in grid by name (e.g. ``"gate1"``, ``"gate1-smoke"``).
"""

from bootstrapper.config.grids import GridConfig, IndexSpec, get_grid

__all__ = [
    "GridConfig",
    "IndexSpec",
    "get_grid",
]
