"""Compute the BGC × BGC similarity matrix using a pluggable metric.

Thin wrapper around the metric callable (see ``metrics.py``). Centralised so
the orchestrator and the reclassifier go through one entry point.

Pre-filters S to columns that are present in M before delegating to the
metric — this drops the column dimension dramatically when many proteins in
the embedding table never appear inside any selected BGC.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import scipy.sparse as sp

    from discovery.services.clustering.metrics import BgcSimilarityMetric

log = logging.getLogger(__name__)


def compute_bgc_similarity(
    M: "sp.csr_matrix",
    S: "sp.csr_matrix",
    metric: "BgcSimilarityMetric",
    *,
    chunk_size: int = 2048,
    prune_below: float = 0.0,
) -> "sp.csr_matrix":
    """Run the metric on a (possibly pre-filtered) M and S.

    Parameters
    ----------
    M:
        BGC × protein 0/1 membership matrix (csr).
    S:
        Protein × protein symmetric similarity matrix already filtered at
        the metric's threshold.
    metric:
        Pluggable metric implementing ``BgcSimilarityMetric``.
    chunk_size:
        Row-block size for the M @ S computation inside the metric.
    prune_below:
        Drop entries strictly less than this value from the result. Default
        0.0 keeps everything; KNN graphs typically only need a handful of
        neighbours per BGC so a small floor (e.g. 0.05) saves memory.
    """
    if M.nnz == 0 or S.nnz == 0:
        return M  # empty similarity if either is empty

    sim = metric(M, S, chunk_size=chunk_size)

    if prune_below > 0.0 and sim.nnz:
        coo = sim.tocoo(copy=False)
        keep = coo.data >= prune_below
        if keep.sum() != coo.nnz:
            import scipy.sparse as sp

            sim = sp.csr_matrix(
                (coo.data[keep], (coo.row[keep], coo.col[keep])),
                shape=coo.shape,
            )

    log.info(
        "compute_bgc_similarity: metric=%s shape=%s nnz=%d (post-prune)",
        getattr(metric, "name", type(metric).__name__),
        sim.shape,
        sim.nnz,
    )
    # Drop the diagonal (a BGC isn't its own neighbour for clustering).
    sim.setdiag(0)
    sim.eliminate_zeros()
    # ``sim`` may be slightly asymmetric due to numerical accumulation; force
    # symmetry so KNN / Leiden see consistent edges.
    sim = sim.maximum(sim.T).tocsr()
    return sim
