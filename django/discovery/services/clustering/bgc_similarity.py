"""Composite weighted-mean BGC × BGC similarity.

The composite score is ``w_d · S(M_domains) + w_a · S(M_pairs)`` where ``S``
is the run's ``similarity_metric`` (ADR 0003):

* ``"dice"`` — Sørensen–Dice on the binary rows (computed here, unchanged so
  older runs score exactly as they always have);
* ``"cosine_idf_enrich"`` — weighted cosine ``X Xᵀ`` with
  ``X = rownorm(M · diag(w))`` and the run's per-feature weights; delegated to
  :mod:`common_core.clustering.similarity`, the implementation the HPC job uses.

and:

* ``M_domains`` is the iBGC × domain-accession binary matrix.
* ``M_pairs``   is the iBGC × adjacent-pair binary matrix.

Both matrices share row ordering, so the two Dice scores are sparse matrices
of identical shape and can be summed directly. The result is symmetrized and
its diagonal zeroed so KNN / Leiden see clean edges.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import scipy.sparse as sp

from discovery.services.clustering.metrics import dice_block, dice_similarity

log = logging.getLogger(__name__)


def compute_composite_similarity(
    M_domains: sp.csr_matrix,
    M_pairs: sp.csr_matrix,
    *,
    weights: tuple[float, float] = (0.5, 0.5),
    prune_below: float = 0.0,
    metric: str = "dice",
    domain_weights: np.ndarray | None = None,
    pair_weights: np.ndarray | None = None,
) -> sp.csr_matrix:
    """Return the weighted-mean composite similarity on two binary matrices.

    Parameters
    ----------
    M_domains : sparse CSR, shape (n_rows, n_domains)
    M_pairs   : sparse CSR, shape (n_rows, n_pairs)
    weights   : (w_domain, w_adjacency); weights are renormalized to sum 1.0
                so the output range stays in [0, 1] even if the caller
                supplies un-normalized weights.
    prune_below: drop entries strictly less than this value from the result.
    metric, domain_weights, pair_weights:
                ``"dice"`` (default) or ``"cosine_idf_enrich"`` with the run's
                per-feature weights aligned to the matrix columns.

    Returns
    -------
    sparse CSR symmetric iBGC × iBGC similarity, diagonal zeroed.
    """
    import scipy.sparse as sp

    if metric != "dice":
        from common_core.clustering.similarity import (
            compute_composite_similarity as compute_weighted,
        )

        return compute_weighted(
            M_domains,
            M_pairs,
            weights=weights,
            prune_below=prune_below,
            metric=metric,
            domain_weights=domain_weights,
            pair_weights=pair_weights,
        )

    if M_domains.shape[0] != M_pairs.shape[0]:
        raise ValueError(
            f"row mismatch: M_domains={M_domains.shape}, M_pairs={M_pairs.shape}"
        )

    w_d, w_a = weights
    total = float(w_d) + float(w_a)
    if total <= 0:
        raise ValueError(f"weights must sum > 0, got {weights}")
    w_d, w_a = w_d / total, w_a / total

    sim_d = dice_similarity(M_domains) if w_d > 0 else None
    sim_a = dice_similarity(M_pairs) if w_a > 0 else None

    if sim_d is not None and sim_a is not None:
        sim = (w_d * sim_d) + (w_a * sim_a)
    elif sim_d is not None:
        sim = w_d * sim_d
    elif sim_a is not None:
        sim = w_a * sim_a
    else:  # both weights zero — unreachable due to total>0 guard
        raise RuntimeError("composite similarity has no contributing components")

    sim = sim.tocsr()

    if prune_below > 0.0 and sim.nnz:
        coo = sim.tocoo(copy=False)
        keep = coo.data >= prune_below
        if keep.sum() != coo.nnz:
            sim = sp.csr_matrix(
                (coo.data[keep], (coo.row[keep], coo.col[keep])),
                shape=coo.shape,
            )

    # BGC isn't its own neighbour.
    sim.setdiag(0)
    sim.eliminate_zeros()
    # Force symmetry; tiny floating drift from the matmul can leak otherwise.
    sim = sim.maximum(sim.T).tocsr()

    log.info(
        "compute_composite_similarity: shape=%s nnz=%d weights=(%.3f, %.3f)",
        sim.shape,
        sim.nnz,
        w_d,
        w_a,
    )
    return sim


def compute_composite_similarity_block(
    M_dom_query: sp.csr_matrix,
    M_dom_ref: sp.csr_matrix,
    M_pair_query: sp.csr_matrix,
    M_pair_ref: sp.csr_matrix,
    *,
    weights: tuple[float, float] = (0.5, 0.5),
    metric: str = "dice",
    domain_weights: np.ndarray | None = None,
    pair_weights: np.ndarray | None = None,
) -> sp.csr_matrix:
    """Composite weighted-mean similarity of query rows vs. reference rows only.

    Equivalent to the ``[n_ref:, :n_ref]`` block of::

        compute_composite_similarity(
            vstack([M_dom_ref, M_dom_query]),
            vstack([M_pair_ref, M_pair_query]),
            weights=weights,
        )

    but computed directly as ``(n_query, n_ref)`` Dice blocks, so the cost is
    proportional to the (small) query set rather than the (large) reference
    set squared. The diagonal-zeroing / symmetrisation that
    ``compute_composite_similarity`` applies do not affect this off-diagonal
    block (query and reference rows are disjoint, and the closed-form Dice is
    already symmetric), so the two paths agree to float tolerance. The same
    holds for ``metric="cosine_idf_enrich"``, whose block is
    ``rownorm(Q·diag(w)) · rownorm(R·diag(w))ᵀ``.

    Returns a ``(n_query, n_ref)`` CSR matrix.
    """
    if M_dom_query.shape[0] != M_pair_query.shape[0]:
        raise ValueError(
            f"query row mismatch: M_dom_query={M_dom_query.shape}, "
            f"M_pair_query={M_pair_query.shape}"
        )
    if M_dom_ref.shape[0] != M_pair_ref.shape[0]:
        raise ValueError(
            f"ref row mismatch: M_dom_ref={M_dom_ref.shape}, "
            f"M_pair_ref={M_pair_ref.shape}"
        )

    w_d, w_a = weights
    total = float(w_d) + float(w_a)
    if total <= 0:
        raise ValueError(f"weights must sum > 0, got {weights}")
    w_d, w_a = w_d / total, w_a / total

    if metric == "dice":
        sim_d = dice_block(M_dom_query, M_dom_ref) if w_d > 0 else None
        sim_a = dice_block(M_pair_query, M_pair_ref) if w_a > 0 else None
    else:
        from common_core.clustering.similarity import check_metric

        check_metric(metric, M_dom_ref, M_pair_ref, domain_weights, pair_weights)
        sim_d = (
            weighted_cosine_block(M_dom_query, M_dom_ref, domain_weights)
            if w_d > 0
            else None
        )
        sim_a = (
            weighted_cosine_block(M_pair_query, M_pair_ref, pair_weights)
            if w_a > 0
            else None
        )

    if sim_d is not None and sim_a is not None:
        sim = (w_d * sim_d) + (w_a * sim_a)
    elif sim_d is not None:
        sim = w_d * sim_d
    elif sim_a is not None:
        sim = w_a * sim_a
    else:  # unreachable due to total>0 guard
        raise RuntimeError("composite similarity has no contributing components")

    sim = sim.tocsr()
    log.info(
        "compute_composite_similarity_block: metric=%s shape=%s nnz=%d "
        "weights=(%.3f, %.3f)",
        metric,
        sim.shape,
        sim.nnz,
        w_d,
        w_a,
    )
    return sim


def weighted_cosine_block(
    M_query: sp.csr_matrix, M_ref: sp.csr_matrix, w: np.ndarray
) -> sp.csr_matrix:
    """``(n_query, n_ref)`` weighted cosine, clipped to 1.0 like the full matrix."""
    import numpy as np
    from common_core.clustering.similarity import weighted_rows

    sim = (weighted_rows(M_query, w) @ weighted_rows(M_ref, w).T).tocsr()
    sim = sim.astype(np.float32)
    np.minimum(sim.data, 1.0, out=sim.data)
    sim.eliminate_zeros()
    return sim
