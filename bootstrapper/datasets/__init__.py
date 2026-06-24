"""Dataset adapters.

The engine is dataset-agnostic; everything dataset-specific lives behind the
:class:`DatasetAdapter` protocol. :class:`Document`, :class:`Evidence` and :class:`Query` are
the dataclasses an adapter yields. FinanceBench is the first loaded dataset.
"""

from bootstrapper.datasets.base import DatasetAdapter, Document, Evidence, Query
from bootstrapper.datasets.financebench import FinanceBenchAdapter
from bootstrapper.datasets.folder import LocalFolderAdapter

__all__ = [
    "DatasetAdapter",
    "Document",
    "Evidence",
    "FinanceBenchAdapter",
    "LocalFolderAdapter",
    "Query",
]
