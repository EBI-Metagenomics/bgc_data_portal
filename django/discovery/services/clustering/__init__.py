"""iBGC similarity, scoring and GCF membership helpers.

Clustering runs on the HPC (``bgc-cluster`` in common-core); the portal
exports the inputs (``export_clustering_inputs``), imports the results
(``import_clustering_results``) and scores iBGCs against the active run
(ADR 0003: IDF x enrichment weighted cosine, or composite Dice for older runs).
Heavy imports (numpy, scipy.sparse) are deferred inside function bodies so the
package imports on the web container without the science stack.
"""

from discovery.services.clustering.integrated import build_integrated_bgcs
from discovery.services.clustering.reclassify import (
    ALLOWED_SCOPES,
    SCOPE_ALL_NON_PRIMARY,
    SCOPE_PARTIAL,
    SCOPE_STALE,
    reclassify_bgcs,
)

__all__ = [
    "build_integrated_bgcs",
    "reclassify_bgcs",
    "ALLOWED_SCOPES",
    "SCOPE_PARTIAL",
    "SCOPE_STALE",
    "SCOPE_ALL_NON_PRIMARY",
]
