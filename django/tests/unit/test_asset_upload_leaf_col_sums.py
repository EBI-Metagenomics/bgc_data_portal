"""Regression tests for the asset-upload per-leaf domain column sums.

``_project_against_run`` used to materialise a dense column-sum vector for
*every* leaf GCF of the active clustering run before scoring the upload. For
the 2026-10 prod run (57,072 leaves × 22,071 domain columns, uint64) that is
~9.4 GiB, so every asset upload OOM-killed the 2 GiB worker regardless of how
small the upload was. ``LeafColumnSums`` computes them lazily, only for the
leaves the uploaded iBGCs inherit.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from discovery.services.asset_upload.project import LeafColumnSums


def _primary():
    # 5 primary iBGCs × 4 domain columns; leaves A (rows 0,1,3), B (row 2),
    # row 4 has no leaf.
    M = sp.csr_matrix(
        np.array(
            [
                [1, 0, 1, 0],
                [1, 1, 0, 0],
                [0, 0, 0, 1],
                [0, 1, 1, 0],
                [1, 1, 1, 1],
            ],
            dtype=np.uint8,
        )
    )
    leaves = ["A", "A", "B", "A", ""]
    return M, leaves


def test_matches_dense_reference_per_leaf():
    M, leaves = _primary()
    lcs = LeafColumnSums(M, leaves)
    dense = M.toarray()
    np.testing.assert_array_equal(lcs.get("A"), dense[[0, 1, 3]].sum(axis=0))
    np.testing.assert_array_equal(lcs.get("B"), dense[[2]].sum(axis=0))


def test_unknown_or_empty_leaf_returns_none():
    M, leaves = _primary()
    lcs = LeafColumnSums(M, leaves)
    assert lcs.get("") is None
    assert lcs.get(None) is None
    assert lcs.get("no-such-leaf") is None


def test_only_requested_leaves_are_computed_and_memoised():
    """Memory must scale with leaves an upload lands in, not with the run."""
    n_leaves, n_cols = 2_000, 5_000
    rng = np.random.default_rng(0)
    rows = np.arange(n_leaves)
    cols = rng.integers(0, n_cols, size=n_leaves)
    M = sp.csr_matrix(
        (np.ones(n_leaves, dtype=np.uint8), (rows, cols)), shape=(n_leaves, n_cols)
    )
    leaves = [f"L{i}" for i in range(n_leaves)]  # one row per leaf: worst case

    lcs = LeafColumnSums(M, leaves)
    assert lcs.n_computed == 0  # nothing materialised up front

    first = lcs.get("L7")
    again = lcs.get("L7")
    lcs.get("L8")
    assert first is again  # memoised
    assert lcs.n_computed == 2
    assert first.shape == (n_cols,)
    assert first[cols[7]] == 1 and first.sum() == 1


def test_domain_novelty_lookup_shape_unchanged():
    """The caller indexes the vector with query domain columns and counts zeros."""
    M, leaves = _primary()
    col_sums = LeafColumnSums(M, leaves).get("B")
    query_domain_cols = np.array([0, 3])
    n_unique = int((col_sums[query_domain_cols] == 0).sum())
    assert n_unique == 1  # col 0 absent from leaf B, col 3 present
