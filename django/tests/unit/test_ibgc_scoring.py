"""Pure-array tests for ``compute_novelty_array`` and ``compute_domain_novelty_array``.

Exercises the math on small synthetic matrices without touching the DB.
The DB-writing path (``score_primary_ibgcs``) is covered by an integration
test that runs the full pipeline; here we just lock the formulas in place.
"""

from __future__ import annotations

import numpy as np
import pytest

scipy_sparse = pytest.importorskip("scipy.sparse")

from discovery.services.clustering.ibgc_scoring import (  # noqa: E402
    compute_domain_novelty_array,
    compute_novelty_against_validated,
    compute_novelty_array,
)


def _zeros(n: int) -> "scipy_sparse.csr_matrix":
    """An all-zero pairs matrix, to isolate the domain component (w_a=0)."""
    return scipy_sparse.csr_matrix((n, 1), dtype=np.uint8)


def _coo(rows: list[list[int]], n_cols: int) -> "scipy_sparse.csr_matrix":
    coords_r: list[int] = []
    coords_c: list[int] = []
    for r, cols in enumerate(rows):
        for c in cols:
            coords_r.append(r)
            coords_c.append(c)
    data = np.ones(len(coords_r), dtype=np.uint8)
    return scipy_sparse.csr_matrix(
        (data, (coords_r, coords_c)),
        shape=(len(rows), n_cols),
        dtype=np.uint8,
    )


def _sym_sim(values: dict[tuple[int, int], float], n: int) -> "scipy_sparse.csr_matrix":
    """Build a symmetric float similarity from upper-triangle entries."""
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for (i, j), v in values.items():
        rows += [i, j]
        cols += [j, i]
        data += [v, v]
    return scipy_sparse.csr_matrix(
        (data, (rows, cols)), shape=(n, n), dtype=np.float32
    )


# ── novelty (deprecated compute_novelty_array — reuses the clustering sim) ─
# These lock the *old* math of the retained-for-compat helper; the corrected
# behaviour lives in the compute_novelty_against_validated tests below.


def test_novelty_no_validated_columns_returns_nans():
    sim = _sym_sim({(0, 1): 0.4, (0, 2): 0.2, (1, 2): 0.9}, n=3)
    out = compute_novelty_array(sim, validated_cols=[])
    assert out.shape == (3,)
    assert np.all(np.isnan(out))


def test_novelty_uses_max_sim_to_validated_column():
    # rows 0,1 are queries; column 2 is the only validated iBGC.
    sim = _sym_sim({(0, 2): 0.7, (1, 2): 0.2, (0, 1): 0.95}, n=3)
    out = compute_novelty_array(sim, validated_cols=[2])
    # novelty(0) = 1 - 0.7 = 0.3   (sim(0,1) is irrelevant; col 1 not validated)
    # novelty(1) = 1 - 0.2 = 0.8
    # novelty(2) = 1 - 0   = 1.0   (diagonal zero, no other validated)
    assert out[0] == pytest.approx(0.3, abs=1e-6)
    assert out[1] == pytest.approx(0.8, abs=1e-6)
    assert out[2] == pytest.approx(1.0, abs=1e-6)


def test_novelty_validated_vs_other_validated_uses_diagonal_zero():
    sim = _sym_sim({(0, 1): 0.6, (0, 2): 0.1, (1, 2): 0.4}, n=3)
    # rows 0 and 1 are both validated; row 0's novelty must come from sim(0,1).
    out = compute_novelty_array(sim, validated_cols=[0, 1])
    assert out[0] == pytest.approx(1.0 - 0.6, abs=1e-6)
    assert out[1] == pytest.approx(1.0 - 0.6, abs=1e-6)
    assert out[2] == pytest.approx(1.0 - 0.4, abs=1e-6)


# ── novelty against validated (decoupled, diagonal-intact) ────────────────


def test_validated_against_validated_block_no_validated_returns_nan():
    M = _coo([[0, 1], [1, 2]], n_cols=3)
    out = compute_novelty_against_validated(M, _zeros(2), [], weights=(1.0, 0.0))
    assert out.shape == (2,)
    assert np.all(np.isnan(out))


def test_validated_row_is_zero_even_with_no_similar_validated_neighbour():
    # Regression: the bug gave such a row novelty 1.0 because the clustering
    # sim matrix zeroes the diagonal, dropping its self-match.
    #   row 0: validated, domains {0,1}
    #   row 1: non-validated, domains {2,3} (no overlap with row 0)
    M = _coo([[0, 1], [2, 3]], n_cols=4)
    out = compute_novelty_against_validated(M, _zeros(2), [0], weights=(1.0, 0.0))
    assert out[0] == pytest.approx(0.0, abs=1e-6)   # self-match → not novel
    assert out[1] == pytest.approx(1.0, abs=1e-6)   # genuinely novel


def test_validated_self_match_beats_partial_overlap():
    #   row 0: domains {0,1}            (identical to validated row 2)
    #   row 1: domains {1,2}            (half-overlap with row 2)
    #   row 2: validated, domains {0,1}
    M = _coo([[0, 1], [1, 2], [0, 1]], n_cols=3)
    out = compute_novelty_against_validated(M, _zeros(3), [2], weights=(1.0, 0.0))
    assert out[0] == pytest.approx(0.0, abs=1e-6)   # Dice(=1.0) → novelty 0
    assert out[1] == pytest.approx(0.5, abs=1e-6)   # Dice 0.5  → novelty 0.5
    assert out[2] == pytest.approx(0.0, abs=1e-6)   # validated self → 0


def test_near_threshold_similarity_is_not_pruned():
    # Regression: with the old pruned (>=0.05) clustering matrix this edge
    # would vanish and the row would read novelty 1.0. The decoupled block is
    # unpruned, so the true 0.033 similarity survives.
    #   row 0: validated, 30 domains {0..29}
    #   row 1: 30 domains {29..58} — overlap is exactly {29}: Dice = 2/60 ≈ 0.033
    M = _coo([list(range(0, 30)), list(range(29, 59))], n_cols=59)
    out = compute_novelty_against_validated(M, _zeros(2), [0], weights=(1.0, 0.0))
    assert out[0] == pytest.approx(0.0, abs=1e-6)
    assert out[1] == pytest.approx(1.0 - (2.0 / 60.0), abs=1e-4)
    assert out[1] < 1.0  # the sub-0.05 edge was NOT pruned away


def test_composite_blends_domain_and_pair_components():
    # Equal weights over two matrices: domain Dice 1.0, pair Dice 0.0
    # → composite 0.5 → novelty 0.5 for the non-validated row.
    M_dom = _coo([[0, 1], [0, 1]], n_cols=2)   # rows identical on domains
    M_pair = _coo([[0], [1]], n_cols=2)        # rows disjoint on pairs
    out = compute_novelty_against_validated(M_dom, M_pair, [0], weights=(0.5, 0.5))
    assert out[0] == pytest.approx(0.0, abs=1e-6)   # validated self
    assert out[1] == pytest.approx(0.5, abs=1e-6)


# ── domain novelty ───────────────────────────────────────────────────────


def test_domain_novelty_singleton_path_is_nan():
    M = _coo([[0, 1, 2]], n_cols=3)
    out = compute_domain_novelty_array(M, leaf_paths=["cluster.0.0.0.0"])
    assert np.isnan(out[0])


def test_domain_novelty_empty_path_is_nan():
    M = _coo([[0, 1], [1, 2]], n_cols=3)
    out = compute_domain_novelty_array(M, leaf_paths=["", ""])
    assert np.isnan(out).all()


def test_domain_novelty_unique_fraction_within_leaf():
    # Three rows in the same leaf path.
    #   row 0 domains: {0, 1}     → 0 shared with 1 (col 1), 1 unique (col 0)
    #   row 1 domains: {1, 2}     → 1 shared (col 1), 1 unique (col 2)
    #   row 2 domains: {3}        → 1 unique (col 3)
    M = _coo([[0, 1], [1, 2], [3]], n_cols=4)
    paths = ["cluster.0.0.0.0"] * 3
    out = compute_domain_novelty_array(M, paths)
    assert out[0] == pytest.approx(1 / 2, abs=1e-6)
    assert out[1] == pytest.approx(1 / 2, abs=1e-6)
    assert out[2] == pytest.approx(1.0, abs=1e-6)


def test_domain_novelty_separates_distinct_leaf_groups():
    # Two leaf groups; uniqueness must NOT cross the boundary.
    # Group A: rows 0,1 both have domain 0  → 0 unique for each
    # Group B: row 2 alone in group         → singleton → NaN
    M = _coo([[0], [0], [0]], n_cols=1)
    paths = ["cluster.A", "cluster.A", "cluster.B"]
    out = compute_domain_novelty_array(M, paths)
    assert out[0] == pytest.approx(0.0, abs=1e-6)
    assert out[1] == pytest.approx(0.0, abs=1e-6)
    assert np.isnan(out[2])


def test_domain_novelty_row_with_no_domains_is_nan():
    # Row 0 has no domains at all; row 1 has one.
    M = _coo([[], [0]], n_cols=2)
    out = compute_domain_novelty_array(M, leaf_paths=["cluster.0", "cluster.0"])
    assert np.isnan(out[0])
    # Row 1's lone domain is unique within the group of {row 0 (empty), row 1}
    # because row 0 contributes nothing to col_sums.
    assert out[1] == pytest.approx(1.0, abs=1e-6)


def test_domain_novelty_length_mismatch_raises():
    M = _coo([[0]], n_cols=1)
    with pytest.raises(ValueError):
        compute_domain_novelty_array(M, leaf_paths=["a", "b"])
