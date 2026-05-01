"""Pure-function tests for build_knn_graph."""

from __future__ import annotations

import numpy as np
import pytest

scipy_sparse = pytest.importorskip("scipy.sparse")
igraph = pytest.importorskip("igraph")

from discovery.services.clustering.knn_graph import build_knn_graph  # noqa: E402


def _sim_from_dense(dense: np.ndarray) -> "scipy_sparse.csr_matrix":
    return scipy_sparse.csr_matrix(np.asarray(dense, dtype=np.float64))


def test_knn_top_k_per_row_symmetrized():
    # 4 BGCs, similarity table:
    #     0   1    2    3
    # 0 [ 0  0.9 0.1 0.0 ]
    # 1 [0.9  0  0.5 0.0 ]
    # 2 [0.1 0.5  0  0.7 ]
    # 3 [0.0 0.0 0.7  0  ]
    sim = _sim_from_dense(
        [
            [0.0, 0.9, 0.1, 0.0],
            [0.9, 0.0, 0.5, 0.0],
            [0.1, 0.5, 0.0, 0.7],
            [0.0, 0.0, 0.7, 0.0],
        ]
    )
    g = build_knn_graph(sim, k=1)
    edges = {tuple(sorted(e)) for e in g.get_edgelist()}
    # Top-1 from row 0 → 1; row 1 → 0; row 2 → 3; row 3 → 2.
    # Symmetric union: {(0,1), (2,3)}.
    assert edges == {(0, 1), (2, 3)}
    # Edge weights present.
    weights = sorted(g.es["weight"])
    assert weights == pytest.approx([0.7, 0.9])


def test_knn_disconnected_vertex_becomes_singleton():
    # Vertex 2 has zero similarity to everyone.
    sim = _sim_from_dense(
        [
            [0.0, 0.9, 0.0],
            [0.9, 0.0, 0.0],
            [0.0, 0.0, 0.0],
        ]
    )
    g = build_knn_graph(sim, k=2)
    assert g.vcount() == 3
    # Vertex 2 has no edges.
    assert g.degree(2) == 0


def test_knn_self_loop_dropped():
    # Similarity matrix with bogus diagonal entries — should be ignored.
    sim = _sim_from_dense(
        [
            [0.99, 0.5, 0.0],
            [0.5, 0.99, 0.4],
            [0.0, 0.4, 0.99],
        ]
    )
    g = build_knn_graph(sim, k=1)
    # No self-loops.
    for src, dst in g.get_edgelist():
        assert src != dst


def test_empty_input_returns_empty_graph():
    sim = scipy_sparse.csr_matrix((0, 0), dtype=np.float64)
    g = build_knn_graph(sim, k=5)
    assert g.vcount() == 0
    assert g.ecount() == 0
