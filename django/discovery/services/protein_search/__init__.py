"""On-disk phmmer-based protein search for the Discovery Dashboard.

The reference DB is a FASTA file (sha256-keyed) plus an Easel SSI index, stored
on the ``PROTEIN_SEARCH_INDEX_DIR`` volume so all worker pods share it.
Searches stream the FASTA in fixed-size blocks, so memory stays bounded and an
updated index is picked up by the next query. ``VERSION`` counts index builds.

Public entry points:

* :func:`discovery.services.protein_search.build.rebuild_index` —
  full FASTA rewrite from ``ContigCds``.
* :func:`discovery.services.protein_search.build.update_index` —
  append-only update for newly ingested proteins.
* :func:`discovery.services.protein_search.search.phmmer_search` —
  run phmmer with a query AA sequence; returns
  ``{sha256: ProteinHitMetrics}`` (bitscore, pident, qcoverage).
* :func:`discovery.services.protein_search.index.iter_index_blocks` —
  stream the index as ``DigitalSequenceBlock``s.
"""

from .build import index_paths, rebuild_index, update_index
from .index import iter_index_blocks
from .search import ProteinHitMetrics, phmmer_search

__all__ = [
    "rebuild_index",
    "update_index",
    "index_paths",
    "iter_index_blocks",
    "phmmer_search",
    "ProteinHitMetrics",
]
