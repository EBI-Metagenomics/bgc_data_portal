"""Pluggable BGC × BGC similarity metrics.

A metric takes:
    M : sparse (n_bgcs, n_proteins) 0/1 BGC-protein membership matrix
    S : sparse (n_proteins, n_proteins) symmetric protein-similarity matrix
        already filtered to ``cosine >= threshold`` (with 1.0 on the diagonal
        so a protein self-matches; this is what makes shared-protein BGCs
        contribute to the "shared" count).

and returns a sparse symmetric BGC × BGC similarity matrix in [0, 1].

Switching the metric used by the pipeline is one class swap — see
``compute_bgc_similarity`` in ``bgc_similarity.py``.

Heavy imports (numpy, scipy.sparse) are deferred inside function bodies so
this module can be imported on the web container without ML dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import scipy.sparse as sp


# ── Protocol ────────────────────────────────────────────────────────────────


@runtime_checkable
class BgcSimilarityMetric(Protocol):
    """A pluggable BGC × BGC similarity metric.

    Implementations operate purely on sparse matrices so they're cheap to
    test in isolation and have no side-effects.
    """

    name: str

    def __call__(
        self,
        M: "sp.csr_matrix",
        S: "sp.csr_matrix",
        *,
        chunk_size: int = 2048,
    ) -> "sp.csr_matrix":
        ...


# ── Helpers shared across metrics ───────────────────────────────────────────


def _binarize(matrix: "sp.csr_matrix") -> "sp.csr_matrix":
    """Return a sparse uint8 matrix with the same shape, 1 wherever input > 0."""
    import numpy as np
    import scipy.sparse as sp

    coo = matrix.tocoo(copy=False)
    data = (coo.data > 0).astype(np.uint8)
    keep = data.astype(bool)
    return sp.csr_matrix(
        (data[keep], (coo.row[keep], coo.col[keep])),
        shape=coo.shape,
    )


def _build_T(M: "sp.csr_matrix", S: "sp.csr_matrix", *, chunk_size: int) -> "sp.csr_matrix":
    """Compute T[b, p] = 1 iff BGC b contains some protein with cos(p, q) >= threshold.

    Computed in row-blocks of M to keep peak memory bounded on large inputs.
    """
    import numpy as np
    import scipy.sparse as sp

    n_bgcs, _ = M.shape
    blocks: list[sp.csr_matrix] = []
    for start in range(0, n_bgcs, chunk_size):
        block = M[start : start + chunk_size]
        T_full = block @ S
        blocks.append(_binarize(T_full))
    if not blocks:
        return sp.csr_matrix((0, S.shape[1]), dtype=np.uint8)
    return sp.vstack(blocks, format="csr")


def _safe_divide(numer: "sp.coo_matrix", sizes: "any") -> "sp.csr_matrix":
    """Element-wise: numer[a, b] / (sizes[a] + sizes[b]); zero rows/cols stay zero."""
    import numpy as np
    import scipy.sparse as sp

    coo = numer.tocoo(copy=False)
    denom = sizes[coo.row] + sizes[coo.col]
    safe = denom > 0
    data = np.zeros_like(coo.data, dtype=np.float64)
    data[safe] = coo.data[safe] / denom[safe]
    return sp.csr_matrix(
        (data, (coo.row, coo.col)),
        shape=coo.shape,
    )


# ── Sørensen–Dice (asymmetric count) ────────────────────────────────────────


class SorensenDiceSimilarity:
    """BGC × BGC Sørensen–Dice similarity using protein-level matches.

    Numerator (the "shared" count) is the **asymmetric average** the user
    chose: count proteins in A that have *any* partner in B at cosine ≥
    threshold, count proteins in B that have any partner in A, average the
    two::

        shared_a(A,B) = #{p in A : exists q in B with cos(p,q) >= threshold}
        shared_b(A,B) = #{q in B : exists p in A with cos(p,q) >= threshold}
        shared       = (shared_a + shared_b) / 2
        dice(A,B)    = 2 * shared / (|A| + |B|)

    The diagonal of S (self-pairs at 1.0) is what makes a BGC pair sharing
    the same protein contribute correctly to ``shared`` without any duplicate
    pair-table work.
    """

    name = "dice"

    def __init__(self, threshold: float):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {threshold}")
        self.threshold = float(threshold)

    def __call__(
        self,
        M: "sp.csr_matrix",
        S: "sp.csr_matrix",
        *,
        chunk_size: int = 2048,
    ) -> "sp.csr_matrix":
        import numpy as np
        import scipy.sparse as sp

        T = _build_T(M, S, chunk_size=chunk_size)

        # X[a, b] = #{p in A: p has a partner in B} = shared_a(A → B)
        X = (M @ T.T).tocoo(copy=False)
        # shared = (X + X.T) / 2
        shared_data = (X.data * 0.5).astype(np.float64)
        shared_half = sp.csr_matrix(
            (shared_data, (X.row, X.col)),
            shape=X.shape,
        )
        shared = shared_half + shared_half.T

        sizes = np.asarray(M.sum(axis=1)).ravel()
        # Numerator * 2 / (|A| + |B|)  →  multiply data by 2 in-place.
        coo = shared.tocoo(copy=False)
        coo.data *= 2.0
        return _safe_divide(coo, sizes)


# ── Jaccard ─────────────────────────────────────────────────────────────────


class JaccardSimilarity:
    """BGC × BGC Jaccard similarity using the same asymmetric-shared count.

    ``jaccard(A,B) = shared / (|A| + |B| - shared)``.
    """

    name = "jaccard"

    def __init__(self, threshold: float):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {threshold}")
        self.threshold = float(threshold)

    def __call__(
        self,
        M: "sp.csr_matrix",
        S: "sp.csr_matrix",
        *,
        chunk_size: int = 2048,
    ) -> "sp.csr_matrix":
        import numpy as np
        import scipy.sparse as sp

        T = _build_T(M, S, chunk_size=chunk_size)
        X = (M @ T.T).tocoo(copy=False)
        shared_data = (X.data * 0.5).astype(np.float64)
        shared_half = sp.csr_matrix(
            (shared_data, (X.row, X.col)),
            shape=X.shape,
        )
        shared = shared_half + shared_half.T

        sizes = np.asarray(M.sum(axis=1)).ravel()
        coo = shared.tocoo(copy=False)
        denom = sizes[coo.row] + sizes[coo.col] - coo.data
        safe = denom > 0
        data = np.zeros_like(coo.data, dtype=np.float64)
        data[safe] = coo.data[safe] / denom[safe]
        return sp.csr_matrix(
            (data, (coo.row, coo.col)),
            shape=coo.shape,
        )


# ── Overlap coefficient ─────────────────────────────────────────────────────


class OverlapSimilarity:
    """BGC × BGC overlap coefficient (Szymkiewicz–Simpson) using shared count.

    ``overlap(A,B) = shared / min(|A|, |B|)``.
    """

    name = "overlap"

    def __init__(self, threshold: float):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {threshold}")
        self.threshold = float(threshold)

    def __call__(
        self,
        M: "sp.csr_matrix",
        S: "sp.csr_matrix",
        *,
        chunk_size: int = 2048,
    ) -> "sp.csr_matrix":
        import numpy as np
        import scipy.sparse as sp

        T = _build_T(M, S, chunk_size=chunk_size)
        X = (M @ T.T).tocoo(copy=False)
        shared_data = (X.data * 0.5).astype(np.float64)
        shared_half = sp.csr_matrix(
            (shared_data, (X.row, X.col)),
            shape=X.shape,
        )
        shared = shared_half + shared_half.T

        sizes = np.asarray(M.sum(axis=1)).ravel()
        coo = shared.tocoo(copy=False)
        denom = np.minimum(sizes[coo.row], sizes[coo.col])
        safe = denom > 0
        data = np.zeros_like(coo.data, dtype=np.float64)
        data[safe] = coo.data[safe] / denom[safe]
        return sp.csr_matrix(
            (data, (coo.row, coo.col)),
            shape=coo.shape,
        )


# ── Lookup ──────────────────────────────────────────────────────────────────


_REGISTRY: dict[str, type] = {
    "dice": SorensenDiceSimilarity,
    "jaccard": JaccardSimilarity,
    "overlap": OverlapSimilarity,
}


def get_metric(name: str, threshold: float) -> BgcSimilarityMetric:
    """Resolve a metric name (``dice``, ``jaccard``, ``overlap``) to an instance."""
    try:
        cls = _REGISTRY[name]
    except KeyError as exc:
        raise ValueError(
            f"unknown metric {name!r}; available: {sorted(_REGISTRY)}"
        ) from exc
    return cls(threshold=threshold)
