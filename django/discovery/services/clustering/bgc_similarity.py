"""Composite weighted-mean BGC × BGC similarity.

The composite score is ``w_d · Dice(M_domains) + w_a · Dice(M_pairs)`` where:

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
    import scipy.sparse as sp

from discovery.services.clustering.metrics import dice_block, dice_similarity

log = logging.getLogger(__name__)


def compute_composite_similarity(
    M_domains: sp.csr_matrix,
    M_pairs: sp.csr_matrix,
    *,
    weights: tuple[float, float] = (0.5, 0.5),
    prune_below: float = 0.0,
) -> sp.csr_matrix:
    """Return weighted-mean Sørensen–Dice similarity on two binary matrices.

    Parameters
    ----------
    M_domains : sparse CSR, shape (n_rows, n_domains)
    M_pairs   : sparse CSR, shape (n_rows, n_pairs)
    weights   : (w_domain, w_adjacency); weights are renormalized to sum 1.0
                so the output range stays in [0, 1] even if the caller
                supplies un-normalized weights.
    prune_below: drop entries strictly less than this value from the result.

    Returns
    -------
    sparse CSR symmetric iBGC × iBGC similarity, diagonal zeroed.
    """
    import scipy.sparse as sp

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
) -> sp.csr_matrix:
    """Composite weighted-mean Dice of query rows vs. reference rows only.

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
    already symmetric), so the two paths agree to float tolerance.

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

    sim_d = dice_block(M_dom_query, M_dom_ref) if w_d > 0 else None
    sim_a = dice_block(M_pair_query, M_pair_ref) if w_a > 0 else None

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
        "compute_composite_similarity_block: shape=%s nnz=%d weights=(%.3f, %.3f)",
        sim.shape,
        sim.nnz,
        w_d,
        w_a,
    )
    return sim
