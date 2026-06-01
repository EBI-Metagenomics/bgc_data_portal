"""Build a symmetric KNN graph over BGCs from a sparse similarity matrix."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import igraph as ig
    import scipy.sparse as sp

log = logging.getLogger(__name__)


def build_knn_graph(sim: "sp.csr_matrix", k: int = 5) -> "ig.Graph":
    """For each row, keep its top-k off-diagonal entries; symmetrize.

    Edges with weight = similarity. Disconnected BGCs become singleton
    vertices. The vertex order matches the row/column order of ``sim``.
    """
    import igraph as ig
    import numpy as np

    n = sim.shape[0]
    if n == 0:
        return ig.Graph(directed=False)

    sim_csr = sim.tocsr(copy=False)
    edges: dict[tuple[int, int], float] = {}

    for row in range(n):
        start = sim_csr.indptr[row]
        end = sim_csr.indptr[row + 1]
        if start == end:
            continue
        neigh_idx = sim_csr.indices[start:end]
        neigh_val = sim_csr.data[start:end]
        # Drop self-loop in case the matrix kept its diagonal.
        mask = neigh_idx != row
        neigh_idx = neigh_idx[mask]
        neigh_val = neigh_val[mask]
        if neigh_idx.size == 0:
            continue
        if neigh_idx.size > k:
            top = np.argpartition(-neigh_val, k - 1)[:k]
            neigh_idx = neigh_idx[top]
            neigh_val = neigh_val[top]
        for col, val in zip(neigh_idx.tolist(), neigh_val.tolist()):
            a, b = (row, col) if row < col else (col, row)
            existing = edges.get((a, b))
            # Symmetrize: if either endpoint had the other in its top-k, keep
            # the larger weight to be safe (numerical noise).
            if existing is None or val > existing:
                edges[(a, b)] = float(val)

    g = ig.Graph(n=n, directed=False)
    if edges:
        edge_list = list(edges.keys())
        weights = [edges[e] for e in edge_list]
        g.add_edges(edge_list)
        g.es["weight"] = weights

    log.info(
        "build_knn_graph: %d vertices, %d edges, k=%d",
        g.vcount(), g.ecount(), k,
    )
    return g
