"""Pure-function tests for the composite weighted-mean Dice similarity.

Operates on synthetic sparse matrices without touching the DB. Verifies:
  * Closed-form Dice math matches hand-computed values on small fixtures.
  * Weights (1, 0) recover pure domain-set Dice; (0, 1) recovers pure pair Dice.
  * Diagonal is zeroed and the matrix is symmetric.
  * Edge case: an all-zero pair-matrix row contributes 0 to that BGC's
    pair score without crashing.
"""

from __future__ import annotations

import numpy as np
import pytest

scipy_sparse = pytest.importorskip("scipy.sparse")

from discovery.services.clustering.bgc_similarity import (  # noqa: E402
    compute_composite_similarity,
    compute_composite_similarity_block,
)
from discovery.services.clustering.metrics import (  # noqa: E402
    dice_block,
    dice_similarity,
)


def _build_M(rows: list[list[int]], n_cols: int) -> scipy_sparse.csr_matrix:
    n_rows = len(rows)
    coords_r: list[int] = []
    coords_c: list[int] = []
    for r, cols in enumerate(rows):
        for c in cols:
            coords_r.append(r)
            coords_c.append(c)
    data = np.ones(len(coords_r), dtype=np.uint8)
    return scipy_sparse.csr_matrix(
        (data, (coords_r, coords_c)),
        shape=(n_rows, n_cols),
        dtype=np.uint8,
    )


def test_dice_similarity_closed_form():
    # |A|=3, |B|=3, shared=2 → 2·2/(3+3) = 0.6667
    M = _build_M([[0, 1, 2], [1, 2, 3], [4, 5]], n_cols=6)
    sim = dice_similarity(M).toarray()
    assert sim[0, 1] == pytest.approx(2 * 2 / (3 + 3))
    assert sim[0, 2] == 0.0
    # Diagonal is intentionally not zeroed by the metric itself.
    assert sim[0, 0] == pytest.approx(2 * 3 / (3 + 3))


def test_composite_default_weights_average_both_components():
    # Domain matrix: A=[0,1,2], B=[1,2,3]  → set Dice = 2*2/(3+3) = 0.6667
    M_dom = _build_M([[0, 1, 2], [1, 2, 3]], n_cols=4)
    # Pair matrix: A has pairs {p0,p1}, B has pairs {p1,p2} → Dice = 2*1/(2+2) = 0.5
    M_pair = _build_M([[0, 1], [1, 2]], n_cols=3)
    sim = compute_composite_similarity(M_dom, M_pair, weights=(0.5, 0.5)).toarray()
    expected = 0.5 * (2 * 2 / (3 + 3)) + 0.5 * (2 * 1 / (2 + 2))
    assert sim[0, 1] == pytest.approx(expected, abs=1e-6)
    # Diagonal must be zeroed.
    assert sim[0, 0] == 0.0
    assert sim[1, 1] == 0.0
    # Symmetric.
    np.testing.assert_allclose(sim, sim.T, atol=1e-9)


def test_lone_domain_weight_recovers_pure_domain_dice():
    M_dom = _build_M([[0, 1, 2], [1, 2, 3]], n_cols=4)
    M_pair = _build_M([[0, 1], [1, 2]], n_cols=3)
    sim = compute_composite_similarity(M_dom, M_pair, weights=(1.0, 0.0)).toarray()
    assert sim[0, 1] == pytest.approx(2 * 2 / (3 + 3), abs=1e-6)


def test_lone_adjacency_weight_recovers_pure_pair_dice():
    M_dom = _build_M([[0, 1, 2], [1, 2, 3]], n_cols=4)
    M_pair = _build_M([[0, 1], [1, 2]], n_cols=3)
    sim = compute_composite_similarity(M_dom, M_pair, weights=(0.0, 1.0)).toarray()
    assert sim[0, 1] == pytest.approx(2 * 1 / (2 + 2), abs=1e-6)


def test_composite_handles_empty_pair_row():
    # Second BGC has no adjacent pairs (e.g. a 1-domain iBGC).
    M_dom = _build_M([[0, 1, 2], [1]], n_cols=4)
    M_pair_data = scipy_sparse.csr_matrix(
        ([1], ([0], [0])),
        shape=(2, 1),
        dtype=np.uint8,
    )  # only row 0 has any pair
    sim = compute_composite_similarity(M_dom, M_pair_data, weights=(0.5, 0.5)).toarray()
    # Pair-Dice with row-2 is 0 (B has empty pair set).
    # Set-Dice: A={0,1,2}, B={1} → 2·1/(3+1) = 0.5. Composite = 0.5·0.5 = 0.25.
    assert sim[0, 1] == pytest.approx(0.5 * 0.5, abs=1e-6)


def test_composite_renormalizes_weights():
    M_dom = _build_M([[0, 1], [0, 2]], n_cols=3)
    M_pair = _build_M([[0], [0]], n_cols=1)
    base = compute_composite_similarity(M_dom, M_pair, weights=(1.0, 1.0)).toarray()
    scaled = compute_composite_similarity(M_dom, M_pair, weights=(2.0, 2.0)).toarray()
    np.testing.assert_allclose(base, scaled, atol=1e-6)


def test_composite_row_mismatch_raises():
    M_dom = _build_M([[0], [1], [2]], n_cols=3)
    M_pair = _build_M([[0], [0]], n_cols=1)
    with pytest.raises(ValueError):
        compute_composite_similarity(M_dom, M_pair)


# ── Rectangular query-vs-reference Dice block (asset projection fast path) ──


def test_dice_block_matches_full_slice():
    # 4 reference rows, 2 query rows over a shared 6-col feature space.
    M_ref = _build_M([[0, 1, 2], [1, 2, 3], [4, 5], [0, 5]], n_cols=6)
    M_query = _build_M([[1, 2, 3], [0, 1]], n_cols=6)
    n_ref = M_ref.shape[0]

    full = dice_similarity(scipy_sparse.vstack([M_ref, M_query])).toarray()
    expected = full[n_ref:, :n_ref]
    got = dice_block(M_query, M_ref).toarray()
    np.testing.assert_allclose(got, expected, atol=1e-6)


def test_dice_block_feature_mismatch_raises():
    M_query = _build_M([[0, 1]], n_cols=4)
    M_ref = _build_M([[0, 1]], n_cols=3)
    with pytest.raises(ValueError):
        dice_block(M_query, M_ref)


def test_dice_block_empty_query_returns_empty():
    M_ref = _build_M([[0, 1], [1, 2]], n_cols=3)
    M_query = scipy_sparse.csr_matrix((0, 3), dtype=np.uint8)
    block = dice_block(M_query, M_ref)
    assert block.shape == (0, 2)


def test_composite_block_equals_full_self_similarity_slice():
    """The fast path must reproduce the asset×primary block of the full
    stacked composite similarity used before the optimisation."""
    # Primary (reference) set.
    M_dom_pri = _build_M([[0, 1, 2], [1, 2, 3], [4, 5], [0, 3, 5]], n_cols=6)
    M_pair_pri = _build_M([[0, 1], [1, 2], [3], [0, 2]], n_cols=4)
    # Asset (query) set — disjoint rows, same column space.
    M_dom_q = _build_M([[1, 2, 3], [4]], n_cols=6)
    M_pair_q = _build_M([[1, 2], [3]], n_cols=4)
    n_pri = M_dom_pri.shape[0]

    weights = (0.5, 0.5)
    full = compute_composite_similarity(
        scipy_sparse.vstack([M_dom_pri, M_dom_q], format="csr"),
        scipy_sparse.vstack([M_pair_pri, M_pair_q], format="csr"),
        weights=weights,
        prune_below=0.0,
    ).toarray()
    expected_block = full[n_pri:, :n_pri]

    got_block = compute_composite_similarity_block(
        M_dom_q, M_dom_pri, M_pair_q, M_pair_pri, weights=weights
    ).toarray()

    assert got_block.shape == (2, n_pri)
    np.testing.assert_allclose(got_block, expected_block, atol=1e-6)


def test_composite_block_respects_weights():
    M_dom_pri = _build_M([[0, 1, 2], [1, 2, 3]], n_cols=4)
    M_pair_pri = _build_M([[0, 1], [1, 2]], n_cols=3)
    M_dom_q = _build_M([[1, 2, 3]], n_cols=4)
    M_pair_q = _build_M([[1, 2]], n_cols=3)

    dom_only = compute_composite_similarity_block(
        M_dom_q, M_dom_pri, M_pair_q, M_pair_pri, weights=(1.0, 0.0)
    ).toarray()
    # query domains {1,2,3} vs primary row1 {1,2,3} → identical sets → Dice 1.0
    assert dom_only[0, 1] == pytest.approx(1.0, abs=1e-6)

    pair_only = compute_composite_similarity_block(
        M_dom_q, M_dom_pri, M_pair_q, M_pair_pri, weights=(0.0, 1.0)
    ).toarray()
    # query pairs {1,2} vs primary row1 pairs {1,2} → identical → Dice 1.0
    assert pair_only[0, 1] == pytest.approx(1.0, abs=1e-6)
