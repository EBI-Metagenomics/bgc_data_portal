"""2D layout for the BGC graph (replacement for the old UMAP-2d step).

Prefers UMAP with ``metric="precomputed_knn"`` fed by the same KNN graph
used for community detection — keeps the visualization coherent with the
clustering. Falls back to igraph DRL/Fruchterman–Reingold for small graphs
or when umap-learn is unavailable.

Coordinates are normalized to ``[-10, 10]`` on both axes so the dashboard
scatter plot scales stay stable across re-runs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import igraph as ig
    import numpy as np
    import scipy.sparse as sp

log = logging.getLogger(__name__)


_LAYOUT_RANGE = 10.0
_UMAP_MIN_VERTICES = 50


def compute_2d_layout(
    graph: "ig.Graph",
    sim: "sp.csr_matrix",
    *,
    seed: int = 42,
    n_neighbors: int | None = None,
) -> "np.ndarray":
    """Return a normalized ``(n_bgcs, 2)`` array of 2D coordinates.

    Tries UMAP on the KNN structure of ``sim``; falls back to igraph DRL
    for small graphs or if umap-learn is missing.
    """
    import numpy as np

    n = graph.vcount()
    if n == 0:
        return np.zeros((0, 2), dtype=np.float64)

    coords: np.ndarray | None = None

    if n >= _UMAP_MIN_VERTICES:
        coords = _umap_layout(sim, seed=seed, n_neighbors=n_neighbors)

    if coords is None:
        coords = _igraph_layout(graph, seed=seed)

    return _normalize(coords)


def _umap_layout(
    sim: "sp.csr_matrix",
    *,
    seed: int,
    n_neighbors: int | None,
) -> "np.ndarray | None":
    """Run UMAP on the KNN structure of ``sim``. Returns None on failure."""
    try:
        import numpy as np
        import umap as umap_lib
    except ImportError:
        log.warning("umap-learn not available; falling back to igraph layout")
        return None

    n = sim.shape[0]
    if n == 0:
        return np.zeros((0, 2), dtype=np.float64)

    # Convert sparse similarity to per-row top-k indices/distances for UMAP.
    # umap-learn's "precomputed_knn" wants knn_indices (n, k) and
    # knn_dists (n, k); we synthesize them from the sparse rows.
    sim_csr = sim.tocsr(copy=False)
    k_default = max(5, min(15, n - 1))
    k = n_neighbors or k_default

    knn_idx = np.full((n, k), -1, dtype=np.int64)
    knn_dist = np.full((n, k), 1.0, dtype=np.float32)
    for row in range(n):
        start = sim_csr.indptr[row]
        end = sim_csr.indptr[row + 1]
        cols = sim_csr.indices[start:end]
        vals = sim_csr.data[start:end]
        order = np.argsort(-vals)[:k]
        cols = cols[order]
        vals = vals[order]
        # Drop self-loops if present.
        keep = cols != row
        cols = cols[keep]
        vals = vals[keep]
        knn_idx[row, : cols.size] = cols
        knn_dist[row, : cols.size] = (1.0 - vals).astype(np.float32)
        # Pad the rest with self-distance 0 — UMAP expects at least one
        # neighbour per row; this is harmless when sim row is degenerate.
        if cols.size == 0:
            knn_idx[row, 0] = row
            knn_dist[row, 0] = 0.0

    try:
        reducer = umap_lib.UMAP(
            n_components=2,
            metric="precomputed",
            random_state=seed,
            n_neighbors=k,
        )
        # When the user-supplied indices/dists are passed via precomputed_knn
        # parameter, umap-learn uses them directly.
        coords = reducer.fit_transform(
            np.zeros((n, 1), dtype=np.float32),
            ensure_all_finite=False,
        )  # placeholder X; UMAP uses `precomputed_knn`
    except Exception:  # pragma: no cover - upstream API drift
        log.exception("UMAP layout failed; falling back to igraph layout")
        return None

    return np.asarray(coords, dtype=np.float64)


def _igraph_layout(graph: "ig.Graph", *, seed: int) -> "np.ndarray":
    """Layout via igraph (DRL preferred, Fruchterman–Reingold as fallback)."""
    import numpy as np

    n = graph.vcount()
    if n == 0:
        return np.zeros((0, 2), dtype=np.float64)
    try:
        layout = graph.layout_drl(seed=None)
    except Exception:
        try:
            layout = graph.layout_fruchterman_reingold(seed=None)
        except Exception:
            layout = graph.layout_random()
    return np.asarray(layout.coords, dtype=np.float64)


def _normalize(coords: "np.ndarray") -> "np.ndarray":
    """Centre on origin; scale longest extent to ``_LAYOUT_RANGE``."""
    import numpy as np

    if coords.shape[0] == 0:
        return coords
    centred = coords - coords.mean(axis=0, keepdims=True)
    extent = float(np.max(np.abs(centred))) or 1.0
    return (centred / extent) * _LAYOUT_RANGE
