"""Build the iBGC × domain-label membership matrix.

Each row is a :class:`discovery.models.IntegratedBgc`; each column is a
unique **domain label**. The matrix is binary: a 1 means at least one
``ContigDomain`` whose parent CDS's ``cds_range`` overlaps the iBGC's
``bgc_range`` on the same contig carries that label.

**Contig-anchored join** — there is no direct FK between ``ContigDomain``
and ``IntegratedBgc`` in the v2 schema. The two are reached via:

    ContigDomain → ContigCds (cds_id)
                 → DashboardContig (contig_id)
                 → IntegratedBgc (contig_id == cds.contig_id
                                  AND bgc_range && cds_range)

This is expressed as a single SQL join below; GIN on ``bgc_range`` and
the FK index on ``cds_id`` keep it cheap.

**IPR-when-available projection** — each row's label is its
``interpro_entry_acc`` when non-blank (e.g. ``IPR000123``), else the raw
signature ``domain_acc`` (e.g. ``PF00001``). Input rows are gated by
``ref_db`` ∈ ``{PFAM, NCBIFAM, TIGRFAM}`` (case-insensitive). See
:func:`project_to_ipr`.

Dedup runs on the projected label: ``(ibgc_id, label, cds_start)`` counts
each label once per CDS position, and the binary projection then collapses
to a single column entry per iBGC.

**Vocabularies** (``ClusteringRun.domain_vocab``):

* ``IPR_PROJECTED`` — the rows above, nothing else (the original vocabulary).
* ``IPR_GAPFILLED`` — ADR 0003. Additionally reads Gene3D / PRINTS /
  ProSitePatterns hits and keeps one only when it fills a gap: it must not
  overlap any already-kept hit on the same CDS by ≥ 50 % of the shorter span
  (priority Gene3D > PRINTS > ProSite). See :func:`gapfilled_labels`; the
  rule is the 2026-10-23 benchmark's ``bgcsim.tokens`` ``V3_all_ipr``.

Heavy imports (numpy, scipy.sparse) are deferred inside the function body
so this module can be imported on the web container without ML deps.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import scipy.sparse as sp

from discovery.services.sql import IBGC_DOMAIN_HIT_JOIN

log = logging.getLogger(__name__)


CHUNK = 200_000

DEFAULT_DOMAIN_SOURCES: tuple[str, ...] = ("PFAM", "NCBIFAM", "TIGRFAM")

# Mirrors ClusteringRun.DOMAIN_VOCAB_* (kept here so the builders don't import
# models at module load).
VOCAB_IPR_PROJECTED = "IPR_PROJECTED"
VOCAB_IPR_GAPFILLED = "IPR_GAPFILLED"
VOCABS: tuple[str, ...] = (VOCAB_IPR_PROJECTED, VOCAB_IPR_GAPFILLED)

# Gap-fill sources, lower value = higher priority.
GAPFILL_PRIORITY: dict[str, int] = {"GENE3D": 0, "PRINTS": 1, "PROSITEPATTERNS": 2}
GAPFILL_MIN_OVERLAP_FRAC = 0.5


def project_to_ipr(domain_acc: str, interpro_entry_acc: str | None) -> str:
    """Return the IPR entry accession when set, else the raw signature acc.

    Single source of truth for the IPR-when-available projection used by
    every matrix builder and architecture surface. ``interpro_entry_acc``
    is stripped to tolerate stored whitespace; a blank entry falls back to
    the signature ``domain_acc``.
    """
    if interpro_entry_acc:
        stripped = interpro_entry_acc.strip()
        if stripped:
            return stripped
    return domain_acc


def _normalize_sources(sources: Sequence[str]) -> tuple[str, ...]:
    """Upper-case, deduplicated, sorted ``ref_db`` names."""
    return tuple(sorted({s.upper() for s in sources}))


def check_vocab(vocab: str) -> str:
    if vocab not in VOCABS:
        raise ValueError(f"unknown domain vocab {vocab!r}; expected one of {VOCABS}")
    return vocab


def query_sources(sources: Sequence[str], vocab: str) -> tuple[str, ...]:
    """``ref_db`` values a builder must read for ``vocab`` (upper-case, sorted)."""
    upper = set(_normalize_sources(sources))
    if check_vocab(vocab) == VOCAB_IPR_GAPFILLED:
        upper |= set(GAPFILL_PRIORITY)
    return tuple(sorted(upper))


def gapfilled_labels(
    rows: Iterable[tuple],
    *,
    sources: Sequence[str] = DEFAULT_DOMAIN_SOURCES,
) -> list[tuple]:
    """Apply the ``IPR_GAPFILLED`` rule to raw domain-hit rows.

    ``rows`` are ``(cds_key, ref_db, domain_acc, ipr_acc, dom_start, dom_end)``;
    ``cds_key`` is any hashable, orderable CDS identifier (overlap is only
    tested within one key). Hits from ``sources`` (minus the gap-fill
    databases) are always kept; a Gene3D / PRINTS / ProSitePatterns hit is
    kept only when its overlap with every already-kept hit on the CDS is
    below ``GAPFILL_MIN_OVERLAP_FRAC`` of the shorter span, visiting
    candidates by (priority, start). Labels are IPR-projected.

    Returns sorted, deduplicated ``(cds_key, dom_start, label)`` tuples.
    """
    prod_dbs = set(_normalize_sources(sources)) - set(GAPFILL_PRIORITY)
    spans: dict = defaultdict(list)
    extras: list[tuple] = []
    out: set[tuple] = set()
    for key, ref_db, acc, ipr_acc, start, end in rows:
        if not acc:
            continue
        db = (ref_db or "").upper()
        s, e = int(start or 0), int(end or 0)
        if db in prod_dbs:
            spans[key].append((s, e))
            out.add((key, s, project_to_ipr(acc, ipr_acc)))
        elif db in GAPFILL_PRIORITY:
            extras.append((key, GAPFILL_PRIORITY[db], s, e, acc, ipr_acc))

    # (priority, start) as in the benchmark; end + accession break ties
    # deterministically.
    extras.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))
    for key, _prio, s, e, acc, ipr_acc in extras:
        kept = spans[key]
        if any(_blocks(s, e, ks, ke) for ks, ke in kept):
            continue
        kept.append((s, e))
        out.add((key, s, project_to_ipr(acc, ipr_acc)))
    return sorted(out)


def _blocks(s: int, e: int, ks: int, ke: int) -> bool:
    ov = min(e, ke) - max(s, ks)
    return ov > 0 and ov >= GAPFILL_MIN_OVERLAP_FRAC * min(e - s, ke - ks)


def iter_ibgc_domain_labels(
    *,
    sources: Sequence[str] = DEFAULT_DOMAIN_SOURCES,
    ibgc_ids_subset: Sequence[int] | None = None,
    vocab: str = VOCAB_IPR_PROJECTED,
    log_name: str = "iter_ibgc_domain_labels",
) -> Iterator[tuple[int, int, int, str]]:
    """Yield ``(ibgc_id, cds_start, dom_start, label)`` for every kept domain hit.

    One contig-anchored join (see module docstring) shared by the domain and
    adjacency-pair builders. ``IPR_PROJECTED`` streams rows straight through;
    ``IPR_GAPFILLED`` buffers them (per iBGC × CDS) to apply
    :func:`gapfilled_labels`. Not deduplicated — callers dedup on the
    columns they use.
    """
    from django.db import connection

    upper_sources = _normalize_sources(sources)
    gapfill = check_vocab(vocab) == VOCAB_IPR_GAPFILLED

    sql = f"""
        SELECT i.id              AS ibgc_id,
               lower(c.cds_range)    AS cds_start,
               c.id              AS cds_id,
               d.ref_db          AS ref_db,
               d.domain_acc      AS domain_acc,
               d.interpro_entry_acc AS ipr_acc,
               d.start_position  AS dom_start,
               d.end_position    AS dom_end
        {IBGC_DOMAIN_HIT_JOIN}
        WHERE UPPER(d.ref_db) = ANY(%s::text[])
    """
    params: list = [list(query_sources(upper_sources, vocab))]
    if ibgc_ids_subset is not None:
        sql += " AND i.id = ANY(%s::bigint[])"
        params.append(list(ibgc_ids_subset))

    buffered: list[tuple] = []
    n = 0
    with connection.cursor() as cur:
        cur.execute(sql, params)
        while True:
            rows = cur.fetchmany(CHUNK)
            if not rows:
                break
            for (
                row_id,
                cds_start,
                cds_id,
                ref_db,
                acc,
                ipr_acc,
                dom_start,
                dom_end,
            ) in rows:
                if not acc:
                    continue
                n += 1
                if gapfill:
                    key = (int(row_id), int(cds_start or 0), int(cds_id))
                    buffered.append((key, ref_db, acc, ipr_acc, dom_start, dom_end))
                    continue
                yield (
                    int(row_id),
                    int(cds_start or 0),
                    int(dom_start or 0),
                    project_to_ipr(acc, ipr_acc),
                )
            if n // 1_000_000 and (n // 1_000_000) != ((n - len(rows)) // 1_000_000):
                log.info("%s: streamed %d ibgc-domain rows", log_name, n)

    if gapfill:
        kept = gapfilled_labels(buffered, sources=upper_sources)
        log.info("%s: gap-fill kept %d of %d hits", log_name, len(kept), len(buffered))
        for (row_id, cds_start, _cds_id), dom_start, label in kept:
            yield row_id, cds_start, dom_start, label


def build_ibgc_domain_matrix(
    *,
    sources: Sequence[str] = DEFAULT_DOMAIN_SOURCES,
    ibgc_ids_subset: Sequence[int] | None = None,
    domain_accs_subset: Sequence[str] | None = None,
    vocab: str = VOCAB_IPR_PROJECTED,
) -> tuple[sp.csr_matrix, np.ndarray, np.ndarray]:
    """Build the iBGC × domain-accession binary matrix.

    Parameters
    ----------
    sources:
        ``ref_db`` values to keep. Normalized to upper-case at the boundary.
    ibgc_ids_subset:
        Optional explicit list of ``IntegratedBgc.id`` values to include.
    domain_accs_subset:
        Optional column vocabulary. When supplied, columns outside this set
        are dropped; ordering is preserved.
    vocab:
        ``IPR_PROJECTED`` (default) or ``IPR_GAPFILLED``; see module docstring.

    Returns
    -------
    M : sparse CSR uint8 (n_rows × n_domain_accs)
    row_ids : np.ndarray[int64] — IntegratedBgc.id per row.
    domain_accs : np.ndarray[object] — column label per column.
    """
    import numpy as np
    import scipy.sparse as sp

    upper_sources = _normalize_sources(sources)

    pair_set: set[tuple[int, str, int]] = {
        (row_id, label, cds_start)
        for row_id, cds_start, _dom_start, label in iter_ibgc_domain_labels(
            sources=upper_sources,
            ibgc_ids_subset=ibgc_ids_subset,
            vocab=vocab,
            log_name="build_ibgc_domain_matrix",
        )
    }

    if not pair_set:
        empty = sp.csr_matrix((0, 0), dtype=np.uint8)
        return empty, np.empty(0, dtype=np.int64), np.empty(0, dtype=object)

    row_ids_unique = sorted({row_id for row_id, _, _ in pair_set})
    if domain_accs_subset is not None:
        domain_accs_unique = list(domain_accs_subset)
    else:
        domain_accs_unique = sorted({acc for _, acc, _ in pair_set})

    row_index = {r: i for i, r in enumerate(row_ids_unique)}
    col_index = {a: j for j, a in enumerate(domain_accs_unique)}

    # Project per-position dedup to per-(row, acc) binary membership.
    membership: set[tuple[int, int]] = set()
    for row_id, acc, _cds_start in pair_set:
        col = col_index.get(acc)
        if col is None:
            continue
        membership.add((row_index[row_id], col))

    rows = np.fromiter(
        (r for r, _ in membership), dtype=np.int64, count=len(membership)
    )
    cols = np.fromiter(
        (c for _, c in membership), dtype=np.int64, count=len(membership)
    )
    data = np.ones(len(membership), dtype=np.uint8)

    M = sp.csr_matrix(
        (data, (rows, cols)),
        shape=(len(row_ids_unique), len(domain_accs_unique)),
        dtype=np.uint8,
    )
    log.info(
        "build_ibgc_domain_matrix: %d rows × %d domains, nnz=%d (sources=%s vocab=%s)",
        M.shape[0],
        M.shape[1],
        M.nnz,
        upper_sources,
        vocab,
    )
    return (
        M,
        np.asarray(row_ids_unique, dtype=np.int64),
        np.asarray(domain_accs_unique, dtype=object),
    )
