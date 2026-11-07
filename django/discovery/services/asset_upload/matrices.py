"""In-memory builders for the iBGC × domain and iBGC × adjacency-pair matrices.

These mirror :mod:`discovery.services.clustering.membership` and
:mod:`discovery.services.clustering.adjacency`, but consume an in-memory
``AssetData`` (the parsed upload) rather than querying the ORM. They emit
sparse CSR matrices with the **same column ordering** as the persisted
scoring cache so they can be horizontally stacked under the primary
matrices for composite similarity.

Label vocabulary: ``vocab`` selects the run's ``domain_vocab``
(``IPR_PROJECTED`` or ``IPR_GAPFILLED``); both go through
:func:`_kept_domain_labels`, which applies the same gap-fill rule as the
persistent builders (``membership.gapfilled_labels``).

Vocabulary handling: callers pass the primary run's ``domain_accs`` and
``pair_vocab`` (loaded from the scoring cache) so asset matrices use the
exact same column space; asset rows lose vocabulary not seen by the
primary run, which is fine — that's what the projection math expects.

The asset row order is determined by ``virtual_ibgcs`` — the same dict the
projection step uses to walk results back into the default cache (Postgres
DatabaseCache). Row N in the
returned matrix corresponds to the Nth ``VirtualIbgc``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from discovery.services.clustering.membership import (
    DEFAULT_DOMAIN_SOURCES,
    VOCAB_IPR_GAPFILLED,
    VOCAB_IPR_PROJECTED,
    _normalize_sources,
    check_vocab,
    gapfilled_labels,
    project_to_ipr,
)

if TYPE_CHECKING:
    import scipy.sparse as sp

    from .project import VirtualIbgc

log = logging.getLogger(__name__)


def _kept_domain_labels(
    vibgc: VirtualIbgc,
    upper_sources: tuple[str, ...],
    vocab: str,
) -> list[tuple[tuple, int, str]]:
    """``((bgc_key, cds_protein_id), dom_start, label)`` per kept asset domain.

    A blank ``ref_db`` counts as a selected source (the upload may omit it),
    as it always has for ``IPR_PROJECTED``. Not deduplicated for
    ``IPR_PROJECTED``; :func:`gapfilled_labels` dedups for ``IPR_GAPFILLED``.
    """
    if check_vocab(vocab) == VOCAB_IPR_GAPFILLED:
        rows = (
            (
                (d.bgc_key, d.cds_protein_id or ""),
                d.ref_db or upper_sources[0],
                d.domain_acc,
                d.interpro_entry_acc,
                d.start_position,
                d.end_position,
            )
            for d in vibgc.domains
        )
        return gapfilled_labels(rows, sources=upper_sources)

    out: list[tuple[tuple, int, str]] = []
    for domain in vibgc.domains:
        if not domain.domain_acc:
            continue
        if domain.ref_db and domain.ref_db.upper() not in upper_sources:
            continue
        label = project_to_ipr(domain.domain_acc, domain.interpro_entry_acc)
        out.append(
            (
                (domain.bgc_key, domain.cds_protein_id or ""),
                domain.start_position,
                label,
            )
        )
    return out


def build_asset_domain_matrix(
    virtual_ibgcs: Sequence[VirtualIbgc],
    *,
    sources: Sequence[str] = DEFAULT_DOMAIN_SOURCES,
    domain_accs: Sequence[str],
    vocab: str = VOCAB_IPR_PROJECTED,
) -> sp.csr_matrix:
    """Return the asset's iBGC × domain binary matrix on the given vocabulary.

    Rows are ordered to match ``virtual_ibgcs``; columns to match
    ``domain_accs`` (the primary run's vocabulary, **already IPR-projected**).
    Each asset domain is projected via
    :func:`discovery.services.clustering.membership.project_to_ipr` to the
    same label space before lookup. Domains from non-selected ``ref_db``
    sources are silently dropped, mirroring the persistent builder's
    behaviour. Per-protein-anchor dedup matches the persistent path:
    ``(virtual_ibgc_index, label, cds_protein_id)`` collapses to a single
    binary entry.
    """
    import numpy as np
    import scipy.sparse as sp

    upper_sources = _normalize_sources(sources)
    col_index = {acc: i for i, acc in enumerate(domain_accs)}

    rows_out: list[int] = []
    cols_out: list[int] = []
    seen: set[tuple[int, int, str]] = set()

    for row_idx, vibgc in enumerate(virtual_ibgcs):
        for (_bgc_key, anchor), _start, label in _kept_domain_labels(
            vibgc, upper_sources, vocab
        ):
            col_idx = col_index.get(label)
            if col_idx is None:
                continue
            key = (row_idx, col_idx, anchor)
            if key in seen:
                continue
            seen.add(key)
            rows_out.append(row_idx)
            cols_out.append(col_idx)

    if not rows_out:
        return sp.csr_matrix((len(virtual_ibgcs), len(domain_accs)), dtype=np.uint8)

    # Project the per-anchor entries down to (row, col) binary membership.
    pairs = {(r, c) for r, c, _ in seen}
    rows_arr = np.fromiter((r for r, _ in pairs), dtype=np.int64, count=len(pairs))
    cols_arr = np.fromiter((c for _, c in pairs), dtype=np.int64, count=len(pairs))
    data = np.ones(len(pairs), dtype=np.uint8)
    M = sp.csr_matrix(
        (data, (rows_arr, cols_arr)),
        shape=(len(virtual_ibgcs), len(domain_accs)),
        dtype=np.uint8,
    )
    log.info(
        "build_asset_domain_matrix: %d rows × %d domains, nnz=%d",
        M.shape[0],
        M.shape[1],
        M.nnz,
    )
    return M


def build_asset_adjacency_pair_matrix(
    virtual_ibgcs: Sequence[VirtualIbgc],
    *,
    sources: Sequence[str] = DEFAULT_DOMAIN_SOURCES,
    pair_vocab: Sequence[tuple[str, str]],
    vocab: str = VOCAB_IPR_PROJECTED,
) -> sp.csr_matrix:
    """Return the asset's iBGC × adjacent-domain-pair binary matrix.

    Mirrors :func:`discovery.services.clustering.adjacency.build_ibgc_adjacency_pair_matrix`:

    1. Filter domains by ``ref_db`` ∈ ``sources``, drop rows without a CDS anchor.
    2. Sort by ``(cds_start, domain_start)`` across all member BGCs of the iBGC.
    3. Project each accession to IPR-when-available
       (see :func:`discovery.services.clustering.membership.project_to_ipr`).
    4. Collapse contiguous repeats of the same projected label.
    5. Sliding-window-2 over the collapsed list; canonicalise each pair to
       a sorted tuple.

    Pairs outside the supplied ``pair_vocab`` are dropped (matches the
    column projection used by ``run_support._align_rows``).
    """
    import numpy as np
    import scipy.sparse as sp

    upper_sources = _normalize_sources(sources)
    pair_index = {tuple(sorted(p)): i for i, p in enumerate(pair_vocab)}

    rows_out: list[int] = []
    cols_out: list[int] = []
    seen: set[tuple[int, int]] = set()

    for row_idx, vibgc in enumerate(virtual_ibgcs):
        # Position-sorted (cds_start, domain_start, acc) entries. cds_start
        # comes from the CDS that owns each domain — look it up from the
        # virtual iBGC's CDS list, keyed on (bgc_key, protein_id).
        cds_start_by_id: dict[tuple[tuple[str, int, int, str], str], int] = {}
        for cds in vibgc.cds:
            cds_start_by_id[(cds.bgc_key, cds.protein_id_str)] = cds.start_position

        entries: list[tuple[int, int, str]] = []
        for cds_key, dom_start, label in _kept_domain_labels(
            vibgc, upper_sources, vocab
        ):
            cds_start = cds_start_by_id.get(cds_key)
            if cds_start is None:
                # No genomic anchor → can't sit in an adjacency.
                continue
            entries.append((cds_start, dom_start, label))

        ordered = sorted(set(entries))
        if len(ordered) < 2:
            continue

        # Collapse contiguous repeats of the same projected label (see
        # discovery.services.clustering.adjacency for the rule).
        accs: list[str] = []
        for _, _, label in ordered:
            if accs and accs[-1] == label:
                continue
            accs.append(label)
        if len(accs) < 2:
            continue
        for i in range(len(accs) - 1):
            pair = tuple(sorted((accs[i], accs[i + 1])))
            col_idx = pair_index.get(pair)
            if col_idx is None:
                continue
            key = (row_idx, col_idx)
            if key in seen:
                continue
            seen.add(key)
            rows_out.append(row_idx)
            cols_out.append(col_idx)

    if not rows_out:
        return sp.csr_matrix((len(virtual_ibgcs), len(pair_vocab)), dtype=np.uint8)

    rows_arr = np.asarray(rows_out, dtype=np.int64)
    cols_arr = np.asarray(cols_out, dtype=np.int64)
    data = np.ones(len(rows_out), dtype=np.uint8)
    M = sp.csr_matrix(
        (data, (rows_arr, cols_arr)),
        shape=(len(virtual_ibgcs), len(pair_vocab)),
        dtype=np.uint8,
    )
    log.info(
        "build_asset_adjacency_pair_matrix: %d rows × %d pairs, nnz=%d",
        M.shape[0],
        M.shape[1],
        M.nnz,
    )
    return M
