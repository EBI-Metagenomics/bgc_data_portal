"""Learn the BGC-core vs flank domain enrichment table (ADR 0003).

SQL port of the 2026-10-23 benchmark's ``scripts/03_enrichment.py``. Over the
contigs of the selected assembly sources (genome catalogues — never MIBiG or
metagenomes):

* **core**  — CDS overlapping a GECCO and/or SanntiS iBGC;
* **flank** — CDS overlapping no iBGC at all, plus the *antiSMASH overhang*:
  for every antiSMASH prediction absorbed by a clusterable GECCO/SanntiS iBGC
  on different coordinates, the CDS it covers that the iBGC does not. Core
  CDS are removed from flank.

CDS of antiSMASH-only iBGCs are in neither set: they hold real clusters the
ML tools missed, so treating them as background would de-weight
antiSMASH-specialist classes (RiPPs, terpenes).

Each CDS contributes its set of domain labels (``vocab``, gap-filled by
default); ``weight = max(0.05, sigmoid(log2(p_core / p_flank)))`` with the
pseudocount split by set size — see
:func:`common_core.clustering.weights.enrichment_from_counts`. Domain-less CDS
count towards the set sizes, as in the benchmark.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from discovery.services.clustering.membership import (
    DEFAULT_DOMAIN_SOURCES,
    VOCAB_IPR_GAPFILLED,
    VOCAB_IPR_PROJECTED,
    _normalize_sources,
    gapfilled_labels,
    project_to_ipr,
    query_sources,
)

log = logging.getLogger(__name__)

CHAIN_TOOLS: tuple[str, ...] = ("GECCO", "SanntiS")
OVERHANG_TOOL = "antiSMASH"
ROLE_CORE = "core"
ROLE_FLANK = "flank"
FETCH = 50_000

# Never learn from these: MIBiG keeps the benchmark independent of the
# weights; metagenomes are the corpus the weights must transfer to.
EXCLUDED_SOURCE_PREFIXES: tuple[str, ...] = ("mibig",)
EXCLUDED_SOURCES: tuple[str, ...] = ("MGnify_Assemblies_v5",)


@dataclass
class EnrichmentCounts:
    """Per-label CDS counts for one enrichment build."""

    n_core: int = 0
    n_flank: int = 0
    core: Counter = field(default_factory=Counter)
    flank: Counter = field(default_factory=Counter)

    def table(self) -> list[tuple[str, int, int, float]]:
        """``(label, n_core, n_flank, weight)`` rows, sorted by label."""
        from common_core.clustering.weights import enrichment_from_counts

        labels = sorted(set(self.core) | set(self.flank))
        w = enrichment_from_counts(
            [self.core[x] for x in labels],
            [self.flank[x] for x in labels],
            self.n_core,
            self.n_flank,
        )
        return [
            (label, int(self.core[label]), int(self.flank[label]), float(wi))
            for label, wi in zip(labels, w.tolist())
        ]


def check_datasets(datasets: Sequence[str]) -> tuple[str, ...]:
    """Reject sources the enrichment must never be learned on."""
    bad = [
        d
        for d in datasets
        if d in EXCLUDED_SOURCES
        or any(d.lower().startswith(p) for p in EXCLUDED_SOURCE_PREFIXES)
    ]
    if bad:
        raise ValueError(
            f"enrichment must not be learned on {bad}: MIBiG and metagenomes "
            "are excluded (ADR 0003)"
        )
    if not datasets:
        raise ValueError("no datasets given")
    return tuple(datasets)


def count_cds_labels(
    rows: Iterable[tuple],
    *,
    sources: Sequence[str] = DEFAULT_DOMAIN_SOURCES,
    vocab: str = VOCAB_IPR_GAPFILLED,
    counts: EnrichmentCounts | None = None,
) -> EnrichmentCounts:
    """Add per-CDS label sets to ``counts``.

    ``rows`` are ``(cds_id, role, ref_db, domain_acc, ipr_acc, dom_start,
    dom_end)`` **grouped by cds_id** (one CDS's hits contiguous). Only label
    counts are updated; the set sizes ``n_core`` / ``n_flank`` come from the
    CDS universe, which includes CDS without hits.
    """
    counts = counts if counts is not None else EnrichmentCounts()
    upper_sources = _normalize_sources(sources)
    prod = set(upper_sources)

    def _flush(role: str | None, hits: list[tuple]) -> None:
        if not hits:
            return
        if vocab == VOCAB_IPR_GAPFILLED:
            labels = {label for _, _, label in gapfilled_labels(hits, sources=prod)}
        else:
            labels = {
                project_to_ipr(acc, ipr)
                for _, db, acc, ipr, _, _ in hits
                if acc and (db or "").upper() in prod
            }
        (counts.core if role == ROLE_CORE else counts.flank).update(labels)

    current, role, hits = None, None, []
    for cds_id, r, ref_db, acc, ipr_acc, start, end in rows:
        if cds_id != current:
            _flush(role, hits)
            current, role, hits = cds_id, r, []
        hits.append((cds_id, ref_db, acc, ipr_acc, start, end))
    _flush(role, hits)
    return counts


_ROLE_SQL = """
    CREATE TEMP TABLE _enrich_cds ON COMMIT DROP AS
    WITH ctg AS (
        SELECT c.id
        FROM discovery_contig c
        JOIN discovery_assembly a ON a.id = c.assembly_id
        JOIN discovery_assembly_source s ON s.id = a.source_id
        WHERE s.name = ANY(%(datasets)s::text[])
    ),
    ibgc AS (
        SELECT i.id, i.contig_id, i.bgc_range, i.source_tools
        FROM discovery_ibgc i
        WHERE i.contig_id IN (SELECT id FROM ctg)
    ),
    chain AS (
        SELECT * FROM ibgc WHERE source_tools ?| %(chain_tools)s::text[]
    ),
    cds AS (
        SELECT x.id, x.contig_id, x.cds_range
        FROM discovery_cds x
        WHERE x.contig_id IN (SELECT id FROM ctg)
    ),
    core AS (
        SELECT DISTINCT x.id
        FROM cds x
        JOIN chain ch ON ch.contig_id = x.contig_id AND ch.bgc_range && x.cds_range
    ),
    in_any AS (
        SELECT DISTINCT x.id
        FROM cds x
        JOIN ibgc i ON i.contig_id = x.contig_id AND i.bgc_range && x.cds_range
    ),
    shadow AS (
        SELECT p.contig_id, p.bgc_range AS p_range, ch.bgc_range AS ch_range
        FROM discovery_source_bgc p
        JOIN discovery_detector d ON d.id = p.detector_id
        JOIN chain ch ON ch.id = p.integrated_bgc_id
        WHERE d.tool = %(overhang_tool)s
          AND p.bgc_range <> ch.bgc_range
          AND EXISTS (
              SELECT 1 FROM discovery_source_bgc q
              WHERE q.integrated_bgc_id = ch.id
                AND (NOT q.is_partial OR q.is_validated)
          )
    ),
    overhang AS (
        SELECT DISTINCT x.id
        FROM cds x
        JOIN shadow sh
          ON sh.contig_id = x.contig_id
         AND sh.p_range && x.cds_range
         AND NOT (sh.ch_range && x.cds_range)
    ),
    flank AS (
        ((SELECT id FROM cds EXCEPT SELECT id FROM in_any)
         UNION SELECT id FROM overhang)
        EXCEPT SELECT id FROM core
    )
    SELECT id AS cds_id, %(core)s::text AS role FROM core
    UNION ALL
    SELECT id, %(flank)s::text FROM flank
"""

_HITS_SQL = """
    SELECT r.cds_id, r.role, h.ref_db, h.domain_acc, h.interpro_entry_acc,
           h.start_position, h.end_position
    FROM _enrich_cds r
    JOIN discovery_domain_hit h ON h.cds_id = r.cds_id
    WHERE UPPER(h.ref_db) = ANY(%s::text[])
    ORDER BY r.cds_id
"""


def build_enrichment_counts(
    *,
    datasets: Sequence[str],
    sources: Sequence[str] = DEFAULT_DOMAIN_SOURCES,
    vocab: str = VOCAB_IPR_GAPFILLED,
) -> EnrichmentCounts:
    """Classify CDS as core / flank in SQL and count labels per set."""
    from django.db import connection, transaction

    if vocab not in (VOCAB_IPR_PROJECTED, VOCAB_IPR_GAPFILLED):
        raise ValueError(f"unsupported vocab {vocab!r}")
    datasets = check_datasets(datasets)
    upper_sources = _normalize_sources(sources)

    counts = EnrichmentCounts()
    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute(
                _ROLE_SQL,
                {
                    "datasets": list(datasets),
                    "chain_tools": list(CHAIN_TOOLS),
                    "overhang_tool": OVERHANG_TOOL,
                    "core": ROLE_CORE,
                    "flank": ROLE_FLANK,
                },
            )
            cur.execute("SELECT role, count(*) FROM _enrich_cds GROUP BY role")
            sizes = dict(cur.fetchall())
        counts.n_core = int(sizes.get(ROLE_CORE, 0))
        counts.n_flank = int(sizes.get(ROLE_FLANK, 0))
        log.info(
            "enrichment: datasets=%s core CDS=%d flank CDS=%d",
            datasets,
            counts.n_core,
            counts.n_flank,
        )
        if not counts.n_core or not counts.n_flank:
            raise ValueError(
                f"empty core ({counts.n_core}) or flank ({counts.n_flank}) set "
                f"for datasets {datasets}"
            )

        # Server-side cursor: the hit stream can run to 10^8 rows on prod.
        raw = connection.connection
        with raw.cursor(name="enrich_hits") as cur:
            cur.itersize = FETCH
            cur.execute(_HITS_SQL, [list(query_sources(upper_sources, vocab))])
            count_cds_labels(cur, sources=upper_sources, vocab=vocab, counts=counts)
    log.info(
        "enrichment: %d labels (core %d, flank %d)",
        len(set(counts.core) | set(counts.flank)),
        len(counts.core),
        len(counts.flank),
    )
    return counts


def save_enrichment_table(
    version: str,
    counts: EnrichmentCounts,
    *,
    vocab: str,
    datasets: Sequence[str],
) -> int:
    """Persist ``counts`` as ``DomainEnrichment`` rows; versions are immutable.

    ``vocab`` / ``datasets`` must be what ``counts`` was built with; they are
    recorded on every row so a clustering run can refuse a version learned on
    a different vocabulary.
    """
    from django.db import transaction

    from discovery.models import DomainEnrichment

    if DomainEnrichment.objects.filter(version=version).exists():
        raise ValueError(
            f"DomainEnrichment version {version!r} already exists; versions are "
            "frozen — build a new one"
        )
    datasets = sorted(check_datasets(datasets))
    rows = [
        DomainEnrichment(
            version=version,
            vocab=vocab,
            datasets=datasets,
            label=label,
            n_core=nc,
            n_flank=nf,
            weight=w,
        )
        for label, nc, nf, w in counts.table()
    ]
    with transaction.atomic():
        DomainEnrichment.objects.bulk_create(rows, batch_size=5_000)
    log.info("Saved DomainEnrichment version=%s (%d labels)", version, len(rows))
    return len(rows)
