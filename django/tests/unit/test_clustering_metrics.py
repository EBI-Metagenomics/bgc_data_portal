"""Pure-function tests for the BGC similarity metric abstraction.

Operates on synthetic sparse matrices without touching the DB. Verifies:
  * ``SorensenDiceSimilarity`` matches the closed form for hand-built inputs.
  * Symmetry, range, and shared-protein dedup invariants hold.
  * Swapping in ``JaccardSimilarity`` / ``OverlapSimilarity`` produces a
    different but predictable result — proving the abstraction works.
"""

from __future__ import annotations

import numpy as np
import pytest

scipy_sparse = pytest.importorskip("scipy.sparse")

from discovery.services.clustering.metrics import (  # noqa: E402
    JaccardSimilarity,
    OverlapSimilarity,
    SorensenDiceSimilarity,
    get_metric,
)


def _build_M(rows: list[list[int]], n_proteins: int) -> "scipy_sparse.csr_matrix":
    """Build a (n_bgcs, n_proteins) 0/1 sparse membership matrix from explicit rows."""
    n_bgcs = len(rows)
    data = []
    coords_r: list[int] = []
    coords_c: list[int] = []
    for r, cols in enumerate(rows):
        for c in cols:
            coords_r.append(r)
            coords_c.append(c)
            data.append(1)
    return scipy_sparse.csr_matrix(
        (data, (coords_r, coords_c)),
        shape=(n_bgcs, n_proteins),
        dtype=np.uint8,
    )


def _identity_S(n: int) -> "scipy_sparse.csr_matrix":
    """Diagonal-only S so a protein only matches itself."""
    return scipy_sparse.eye(n, dtype=np.float32, format="csr")


def test_dice_diagonal_only_S_matches_classical_dice():
    # 3 BGCs sharing some proteins; S = identity → asymmetric == classical.
    M = _build_M([[0, 1, 2], [1, 2, 3], [4, 5]], n_proteins=6)
    sim = SorensenDiceSimilarity(threshold=0.9)(M, _identity_S(6))
    dense = sim.toarray()
    # |A| = 3, |B| = 3, shared = 2 (proteins 1 & 2) → dice = 2*2/(3+3) = 0.6667
    assert dense[0, 1] == pytest.approx(2 * 2 / (3 + 3))
    # symmetry
    assert dense[0, 1] == pytest.approx(dense[1, 0])
    # disjoint pair → 0
    assert dense[0, 2] == 0.0
    # diagonal is dropped by compute_bgc_similarity, but raw metric output
    # leaves it; the metric itself does NOT drop self-matches:
    assert dense[0, 0] == pytest.approx(2 * 3 / (3 + 3))


def test_dice_range_and_symmetry():
    rng = np.random.default_rng(42)
    n_bgcs = 7
    n_proteins = 12
    rows = []
    for _ in range(n_bgcs):
        size = rng.integers(2, 6)
        rows.append(sorted(rng.choice(n_proteins, size=size, replace=False).tolist()))
    M = _build_M(rows, n_proteins)
    sim = SorensenDiceSimilarity(threshold=0.9)(M, _identity_S(n_proteins))
    dense = sim.toarray()
    # Every entry in [0, 1].
    assert np.all((dense >= 0) & (dense <= 1.0 + 1e-9))
    # Symmetric.
    np.testing.assert_allclose(dense, dense.T, atol=1e-9)


def test_dice_shared_protein_dedup_overlapping_bgcs():
    # Two BGCs that physically overlap and therefore share the same protein.
    # Protein 1 is in both — must be counted once, not twice.
    M = _build_M([[0, 1, 2], [1, 3]], n_proteins=4)
    sim = SorensenDiceSimilarity(threshold=0.9)(M, _identity_S(4))
    dense = sim.toarray()
    # |A|=3, |B|=2, shared = {protein 1} via self-match → dice = 2*1/(3+2) = 0.4
    assert dense[0, 1] == pytest.approx(2 * 1 / (3 + 2))


def test_swapping_metric_changes_result_predictably():
    M = _build_M([[0, 1, 2, 3], [2, 3, 4]], n_proteins=5)
    S = _identity_S(5)

    dice = SorensenDiceSimilarity(threshold=0.9)(M, S).toarray()
    jaccard = JaccardSimilarity(threshold=0.9)(M, S).toarray()
    overlap = OverlapSimilarity(threshold=0.9)(M, S).toarray()

    # |A|=4, |B|=3, shared=2.
    # dice    = 2*2/(4+3)   = 0.5714...
    # jaccard = 2 / (4+3-2) = 0.4
    # overlap = 2 / min(4,3)= 0.6667
    assert dice[0, 1] == pytest.approx(2 * 2 / (4 + 3))
    assert jaccard[0, 1] == pytest.approx(2 / (4 + 3 - 2))
    assert overlap[0, 1] == pytest.approx(2 / min(4, 3))
    assert dice[0, 1] != jaccard[0, 1]


def test_get_metric_resolves_by_name():
    m = get_metric("dice", threshold=0.9)
    assert isinstance(m, SorensenDiceSimilarity)
    assert m.name == "dice"
    with pytest.raises(ValueError):
        get_metric("bogus", threshold=0.9)


def test_threshold_guard():
    with pytest.raises(ValueError):
        SorensenDiceSimilarity(threshold=1.5)
    with pytest.raises(ValueError):
        OverlapSimilarity(threshold=-0.1)
