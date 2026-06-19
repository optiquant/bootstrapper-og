"""Named configuration grids.

A grid is the cartesian space a run sweeps: embedding models x index families (with build and
search params) x retrievers, plus the k values and bootstrap B. Grids are pydantic models so
they serialize verbatim into every run manifest for reproducibility.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


def _default_search_params() -> list[dict[str, int]]:
    return [{}]


class IndexSpec(BaseModel):
    family: str  # "flat" | "hnsw" | (Gate 2) "ivf" | "ivfpq"
    build_params: dict[str, int] = Field(default_factory=dict)
    # One sweep point per search-param dict (e.g. several efSearch values for HNSW).
    search_params: list[dict[str, int]] = Field(default_factory=_default_search_params)

    model_config = {"frozen": True}


class GridConfig(BaseModel):
    name: str
    embedding_ids: list[str]
    chunker_id: str
    indices: list[IndexSpec]
    retrievers: list[str]
    k_values: list[int]
    bootstrap_b: int = 1000

    model_config = {"frozen": True}

    @property
    def max_k(self) -> int:
        return max(self.k_values)


# Gate 1 canonical grid: Flat + HNSW, dense retrieval, the documented bge-small default.
GATE1 = GridConfig(
    name="gate1",
    embedding_ids=["bge-small"],
    chunker_id="tokenwindow-256-32",
    indices=[
        IndexSpec(family="flat"),
        IndexSpec(
            family="hnsw",
            build_params={"M": 32, "efConstruction": 200},
            search_params=[{"efSearch": 64}],
        ),
    ],
    retrievers=["dense"],
    k_values=[1, 5, 10],
    bootstrap_b=1000,
)

# Identical sweep, but the deterministic offline encoder. Used for fully reproducible runs in
# environments without HuggingFace egress (the recall numbers reflect a crude lexical encoder,
# not bge-small -- the manifest's embedding_ids make this explicit).
GATE1_SMOKE = GATE1.model_copy(update={"name": "gate1-smoke", "embedding_ids": ["hashing-256"]})


GRIDS: dict[str, GridConfig] = {g.name: g for g in (GATE1, GATE1_SMOKE)}


def get_grid(name: str) -> GridConfig:
    if name not in GRIDS:
        raise KeyError(f"unknown grid {name!r}; available: {sorted(GRIDS)}")
    return GRIDS[name]
