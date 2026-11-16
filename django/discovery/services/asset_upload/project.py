"""Project parsed asset data onto the latest ClusteringRun.

Pipeline:

1. Walk asset BGCs per contig and apply the canonical overlap-chain rules
   (validated standalones, GECCO+SanntiS chains, antiSMASH absorb-or-emit)
   via the shared :func:`integrated._build_ibgcs_for_contig`. Each
   resulting iBGC gets a negative integer id and is materialised as a
   ``VirtualIbgc`` carrying its member BGCs, CDS rows, domains, and NPs.

2. Load the most recent ``ClusteringRun``'s scoring cache from disk —
   primary domain matrix, primary adjacency-pair matrix, vocabularies,
   per-row leaf paths.

3. Build the asset's domain + adjacency-pair matrices on the same column
   space (and label vocabulary) as the run, score them against the primary
   matrices with the run's similarity metric and persisted feature weights
   (ADR 0003), take the top-K nearest primary neighbours per virtual iBGC
   and compute:

   * ``gene_cluster_family`` — weighted-vote leaf path of the K neighbours
   * ``novelty_score``       — ``1 − max(sim to validated primary iBGC)``
   * ``domain_novelty``      — fraction of this iBGC's domains not present
     in any primary member of the inherited leaf GCF

   iBGCs without any source-vocabulary overlap keep ``None``/``""`` for the
   three quantities — they still appear in the roster, just dimmed on the
   Variables map.

4. Materialise per-iBGC cache payloads (manifest, roster rows, IbgcDetail,
   region, architecture) under the ``asset:{token}:*`` keyspace.
"""

from __future__ import annotations

import base64
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from django.conf import settings

from discovery.services.go_slim import go_slim_for_terms
from discovery.services.ingestion.edge_partial import is_edge_partial

from . import cache as asset_cache
from .matrices import (
    DEFAULT_DOMAIN_SOURCES,
    build_asset_adjacency_pair_matrix,
    build_asset_domain_matrix,
)
from .schemas import (
    AssetBgc,
    AssetCds,
    AssetData,
    AssetDomain,
)

log = logging.getLogger(__name__)

KNN_K = 5
# Fallback only: the run's ``min_projection_similarity`` applies (it is
# metric-specific); 0.1 is what every Dice run uses.
MIN_TOTAL_SIMILARITY = 0.1


@dataclass
class VirtualIbgc:
    """One ephemeral iBGC built from the asset, with everything its detail /
    region / architecture payloads need pre-joined."""

    neg_id: int  # negative integer id (-1, -2, …)
    contig_sha256: str
    contig_accession: str
    assembly_accession: str
    organism_name: str
    is_type_strain: bool
    start_position: int
    end_position: int
    source_tools: list[str]
    member_bgcs: list[AssetBgc]
    is_partial: bool
    is_validated: bool
    cds: list[AssetCds] = field(default_factory=list)
    domains: list[AssetDomain] = field(default_factory=list)

    # Derived during projection
    projected: bool = False
    novelty_score: float | None = None
    domain_novelty: float | None = None
    gene_cluster_family: str = ""

    @property
    def size_kb(self) -> float:
        return round((self.end_position - self.start_position) / 1000.0, 3)

    @property
    def label(self) -> str:
        return f"iBGC-A{abs(self.neg_id)}"


# ── Step 1: build virtual iBGCs from asset rows ─────────────────────────────


def build_virtual_ibgcs(data: AssetData) -> list[VirtualIbgc]:
    """Return the asset's virtual iBGCs with negative ids assigned.

    Reuses the canonical overlap-chain algorithm from
    :func:`discovery.services.clustering.integrated._build_ibgcs_for_contig`
    by giving each asset BGC a transient positive integer id, mapping back
    after the chains are formed.
    """
    from discovery.services.clustering.integrated import (
        _build_ibgcs_for_contig,
    )

    asm_lookup = data.assembly_lookup()
    contig_lookup = data.contig_lookup()
    detector_tool = {d.name: d.tool for d in data.detectors}
    bgcs_by_contig = data.bgcs_by_contig()
    cds_by_bgc = data.cds_by_bgc()
    domains_by_bgc = data.domains_by_bgc()

    virtual: list[VirtualIbgc] = []
    next_neg_id = -1

    for contig_sha, bgcs in bgcs_by_contig.items():
        contig = contig_lookup.get(contig_sha)
        if contig is None:
            continue
        assembly = asm_lookup.get(contig.assembly_accession)
        organism = assembly.organism_name if assembly else ""
        is_type_strain = bool(assembly.is_type_strain) if assembly else False

        # Build rows shaped like the persistent path expects, using array
        # indices as transient bgc_ids so we can map back to the source rows.
        # Row format mirrors integrated._build_ibgcs_for_contig:
        # (sbgc_id, cbgc_id, start, end, tool, is_partial, is_validated, contig_accession).
        # The helper ignores cbgc_id and contig_accession, so we pass placeholders.
        id_to_bgc: dict[int, AssetBgc] = dict(enumerate(bgcs))
        # Contig-edge flags: the uploaded ``is_partial`` is replaced by the
        # gene-margin rule the persistent path applies (mark_edge_partials),
        # over every uploaded CDS on this contig.
        gene_spans = {
            (c.start_position, c.end_position)
            for b in bgcs
            for c in cds_by_bgc.get(b.key, [])
        }
        for b in bgcs:
            b.is_partial = is_edge_partial(
                start=b.start_position,
                end=b.end_position,
                contig_length=contig.length,
                gene_spans=gene_spans,
                validated=b.is_validated,
            )
        rows = [
            (
                i,
                0,  # cbgc_id — unused by the helper
                b.start_position,
                b.end_position,
                detector_tool.get(b.detector_name, ""),
                b.is_partial,
                b.is_validated,
                contig.accession or "",  # contig_accession — unused by the helper
            )
            for i, b in id_to_bgc.items()
        ]
        ibgc_tuples, _absorbed, _validated_standalones = _build_ibgcs_for_contig(rows)

        for (
            interval_start,
            interval_end,
            source_tools,
            member_ids,
            absorbed_ids,
        ) in ibgc_tuples:
            # Absorbed antiSMASH predictions share the iBGC FK in the
            # persistent path, so fold them in as members here too — their
            # CDS / domains belong to this virtual iBGC.
            members = [id_to_bgc[i] for i in (*member_ids, *absorbed_ids)]
            cds_rows: list[AssetCds] = []
            dom_rows: list[AssetDomain] = []
            for b in members:
                bcds = cds_by_bgc.get(b.key, [])
                cds_rows.extend(bcds)
                dom_rows.extend(domains_by_bgc.get(b.key, []))

            is_partial = all(m.is_partial for m in members) and not any(
                m.is_validated for m in members
            )
            is_validated = any(m.is_validated for m in members)

            vibgc = VirtualIbgc(
                neg_id=next_neg_id,
                contig_sha256=contig_sha,
                contig_accession=contig.accession,
                assembly_accession=contig.assembly_accession,
                organism_name=organism,
                is_type_strain=is_type_strain,
                start_position=interval_start,
                end_position=interval_end,
                source_tools=sorted(source_tools),
                member_bgcs=members,
                is_partial=is_partial,
                is_validated=is_validated,
                cds=cds_rows,
                domains=dom_rows,
            )
            virtual.append(vibgc)
            next_neg_id -= 1

    log.info("build_virtual_ibgcs: built %d virtual iBGCs", len(virtual))
    return virtual


# ── Step 2: load primary scoring cache + Step 3: project ───────────────────


def _latest_clustering_run():
    """Return the most-recent ``ClusteringRun`` or ``None`` if none exist."""
    from discovery.models import ClusteringRun

    return ClusteringRun.objects.order_by("-created_at").first()


class LeafColumnSums:
    """Lazy, memoised per-leaf column sums of the primary domain matrix.

    ``get(leaf)`` returns the 1-D column-sum vector over the primary rows whose
    leaf path is ``leaf`` (or ``None`` for an unknown / empty leaf). Only the
    leaves actually requested are ever summed, so memory scales with the number
    of distinct leaves an upload lands in, not with the size of the run.
    """

    def __init__(self, M_domains, leaf_paths) -> None:
        self._M = M_domains.tocsr() if hasattr(M_domains, "tocsr") else M_domains
        self._rows: dict[str, list[int]] = defaultdict(list)
        for i, p in enumerate(leaf_paths):
            if p:
                self._rows[p].append(i)
        self._cache: dict[str, Any] = {}

    def get(self, leaf: str | None):
        if not leaf:
            return None
        if leaf in self._cache:
            return self._cache[leaf]
        rows = self._rows.get(leaf)
        if not rows:
            return None
        import numpy as np

        sums = np.asarray(self._M[rows].sum(axis=0)).reshape(-1)
        self._cache[leaf] = sums
        return sums

    @property
    def n_computed(self) -> int:
        return len(self._cache)


def _project_against_run(
    virtual_ibgcs: list[VirtualIbgc],
    run,
) -> None:
    """Fill ``gene_cluster_family``, ``novelty_score`` and ``domain_novelty``
    on each virtual iBGC by KNN-projecting against the primary iBGCs of
    ``run``.

    Mutates ``virtual_ibgcs`` in place. Virtual iBGCs with no source-vocab
    overlap with the primary matrix are left unprojected (the three fields
    stay at their default ``None`` / ``""``).
    """
    if not virtual_ibgcs:
        return

    import numpy as np

    from discovery.models import SourceBgcPrediction
    from discovery.services.clustering.bgc_similarity import (
        compute_composite_similarity_block,
    )
    from discovery.services.clustering.ibgc_scoring import load_scoring_cache

    sources = tuple(run.domain_sources) or DEFAULT_DOMAIN_SOURCES
    weights = tuple(run.score_weights) if run.score_weights else (0.5, 0.5)
    artifacts_dir = settings.CLUSTERING_ARTIFACTS_DIR / run.sha256[:12]

    try:
        cache_payload = load_scoring_cache(artifacts_dir)
    except FileNotFoundError as exc:
        log.warning(
            "Scoring cache missing at %s — virtual iBGCs cannot be projected (%s)",
            artifacts_dir,
            exc,
        )
        return

    metric = run.similarity_metric or "dice"
    if cache_payload.get("similarity_metric", "dice") != metric:
        log.warning(
            "Scoring cache at %s was written for %r but the run uses %r — "
            "virtual iBGCs cannot be projected until it is rebuilt",
            artifacts_dir,
            cache_payload.get("similarity_metric"),
            metric,
        )
        return
    min_total_similarity = getattr(run, "min_projection_similarity", None)
    if min_total_similarity is None:
        min_total_similarity = MIN_TOTAL_SIMILARITY
    vocab = run.domain_vocab or "IPR_PROJECTED"

    M_dom_pri = cache_payload["M_domains"]
    M_pair_pri = cache_payload["M_pairs"]
    pri_row_ids = cache_payload["ibgc_ids"]
    dom_accs = cache_payload["domain_accs"].tolist()
    pair_vocab = cache_payload["pair_vocab"].tolist()
    pri_leaf_paths = list(cache_payload["leaf_paths"])
    n_primary = M_dom_pri.shape[0]

    if n_primary == 0:
        log.warning("Scoring cache has no primary rows — skipping projection")
        return

    pri_id_to_row = {int(x): i for i, x in enumerate(pri_row_ids.tolist())}

    validated_ibgc_ids = set(
        SourceBgcPrediction.objects.filter(
            is_validated=True, integrated_bgc__isnull=False
        ).values_list("integrated_bgc_id", flat=True)
    )
    validated_col_set = {
        pri_id_to_row[v] for v in validated_ibgc_ids if v in pri_id_to_row
    }

    # Per-leaf domain column sums, computed lazily for the leaves the asset
    # rows actually inherit. Materialising them for every leaf is
    # n_leaves × n_domain_cols dense — ~9.4 GiB for the 2026-10 prod run
    # (57k leaves × 22k cols, uint64) — which OOM-killed the worker on every
    # upload regardless of upload size.
    leaf_col_sums = LeafColumnSums(M_dom_pri, pri_leaf_paths)

    # Build asset matrices on the primary's column space.
    M_dom_q = build_asset_domain_matrix(
        virtual_ibgcs, sources=sources, domain_accs=dom_accs, vocab=vocab
    )
    M_pair_q = build_asset_adjacency_pair_matrix(
        virtual_ibgcs, sources=sources, pair_vocab=pair_vocab, vocab=vocab
    )

    # Score the asset rows against the (large, fixed) primary set directly.
    # Stacking under the primary matrix and running the full self-similarity
    # would recompute the entire n_primary² primary block — already cached from
    # the clustering run and irrelevant here — on every upload. The asset set is
    # tiny, so we compute only the (n_asset × n_primary) block.
    sim_block = compute_composite_similarity_block(
        M_dom_q,
        M_dom_pri,
        M_pair_q,
        M_pair_pri,
        weights=weights,
        metric=metric,
        domain_weights=cache_payload.get("domain_weights"),
        pair_weights=cache_payload.get("pair_weights"),
    )
    M_dom_q_csr = M_dom_q.tocsr()

    for q_row, vibgc in enumerate(virtual_ibgcs):
        sp_start = sim_block.indptr[q_row]
        sp_end = sim_block.indptr[q_row + 1]
        if sp_start == sp_end:
            continue
        cols = sim_block.indices[sp_start:sp_end]
        vals = sim_block.data[sp_start:sp_end]
        order = np.argsort(-vals)[:KNN_K]
        top_cols = cols[order]
        top_vals = vals[order]
        top_sum = float(top_vals.sum())
        if top_sum < min_total_similarity:
            continue

        vibgc.projected = True

        votes: Counter[str] = Counter()
        for col, val in zip(top_cols.tolist(), top_vals.tolist()):
            leaf = pri_leaf_paths[col]
            if leaf:
                votes[leaf] += float(val)
        if votes:
            vibgc.gene_cluster_family = votes.most_common(1)[0][0]

        # Novelty against validated primary cols inside this row's non-zeros.
        if validated_col_set:
            max_sim_validated = 0.0
            for col, val in zip(cols.tolist(), vals.tolist()):
                if col in validated_col_set and val > max_sim_validated:
                    max_sim_validated = float(val)
            vibgc.novelty_score = 1.0 - max_sim_validated

        # Domain novelty against the inherited leaf GCF.
        q_dom_start = M_dom_q_csr.indptr[q_row]
        q_dom_end = M_dom_q_csr.indptr[q_row + 1]
        n_dom = int(q_dom_end - q_dom_start)
        if n_dom and vibgc.gene_cluster_family:
            col_sums_L = leaf_col_sums.get(vibgc.gene_cluster_family)
            if col_sums_L is not None:
                domain_cols = M_dom_q_csr.indices[q_dom_start:q_dom_end]
                n_unique = int((col_sums_L[domain_cols] == 0).sum())
                vibgc.domain_novelty = n_unique / n_dom


# ── Step 4: materialise cache payloads ─────────────────────────────────────


def _ordered_architecture(vibgc: VirtualIbgc, sources: tuple[str, ...]) -> list[dict]:
    """Pooled positional architecture across all member BGCs of the virtual iBGC.

    Mirrors :func:`discovery.services.architecture.ibgc_architecture` but
    walks the in-memory rows.
    """
    upper_sources = tuple(s.upper() for s in sources)
    cds_start_by_id: dict[tuple[tuple[str, int, int, str], str], int] = {}
    for cds in vibgc.cds:
        cds_start_by_id[(cds.bgc_key, cds.protein_id_str)] = cds.start_position

    from discovery.services.architecture import _interpro_url

    seen: set[tuple[int, int, str]] = set()
    ordered: list[tuple[int, int, dict]] = []
    for d in vibgc.domains:
        if not d.domain_acc:
            continue
        if d.ref_db and d.ref_db.upper() not in upper_sources:
            continue
        cds_start = cds_start_by_id.get((d.bgc_key, d.cds_protein_id))
        if cds_start is None:
            continue
        ipr_acc = (d.interpro_entry_acc or "").strip()
        if ipr_acc:
            projected = {
                "domain_acc": ipr_acc,
                "domain_name": d.interpro_entry_description or d.domain_name,
                "ref_db": "InterPro",
                "url": _interpro_url(ipr_acc),
                "start": 0,
                "end": 0,
                "score": None,
                "go_slim": go_slim_for_terms(d.go_terms),
            }
        else:
            projected = {
                "domain_acc": d.domain_acc,
                "domain_name": d.domain_name,
                "ref_db": d.ref_db,
                "url": d.url,
                "start": 0,
                "end": 0,
                "score": None,
                "go_slim": go_slim_for_terms(d.go_terms),
            }
        key = (cds_start, d.start_position, projected["domain_acc"])
        if key in seen:
            continue
        seen.add(key)
        ordered.append((cds_start, d.start_position, projected))
    ordered.sort(key=lambda t: (t[0], t[1], t[2]["domain_acc"]))
    return [t[2] for t in ordered]


def _roster_row(vibgc: VirtualIbgc) -> dict[str, Any]:
    return {
        "id": vibgc.neg_id,
        "label": vibgc.label,
        "classification_path": vibgc.gene_cluster_family,
        "size_kb": vibgc.size_kb,
        "n_source_bgcs": len(vibgc.member_bgcs),
        "source_tools": vibgc.source_tools,
        "novelty_score": vibgc.novelty_score,
        "domain_novelty": vibgc.domain_novelty,
        "is_partial": vibgc.is_partial,
        "is_validated": vibgc.is_validated,
        "is_type_strain": vibgc.is_type_strain,
        "parent_assembly_id": None,
        "parent_assembly_accession": vibgc.assembly_accession,
        "organism_name": vibgc.organism_name,
        "contig_accession": vibgc.contig_accession,
        "similarity_score": None,
        "best_hit_protein_id": None,
        "best_pident": None,
        "best_qcoverage": None,
        "is_asset": True,
    }


def _ibgc_detail(vibgc: VirtualIbgc, sources: tuple[str, ...]) -> dict[str, Any]:
    member_items = [
        {
            "id": -idx - 1,  # synthetic, scoped to this asset iBGC
            "accession": f"{vibgc.label}.{idx + 1}",
            "detector_name": m.detector_name,
            "is_partial": m.is_partial,
            "is_validated": m.is_validated,
            "size_kb": m.size_kb,
        }
        for idx, m in enumerate(vibgc.member_bgcs)
    ]
    parent_assembly = {
        "assembly_id": None,
        "accession": vibgc.assembly_accession,
        "organism_name": vibgc.organism_name,
        "source_name": None,
        "is_type_strain": vibgc.is_type_strain,
        "url": "",
    }
    return {
        "id": vibgc.neg_id,
        "label": vibgc.label,
        "classification_path": vibgc.gene_cluster_family,
        "size_kb": vibgc.size_kb,
        "start_position": vibgc.start_position,
        "end_position": vibgc.end_position,
        "contig_accession": vibgc.contig_accession,
        "source_tools": vibgc.source_tools,
        "novelty_score": vibgc.novelty_score,
        "domain_novelty": vibgc.domain_novelty,
        "is_partial": vibgc.is_partial,
        "is_validated": vibgc.is_validated,
        "is_type_strain": vibgc.is_type_strain,
        "parent_assembly": parent_assembly,
        # Use the iBGC's own negative id as the representative — the region
        # endpoint resolves it back through asset_cache.read_region(token, id).
        "representative_bgc_id": vibgc.neg_id if vibgc.member_bgcs else None,
        "member_bgcs": member_items,
        "domain_architecture": _ordered_architecture(vibgc, sources),
    }


def _region_payload(vibgc: VirtualIbgc) -> dict[str, Any]:
    """Region payload matching ``BgcRegionOut`` for the asset iBGC.

    Coordinates are translated to be relative to the iBGC interval, like the
    persistent region view does for IntegratedBgc rows.
    """
    window_start = vibgc.start_position
    region_length = vibgc.end_position - vibgc.start_position

    cds_list = []
    domain_list: list[dict[str, Any]] = []
    domains_by_cds_pid: dict[
        tuple[tuple[str, int, int, str], str], list[AssetDomain]
    ] = defaultdict(list)
    for d in vibgc.domains:
        domains_by_cds_pid[(d.bgc_key, d.cds_protein_id)].append(d)

    from discovery.services.architecture import collapse_to_interpro_rows

    for cds in vibgc.cds:
        sequence = ""
        if cds.sequence_zlib_b64:
            try:
                import zlib

                sequence = zlib.decompress(
                    base64.b64decode(cds.sequence_zlib_b64)
                ).decode("ascii", errors="replace")
            except Exception:  # noqa: BLE001
                sequence = ""

        cds_domains = domains_by_cds_pid.get((cds.bgc_key, cds.protein_id_str), [])
        interpro = collapse_to_interpro_rows(
            cds_domains, slim_for=lambda d: go_slim_for_terms(d.go_terms)
        )

        pfam = []
        for d in cds_domains:
            slim = go_slim_for_terms(d.go_terms)
            pfam.append(
                {
                    "accession": d.domain_acc,
                    "description": d.domain_description or d.domain_name,
                    "go_slim": slim,
                    "envelope_start": d.start_position,
                    "envelope_end": d.end_position,
                    "e_value": str(d.score) if d.score is not None else None,
                    "url": d.url,
                }
            )
            # RegionPlot.tsx builds the per-CDS dominant-slim colouring map
            # off `domain_list` only — it never reads cds_list[*].pfam. AA→NT
            # conversion mirrors _build_bgc_region_data so the strand handling
            # stays consistent with the persistent path.
            if cds.strand >= 0:
                dom_nt_start = cds.start_position + d.start_position * 3
                dom_nt_end = cds.start_position + d.end_position * 3
            else:
                dom_nt_start = cds.end_position - d.end_position * 3
                dom_nt_end = cds.end_position - d.start_position * 3
            domain_list.append(
                {
                    "accession": d.domain_acc,
                    "description": d.domain_description or d.domain_name or "",
                    "start": max(0, dom_nt_start - window_start),
                    "end": max(0, dom_nt_end - window_start),
                    "strand": cds.strand,
                    "score": d.score,
                    "go_slim": list(slim),
                    "parent_cds_id": cds.protein_id_str,
                    "url": d.url or "",
                }
            )

        cds_list.append(
            {
                "protein_id": cds.protein_id_str,
                "start": cds.start_position - window_start,
                "end": cds.end_position - window_start,
                "strand": cds.strand,
                "protein_length": cds.protein_length,
                "gene_caller": cds.gene_caller,
                "cluster_representative": cds.cluster_representative or None,
                "cluster_representative_url": None,
                "sequence": sequence,
                "pfam": pfam,
                "interpro": interpro,
            }
        )

    cluster_list = [
        {
            "accession": f"{vibgc.label}.{idx + 1}",
            "start": m.start_position - window_start,
            "end": m.end_position - window_start,
            "source": m.detector_name,
            "bgc_classes": (
                [m.classification_path.split(".", 1)[0]]
                if m.classification_path
                else []
            ),
        }
        for idx, m in enumerate(vibgc.member_bgcs)
    ]

    return {
        "region_length": region_length,
        "window_start": 0,
        "window_end": region_length,
        "cds_list": cds_list,
        "domain_list": domain_list,
        "cluster_list": cluster_list,
    }


# ── Top-level entry point ──────────────────────────────────────────────────


def project_asset(token: str, data: AssetData, *, task_id: str = "") -> dict[str, Any]:
    """Run the full asset projection and materialise cache payloads.

    Returns a summary dict (mirrored into the task status payload).
    """
    virtual_ibgcs = build_virtual_ibgcs(data)
    if not virtual_ibgcs:
        raise ValueError("No iBGCs could be built from the upload")

    run = _latest_clustering_run()
    if run is not None:
        _project_against_run(virtual_ibgcs, run)
    else:
        log.warning(
            "project_asset: no ClusteringRun present — iBGCs persisted unprojected"
        )

    sources = tuple(run.domain_sources) if run else DEFAULT_DOMAIN_SOURCES

    roster_rows = [_roster_row(v) for v in virtual_ibgcs]
    asset_cache.write_ibgc_list(token, roster_rows)

    # Flat per-iBGC-deduped domain-hit list for the report builder. Mirrors
    # the SQL ``domain_pairs`` set semantics at services/report.py:154.
    domain_hits: list[dict[str, Any]] = []
    for vibgc in virtual_ibgcs:
        seen_accs: set[str] = set()
        for d in vibgc.domains:
            if not d.domain_acc or d.domain_acc in seen_accs:
                continue
            seen_accs.add(d.domain_acc)
            domain_hits.append(
                {
                    "ibgc_id": vibgc.neg_id,
                    "domain_acc": d.domain_acc,
                    "domain_name": d.domain_name,
                    "domain_description": d.domain_description or d.domain_name,
                    "go_slim": go_slim_for_terms(d.go_terms),
                    "interpro_entry_acc": (d.interpro_entry_acc or "").strip(),
                    "interpro_entry_description": d.interpro_entry_description or "",
                    "ref_db": d.ref_db or "",
                }
            )
    asset_cache.write_domain_hits(token, domain_hits)

    for vibgc in virtual_ibgcs:
        detail = _ibgc_detail(vibgc, sources)
        region = _region_payload(vibgc)
        architecture = [d["domain_acc"] for d in detail["domain_architecture"]]
        asset_cache.write_ibgc_detail(token, vibgc.neg_id, detail)
        asset_cache.write_region(token, vibgc.neg_id, region)
        asset_cache.write_architecture(token, vibgc.neg_id, architecture)

    first = virtual_ibgcs[0]
    summary = {
        "token": token,
        "uploaded_at": datetime.now(UTC).isoformat(),
        "n_ibgcs": len(virtual_ibgcs),
        "n_bgcs": sum(len(v.member_bgcs) for v in virtual_ibgcs),
        "assembly_accession": first.assembly_accession,
        "organism": first.organism_name,
        "source_label": ", ".join(
            sorted({b.detector_name for v in virtual_ibgcs for b in v.member_bgcs})
        ),
        "clustering_run_id": run.id if run is not None else None,
        "projected": run is not None,
        "n_projected": sum(1 for v in virtual_ibgcs if v.projected),
    }
    asset_cache.write_manifest(token, summary)
    asset_cache.mark_success(token, task_id=task_id, summary=summary)
    log.info(
        "project_asset: token=%s n_ibgcs=%d projected=%d",
        token,
        len(virtual_ibgcs),
        summary["n_projected"],
    )
    return summary
