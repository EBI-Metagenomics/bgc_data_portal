"""Pick representative BGCs (medoids) for cluster nodes.

The representative is the BGC with the highest sum of similarities to other
members of its community — i.e. the medoid under the BGC × BGC similarity
matrix used for clustering.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import scipy.sparse as sp

log = logging.getLogger(__name__)


def pick_medoid(
    member_indices: list[int],
    sim: "sp.csr_matrix",
) -> int:
    """Return the BGC index from ``member_indices`` with the highest summed similarity to the rest.

    Ties are broken deterministically by smallest member index.
    Operates on the global ``sim`` matrix and the global indices in
    ``member_indices`` to avoid copying. Returns one of the input indices.
    """
    import numpy as np

    if not member_indices:
        raise ValueError("member_indices must be non-empty")
    if len(member_indices) == 1:
        return member_indices[0]

    sim_csr = sim.tocsr(copy=False)
    # Sum of similarities to other members of the community (excluding self).
    members_set = set(member_indices)
    sums = np.zeros(len(member_indices), dtype=np.float64)
    for i, idx in enumerate(member_indices):
        start = sim_csr.indptr[idx]
        end = sim_csr.indptr[idx + 1]
        cols = sim_csr.indices[start:end]
        vals = sim_csr.data[start:end]
        s = 0.0
        for c, v in zip(cols.tolist(), vals.tolist()):
            if c == idx:
                continue
            if c in members_set:
                s += float(v)
        sums[i] = s

    best = int(np.argmax(sums))
    # Stable tie-break on equal score: smallest index wins.
    max_score = sums[best]
    candidates = [
        member_indices[i] for i in range(len(member_indices)) if sums[i] == max_score
    ]
    return min(candidates)
