"""Build the BGC × protein membership matrix from DashboardCds.

Protein vocabulary is keyed on **unique ``protein_sha256``** so overlapping
BGCs that share a protein contribute the same column index — never duplicate
columns. The (bgc_id, protein_sha256) pairs are deduplicated before COO
assembly so a BGC that lists the same protein twice (multi-CDS pointing to
identical sequence) doesn't get an inflated membership count.

Heavy imports (numpy, scipy.sparse) are deferred inside the function body.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import scipy.sparse as sp

log = logging.getLogger(__name__)


CHUNK = 200_000


def build_bgc_protein_matrix(
    *,
    only_complete: bool = True,
    bgc_ids_subset: list[int] | None = None,
    protein_shas_subset: list[str] | None = None,
) -> tuple["sp.csr_matrix", "np.ndarray", "np.ndarray"]:
    """Stream DashboardCds rows and build a sparse membership matrix.

    Parameters
    ----------
    only_complete:
        Restrict to BGCs with ``is_partial=False`` — used for the primary
        clustering pass. Partial BGCs are routed through ``reclassify`` later.
    bgc_ids_subset:
        Optional explicit list of BGC ids to include (intersected with the
        ``only_complete`` filter). Used by the reclassifier to materialize a
        single-row M against the run's vocabulary.
    protein_shas_subset:
        Optional list of protein sha256 strings defining the column space.
        When supplied, proteins outside this set are dropped from the matrix.
        The reclassifier uses this to align query BGCs with the run's S.

    Returns
    -------
    M:
        ``csr_matrix`` of shape ``(n_bgcs, n_proteins)`` with dtype uint8 and
        deduplicated 1-entries.
    bgc_ids:
        ``np.ndarray[int64]`` row label for each row of M.
    protein_shas:
        ``np.ndarray[object]`` column label (sha256 string) for each column of M.
    """
    import numpy as np
    import scipy.sparse as sp

    from discovery.models import DashboardCds

    qs = DashboardCds.objects.exclude(protein_sha256="").values_list(
        "bgc_id", "protein_sha256"
    )
    if only_complete:
        qs = qs.filter(bgc__is_partial=False)
    if bgc_ids_subset is not None:
        qs = qs.filter(bgc_id__in=list(bgc_ids_subset))
    if protein_shas_subset is not None:
        qs = qs.filter(protein_sha256__in=list(protein_shas_subset))

    pair_set: set[tuple[int, str]] = set()
    n = 0
    for bgc_id, sha in qs.iterator(chunk_size=CHUNK):
        if not sha:
            continue
        pair_set.add((bgc_id, sha))
        n += 1
        if n % 1_000_000 == 0:
            log.info("build_bgc_protein_matrix: streamed %d cds rows", n)

    if not pair_set:
        empty = sp.csr_matrix((0, 0), dtype=np.uint8)
        return empty, np.empty(0, dtype=np.int64), np.empty(0, dtype=object)

    bgc_ids_unique = sorted({bid for bid, _ in pair_set})
    if protein_shas_subset is not None:
        # Preserve caller-provided ordering so columns line up across runs.
        protein_shas_unique = list(protein_shas_subset)
    else:
        protein_shas_unique = sorted({sha for _, sha in pair_set})

    bgc_index = {b: i for i, b in enumerate(bgc_ids_unique)}
    protein_index = {p: j for j, p in enumerate(protein_shas_unique)}

    rows: list[int] = []
    cols: list[int] = []
    for bgc_id, sha in pair_set:
        col = protein_index.get(sha)
        if col is None:
            continue
        rows.append(bgc_index[bgc_id])
        cols.append(col)

    data = np.ones(len(rows), dtype=np.uint8)
    M = sp.csr_matrix(
        (data, (np.asarray(rows, dtype=np.int64), np.asarray(cols, dtype=np.int64))),
        shape=(len(bgc_ids_unique), len(protein_shas_unique)),
        dtype=np.uint8,
    )
    log.info(
        "build_bgc_protein_matrix: %d BGCs × %d proteins, nnz=%d (only_complete=%s)",
        M.shape[0], M.shape[1], M.nnz, only_complete,
    )
    return (
        M,
        np.asarray(bgc_ids_unique, dtype=np.int64),
        np.asarray(protein_shas_unique, dtype=object),
    )
