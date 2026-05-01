"""Pair-based hierarchical Leiden clustering for BGCs.

Public API surface for the discovery clustering pipeline. Heavy imports
(numpy, scipy.sparse, igraph, leidenalg, umap-learn) are deferred inside
the individual modules' function bodies so this package can be imported on
the web container without any ML dependencies installed.

See ``services/clustering/pipeline.py`` for the orchestrator and
``services/clustering/reclassify.py`` for the post-hoc step.
"""

from discovery.services.clustering.metrics import (
    BgcSimilarityMetric,
    JaccardSimilarity,
    OverlapSimilarity,
    SorensenDiceSimilarity,
    get_metric,
)
from discovery.services.clustering.pipeline import (
    DEFAULT_RESOLUTIONS,
    run_clustering_pipeline,
)
from discovery.services.clustering.reclassify import (
    ALLOWED_SCOPES,
    SCOPE_ALL_NON_PRIMARY,
    SCOPE_PARTIAL,
    SCOPE_STALE,
    reclassify_bgcs,
)
from discovery.services.clustering.pairs import build_protein_similar_pairs

__all__ = [
    "BgcSimilarityMetric",
    "SorensenDiceSimilarity",
    "JaccardSimilarity",
    "OverlapSimilarity",
    "get_metric",
    "DEFAULT_RESOLUTIONS",
    "run_clustering_pipeline",
    "build_protein_similar_pairs",
    "reclassify_bgcs",
    "ALLOWED_SCOPES",
    "SCOPE_PARTIAL",
    "SCOPE_STALE",
    "SCOPE_ALL_NON_PRIMARY",
]
