"""Build the protein × protein similarity matrix S from ProteinSimilarPair.

Streams pairs at ``cosine >= threshold`` and assembles a symmetric sparse
matrix with ``1.0`` on the diagonal so a protein self-matches when computing
the asymmetric Dice "shared" count.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import scipy.sparse as sp

log = logging.getLogger(__name__)


CHUNK = 500_000


def build_protein_similarity_matrix(
    protein_shas: "np.ndarray",
    threshold: float,
) -> "sp.csr_matrix":
    """Build the protein-protein similarity matrix S aligned with ``protein_shas``.

    Parameters
    ----------
    protein_shas:
        Column ordering for both rows and columns of S. Must match the
        column ordering of M produced by ``build_bgc_protein_matrix``.
    threshold:
        Minimum cosine kept. Pairs are filtered server-side via the
        ``(protein_a_sha256, cosine)`` index.

    Returns
    -------
    S:
        ``csr_matrix`` of shape ``(len(protein_shas), len(protein_shas))``
        with float32 entries; diagonal set to 1.0.
    """
    import numpy as np
    import scipy.sparse as sp

    from discovery.models import ProteinSimilarPair

    n = int(len(protein_shas))
    if n == 0:
        return sp.csr_matrix((0, 0), dtype=np.float32)

    sha_to_idx: dict[str, int] = {sha: i for i, sha in enumerate(protein_shas.tolist())}

    qs = (
        ProteinSimilarPair.objects.filter(
            cosine__gte=threshold,
            protein_a_sha256__in=list(sha_to_idx.keys()),
            protein_b_sha256__in=list(sha_to_idx.keys()),
        )
        .values_list("protein_a_sha256", "protein_b_sha256", "cosine")
    )

    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    counter = 0
    for a, b, cos in qs.iterator(chunk_size=CHUNK):
        ia = sha_to_idx.get(a)
        ib = sha_to_idx.get(b)
        if ia is None or ib is None or ia == ib:
            continue
        rows.append(ia)
        cols.append(ib)
        data.append(float(cos))
        counter += 1
        if counter % 5_000_000 == 0:
            log.info("build_protein_similarity_matrix: streamed %d pairs", counter)

    # Diagonal = 1.0 (self-pair) so a protein matches itself in M @ S.
    rows.extend(range(n))
    cols.extend(range(n))
    data.extend([1.0] * n)

    S = sp.csr_matrix(
        (np.asarray(data, dtype=np.float32),
         (np.asarray(rows, dtype=np.int64), np.asarray(cols, dtype=np.int64))),
        shape=(n, n),
    )
    # Pairs are stored both directions so S already symmetrizes after dedup.
    # Make symmetry explicit defensively (no-op when both directions are present).
    S = S.maximum(S.T).tocsr()
    log.info(
        "build_protein_similarity_matrix: %d × %d, nnz=%d, threshold=%.3f",
        S.shape[0], S.shape[1], S.nnz, threshold,
    )
    return S
