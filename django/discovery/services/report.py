"""Shortlist Report payload builder.

Stateless: given a list of iBGC ids, return a ready-to-render dict with all
the panels the Report Page needs (iBGC rows, domain composition, GCF
distribution, score distributions, completeness pie, BGC class pie, length
histogram, predictor distribution, assembly roster, assembly stats).

The endpoint layer caches the payload in Redis keyed by ``sha256(sorted ids)``
so reloading the report page is cheap. Nothing is persisted to the DB.

Per the v2 schema, the operational unit is ``IntegratedBgc`` and per-iBGC
domain pooling joins through ``ContigDomain → ContigCds → IntegratedBgc``
via ``contig`` + ``bgc_range && cds_range`` overlap.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import timedelta

from discovery.models import (
    DashboardAssembly,
    DashboardContig,
    IntegratedBgc,
    SourceBgcPrediction,
)
from django.db import connection
from django.utils import timezone

log = logging.getLogger(__name__)

REPORT_TTL_SECONDS = 86_400  # 24h Redis TTL
MAX_SHORTLIST = 1000

# Tier thresholds for the Domain Composition stacked-bar.
CORE_FRACTION = 0.8
VARIABLE_FRACTION = 0.4

# Length-histogram buckets (kb).
LENGTH_BUCKETS: list[tuple[float, float, str]] = [
    (0, 10, "<10 kb"),
    (10, 20, "10–20"),
    (20, 40, "20–40"),
    (40, 80, "40–80"),
    (80, 160, "80–160"),
    (160, float("inf"), "≥160"),
]

# Score-histogram sampling cap (avoid blowing the payload up for huge lists).
SCORE_SAMPLE_CAP = 500


def _taxonomy_phylum(taxonomy_path: str | None) -> str | None:
    if not taxonomy_path:
        return None
    parts = taxonomy_path.split(".")
    return parts[1] if len(parts) >= 2 else parts[0]


def _is_partial(ibgc: IntegratedBgc) -> bool:
    return bool(ibgc.umap_projected) or ibgc.classification_run_id is None


def _fetch_domain_rows_for_ibgcs(ibgc_ids: list[int]) -> list[tuple]:
    """Return ``(ibgc_id, domain_acc, domain_name, domain_description, go_slim)``.

    One row per ``ContigDomain`` whose parent CDS's ``cds_range`` overlaps
    an iBGC's ``bgc_range`` on the same contig.
    """
    if not ibgc_ids:
        return []
    sql = """
        SELECT i.id              AS ibgc_id,
               cd.domain_acc     AS domain_acc,
               cd.domain_name    AS domain_name,
               cd.domain_description AS domain_description,
               cd.go_slim        AS go_slim
        FROM discovery_domain_hit cd
        JOIN discovery_cds cc ON cc.id = cd.cds_id
        JOIN discovery_ibgc i
          ON i.contig_id = cc.contig_id
         AND i.bgc_range && cc.cds_range
        WHERE i.id = ANY(%s::bigint[])
    """
    with connection.cursor() as cur:
        cur.execute(sql, [list(ibgc_ids)])
        return cur.fetchall()


def build_report_payload(
    ibgc_ids: list[int],
    *,
    extra_ibgc_rows: list[dict] | None = None,
    extra_domain_rows: list[dict] | None = None,
) -> dict:
    """Assemble the complete report payload for a shortlist of iBGC ids.

    ``extra_ibgc_rows`` are already-shaped asset roster rows (from
    ``asset:{token}:ibgcs`` in Redis); ``extra_domain_rows`` is the asset's
    flat per-iBGC-deduped domain-hit list (from
    ``asset:{token}:domain_hits``).

    Returns a JSON-serialisable dict matching the ``ReportPayload`` schema
    (minus ``token`` which the endpoint sets).
    """
    # Negative ids belong to assets; keep them out of ORM filters but let
    # the asset rows feed every per-iBGC/per-domain aggregate below.
    db_ibgc_ids = sorted({nid for nid in ibgc_ids if nid >= 0})
    extra_ibgc_rows = list(extra_ibgc_rows or [])
    extra_domain_rows = list(extra_domain_rows or [])
    ibgcs = list(
        IntegratedBgc.objects.select_related("contig", "cbgc").filter(
            id__in=db_ibgc_ids
        )
    )
    n_ibgcs = len(ibgcs) + len(extra_ibgc_rows)
    now = timezone.now()
    expires_at = now + timedelta(seconds=REPORT_TTL_SECONDS)

    if n_ibgcs == 0:
        return _empty_payload(now, expires_at)

    # ── Source predictions grouped by iBGC (single sweep) ──────────────────
    members = list(
        SourceBgcPrediction.objects.filter(
            integrated_bgc_id__in=db_ibgc_ids
        ).select_related("assembly", "assembly__source", "contig", "detector")
    )
    members_by_ibgc: dict[int, list[SourceBgcPrediction]] = defaultdict(list)
    for m in members:
        members_by_ibgc[m.integrated_bgc_id].append(m)

    # ── iBGC rows + parent-assembly collection ─────────────────────────────
    assembly_ids: set[int] = set()
    ibgc_rows: list[dict] = []
    for ibgc in ibgcs:
        mems = members_by_ibgc.get(ibgc.id, [])
        is_validated = any(m.is_validated for m in mems)
        is_type_strain = any(
            m.assembly is not None and m.assembly.is_type_strain for m in mems
        )
        first_asm = mems[0].assembly if mems else None
        if first_asm:
            assembly_ids.add(first_asm.id)
        contig = ibgc.contig
        ibgc_rows.append(
            {
                "id": ibgc.id,
                "accession": ibgc.accession,
                "cbgc_accession": ibgc.cbgc.accession if ibgc.cbgc_id else None,
                "label": ibgc.accession,
                "classification_path": ibgc.gene_cluster_family or "",
                "bgc_class": ibgc.bgc_class or "",
                "size_kb": round(ibgc.size_kb, 3),
                "start": ibgc.start_position,
                "end": ibgc.end_position,
                "novelty_score": ibgc.novelty_score,
                "domain_novelty": ibgc.domain_novelty,
                "n_source_bgcs": len(mems),
                "source_tools": list(ibgc.source_tools or []),
                "is_partial": _is_partial(ibgc),
                "is_validated": is_validated,
                "is_type_strain": is_type_strain,
                "parent_assembly_accession": (
                    first_asm.assembly_accession if first_asm else None
                ),
                "parent_assembly_id": first_asm.id if first_asm else None,
                "organism_name": first_asm.organism_name if first_asm else None,
                "biome_path": first_asm.biome_path if first_asm else "",
                "taxonomy_phylum": _taxonomy_phylum(
                    contig.taxonomy_path if contig else None
                ),
                "contig_accession": contig.accession if contig else None,
            }
        )

    # ── Domain composition (core / variable / rare per acc) ───────────────
    domain_to_ibgcs: dict[str, set[int]] = defaultdict(set)
    domain_name_lookup: dict[str, str] = {}
    domain_desc_lookup: dict[str, str] = {}
    domain_goslim_lookup: dict[str, str] = {}

    # ContigDomain.go_slim is a JSONField list of slim term names (already
    # sorted/deduped by go_slim_for_terms). The heatmap keys each column by a
    # single string, so we collapse to the first term. Be defensive about the
    # raw value: depending on the read path it can arrive as a real list, as a
    # JSON-encoded string (e.g. a double-encoded jsonb cell decoded by psycopg
    # to ``'["…"]'`` / ``'[]'``), or as a plain string. Normalise all of them
    # to a clean list so the column label is a term, never list syntax.
    def _slim_terms(value) -> list[str]:
        if isinstance(value, list):
            return [str(t) for t in value if t]
        if isinstance(value, str):
            s = value.strip()
            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(t) for t in parsed if t]
            return [s] if s else []
        return []

    def _slim_str(value) -> str:
        terms = _slim_terms(value)
        return terms[0] if terms else ""

    for nid, acc, name, desc, slim in _fetch_domain_rows_for_ibgcs(db_ibgc_ids):
        if not acc:
            continue
        domain_to_ibgcs[acc].add(int(nid))
        if name and acc not in domain_name_lookup:
            domain_name_lookup[acc] = name
        if desc and acc not in domain_desc_lookup:
            domain_desc_lookup[acc] = desc
        slim_str = _slim_str(slim)
        if slim_str and acc not in domain_goslim_lookup:
            domain_goslim_lookup[acc] = slim_str

    # Fold in asset domain hits (negative iBGC ids).
    for r in extra_domain_rows:
        acc = r.get("domain_acc")
        if not acc:
            continue
        nid = int(r["ibgc_id"])
        domain_to_ibgcs[acc].add(nid)
        name = r.get("domain_name") or ""
        if name and acc not in domain_name_lookup:
            domain_name_lookup[acc] = name
        desc = r.get("domain_description") or ""
        if desc and acc not in domain_desc_lookup:
            domain_desc_lookup[acc] = desc
        slim = _slim_str(r.get("go_slim"))
        if slim and acc not in domain_goslim_lookup:
            domain_goslim_lookup[acc] = slim

    composition_rows: list[dict] = []
    core_count = variable_count = rare_count = 0
    matrix_buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    domains_long: list[dict] = []
    NO_GOSLIM = "No GO slim"
    for acc, hit_ibgcs in sorted(
        domain_to_ibgcs.items(), key=lambda kv: (-len(kv[1]), kv[0])
    ):
        c = len(hit_ibgcs)
        frac = c / n_ibgcs
        if frac >= CORE_FRACTION:
            tier = "core"
            core_count += 1
        elif frac >= VARIABLE_FRACTION:
            tier = "variable"
            variable_count += 1
        else:
            tier = "rare"
            rare_count += 1
        name = domain_name_lookup.get(acc, "")
        desc = domain_desc_lookup.get(acc, "")
        slim = domain_goslim_lookup.get(acc, "") or NO_GOSLIM
        composition_rows.append(
            {
                "domain_acc": acc,
                "domain_name": name,
                "domain_description": desc,
                "go_slim": slim,
                "ibgc_count": c,
                "fraction": round(frac, 4),
                "tier": tier,
            }
        )
        matrix_buckets[(slim, tier)].append(
            {
                "domain_acc": acc,
                "domain_name": name,
                "domain_description": desc,
            }
        )
        for nid in sorted(hit_ibgcs):
            domains_long.append(
                {
                    "ibgc_id": nid,
                    "domain_acc": acc,
                    "domain_name": name,
                    "domain_description": desc,
                    "go_slim": slim,
                    "tier": tier,
                    "occurs_in_n_ibgcs": c,
                    "fraction": round(frac, 4),
                }
            )
    domain_composition = {
        "core_count": core_count,
        "variable_count": variable_count,
        "rare_count": rare_count,
        "total_unique": len(composition_rows),
        "rows": composition_rows,
    }

    # ── GO slim × tier matrix (for the Domain composition heatmap) ────────
    category_totals: dict[str, int] = defaultdict(int)
    for (slim, _tier), domains in matrix_buckets.items():
        category_totals[slim] += len(domains)
    # "No GO slim" always leads; the rest follow by descending count then name.
    categories = sorted(
        category_totals.keys(),
        key=lambda c: (c != NO_GOSLIM, -category_totals[c], c),
    )
    tiers = ["core", "variable", "rare"]
    cells = []
    for cat in categories:
        for tier in tiers:
            doms = matrix_buckets.get((cat, tier), [])
            cells.append(
                {
                    "category": cat,
                    "tier": tier,
                    "count": len(doms),
                    "domains": doms,
                }
            )
    domain_goslim_matrix = {
        "categories": categories,
        "tiers": tiers,
        "cells": cells,
    }

    # ── GCF distribution ──────────────────────────────────────────────────
    gcf_counts: dict[str, int] = defaultdict(int)
    for ibgc in ibgcs:
        gcf_counts[ibgc.gene_cluster_family or "(unclassified)"] += 1
    for r in extra_ibgc_rows:
        gcf_counts[r.get("classification_path") or "(unclassified)"] += 1
    # iBGC-derived GCF sunburst over the full classification path (e.g.
    # 42 → 42.7 → 42.7.3). Unclassified iBGCs (empty path) are omitted.
    from discovery.services.stats import build_sunburst_from_paths

    gcf_paths = [ibgc.gene_cluster_family for ibgc in ibgcs if ibgc.gene_cluster_family]
    gcf_paths += [
        r.get("classification_path")
        for r in extra_ibgc_rows
        if r.get("classification_path")
    ]
    gcf_sunburst = build_sunburst_from_paths(gcf_paths)
    gcf_distribution = sorted(
        [
            {
                "classification_path": p,
                "ibgc_count": c,
                "fraction": round(c / n_ibgcs, 4),
            }
            for p, c in gcf_counts.items()
        ],
        key=lambda r: (-r["ibgc_count"], r["classification_path"]),
    )

    # ── Score distributions (capped sample for histogram rendering) ───────
    novelty_vals = [
        float(n.novelty_score) for n in ibgcs if n.novelty_score is not None
    ]
    for r in extra_ibgc_rows:
        if r.get("novelty_score") is not None:
            novelty_vals.append(float(r["novelty_score"]))
    novelty_vals = novelty_vals[:SCORE_SAMPLE_CAP]
    dn_vals = [float(n.domain_novelty) for n in ibgcs if n.domain_novelty is not None]
    for r in extra_ibgc_rows:
        if r.get("domain_novelty") is not None:
            dn_vals.append(float(r["domain_novelty"]))
    dn_vals = dn_vals[:SCORE_SAMPLE_CAP]
    score_distributions = [
        {"label": "Novelty", "values": novelty_vals},
        {"label": "Domain Novelty", "values": dn_vals},
    ]

    # ── Completeness bar (complete vs partial) ────────────────────────────
    # An iBGC is "complete" iff none of its source predictions are partial
    # (contig-edge truncation) — the same definition compute_bgc_stats uses.
    if db_ibgc_ids:
        partial_ibgc_ids = set(
            SourceBgcPrediction.objects.filter(
                integrated_bgc_id__in=db_ibgc_ids, is_partial=True
            )
            .values_list("integrated_bgc_id", flat=True)
            .distinct()
        )
    else:
        partial_ibgc_ids = set()
    partial_n = len(partial_ibgc_ids)
    for r in extra_ibgc_rows:
        if r.get("is_partial"):
            partial_n += 1
    complete_n = n_ibgcs - partial_n
    completeness_bar = [
        {"name": "Complete", "count": complete_n},
        {"name": "Partial", "count": partial_n},
    ]

    # ── BGC class distribution ────────────────────────────────────────────
    # The iBGC class is the normalised product class on ``IntegratedBgc``
    # (Polyketide / NRP / RiPP / … / Hybrid), not the GCF lineage segment.
    class_counts: dict[str, int] = defaultdict(int)
    for ibgc in ibgcs:
        head = (ibgc.bgc_class or "").strip() or "(unclassified)"
        class_counts[head] += 1
    for r in extra_ibgc_rows:
        head = (r.get("bgc_class") or "").strip() or "(unclassified)"
        class_counts[head] += 1
    bgc_class_pie = sorted(
        [{"name": k, "count": v} for k, v in class_counts.items()],
        key=lambda r: (-r["count"], r["name"]),
    )

    # ── Length histogram ──────────────────────────────────────────────────
    bucket_counts = [0] * len(LENGTH_BUCKETS)
    for ibgc in ibgcs:
        kb = ibgc.size_kb
        for i, (lo, hi, _) in enumerate(LENGTH_BUCKETS):
            if lo <= kb < hi:
                bucket_counts[i] += 1
                break
    for r in extra_ibgc_rows:
        kb = float(r.get("size_kb") or 0.0)
        for i, (lo, hi, _) in enumerate(LENGTH_BUCKETS):
            if lo <= kb < hi:
                bucket_counts[i] += 1
                break
    length_histogram = [
        {"label": lbl, "count": c}
        for (_, _, lbl), c in zip(LENGTH_BUCKETS, bucket_counts)
    ]

    # ── Predictor distribution ────────────────────────────────────────────
    predictor_counts: dict[str, int] = defaultdict(int)
    for ibgc in ibgcs:
        for tool in ibgc.source_tools or []:
            predictor_counts[tool] += 1
    for r in extra_ibgc_rows:
        for tool in r.get("source_tools") or []:
            predictor_counts[tool] += 1
    predictor_distribution = sorted(
        [{"name": k, "count": v} for k, v in predictor_counts.items()],
        key=lambda r: (-r["count"], r["name"]),
    )

    # ── Source distribution (iBGCs per source collection) ──────────────────
    source_counts: dict[str, int] = defaultdict(int)
    for ibgc in ibgcs:
        names: set[str] = set()
        for m in members_by_ibgc.get(ibgc.id, []):
            src = getattr(m.assembly, "source", None) if m.assembly else None
            if src and src.name:
                names.add(src.name)
        for name in names:
            source_counts[name] += 1
    if extra_ibgc_rows:
        source_counts["Assets"] += len(extra_ibgc_rows)
    source_distribution = sorted(
        [{"name": k, "count": v} for k, v in source_counts.items()],
        key=lambda r: (-r["count"], r["name"]),
    )

    # ── Assembly roster + stats ───────────────────────────────────────────
    assemblies = list(
        DashboardAssembly.objects.filter(id__in=assembly_ids).select_related("source")
    )
    contig_taxonomy_lookup: dict[int, str] = {}
    for c in DashboardContig.objects.filter(assembly_id__in=assembly_ids).values(
        "assembly_id", "taxonomy_path"
    ):
        if c["taxonomy_path"] and c["assembly_id"] not in contig_taxonomy_lookup:
            contig_taxonomy_lookup[c["assembly_id"]] = c["taxonomy_path"]

    ibgcs_per_assembly: dict[int, int] = defaultdict(int)
    for r in ibgc_rows:
        if r["parent_assembly_id"]:
            ibgcs_per_assembly[r["parent_assembly_id"]] += 1

    assembly_rows = []
    for asm in assemblies:
        tx = contig_taxonomy_lookup.get(asm.id, "")
        assembly_rows.append(
            {
                "id": asm.id,
                "accession": asm.assembly_accession,
                "organism_name": asm.organism_name,
                "source_name": asm.source.name if asm.source else None,
                "biome_path": asm.biome_path,
                "taxonomy_path": tx,
                "taxonomy_phylum": _taxonomy_phylum(tx),
                "assembly_size_mb": asm.assembly_size_mb,
                "total_bgcs_in_assembly": asm.bgc_count,
                "ibgcs_in_shortlist": ibgcs_per_assembly.get(asm.id, 0),
                "is_type_strain": asm.is_type_strain,
            }
        )

    from discovery.services.stats import compute_assembly_stats

    try:
        assembly_stats = compute_assembly_stats(
            DashboardAssembly.objects.filter(id__in=assembly_ids)
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "compute_assembly_stats failed for shortlist; "
            "returning empty assembly_stats"
        )
        assembly_stats = {}

    # ── iBGC-derived taxonomy sunburst ─────────────────────────────────────
    from discovery.services.stats import build_taxonomy_sunburst_from_paths

    ibgc_taxonomy_paths = [
        n.contig.taxonomy_path for n in ibgcs if n.contig and n.contig.taxonomy_path
    ]
    taxonomy_sunburst = build_taxonomy_sunburst_from_paths(ibgc_taxonomy_paths)

    # ── iBGC-derived biome sunburst (one count per iBGC) ───────────────────
    biome_paths = [r.get("biome_path") for r in ibgc_rows if r.get("biome_path")]
    biome_paths += [r.get("biome_path") for r in extra_ibgc_rows if r.get("biome_path")]
    biome_sunburst = build_sunburst_from_paths(biome_paths)

    if extra_ibgc_rows:
        # Asset roster rows may predate the start/end/class columns; backfill
        # the keys so every iBGC row (DB + asset) has a uniform shape for the
        # table, TSV, and analyst JSON.
        for r in extra_ibgc_rows:
            r.setdefault("bgc_class", "")
            r.setdefault("start", None)
            r.setdefault("end", None)
        ibgc_rows = list(extra_ibgc_rows) + ibgc_rows

    return {
        "generated_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "n_ibgcs": n_ibgcs,
        "n_assemblies": len(assembly_rows),
        "ibgc_rows": ibgc_rows,
        "domain_composition": domain_composition,
        "gcf_distribution": gcf_distribution,
        "gcf_sunburst": gcf_sunburst,
        "score_distributions": score_distributions,
        "completeness_bar": completeness_bar,
        "bgc_class_pie": bgc_class_pie,
        "length_histogram": length_histogram,
        "predictor_distribution": predictor_distribution,
        "source_distribution": source_distribution,
        "assembly_rows": assembly_rows,
        "assembly_stats": assembly_stats,
        "taxonomy_sunburst": taxonomy_sunburst,
        "biome_sunburst": biome_sunburst,
        "domain_goslim_matrix": domain_goslim_matrix,
        "_domains_long": domains_long,
    }


# v2: added domain_composition tiers, domain_goslim_matrix, gcf/biome
# sunbursts, assembly_stats, and start/end/class on each iBGC row.
ANALYST_SCHEMA_VERSION = "2"


def build_report_analyst_export(token: str, payload: dict) -> dict:
    """Reshape a cached Report payload into an analyst-friendly JSON.

    The export carries two aggregation levels so a consumer can both
    reproduce every summary plot/table and inspect the individual iBGCs:

      * **Per-iBGC** — ``ibgcs`` (one row per iBGC, full column set incl.
        start/end/class/contig), ``assemblies``, and ``domains_long`` (the
        tidy per-iBGC × domain table).
      * **Summary stats** — every panel's underlying data: the BGC-class,
        completeness, length, predictor and source distributions, GCF
        distribution + sunburst, score distributions, taxonomy & biome
        sunbursts, the domain-composition tiers (core/variable/rare with
        fractions), the GO-slim × tier matrix, and assembly stats.
    """
    return {
        "metadata": {
            "schema_version": ANALYST_SCHEMA_VERSION,
            "token": token,
            "generated_at": payload.get("generated_at"),
            "expires_at": payload.get("expires_at"),
            "n_ibgcs": payload.get("n_ibgcs", 0),
            "n_assemblies": payload.get("n_assemblies", 0),
        },
        # ── Per-iBGC detail ──────────────────────────────────────────────
        "ibgcs": payload.get("ibgc_rows", []),
        "assemblies": payload.get("assembly_rows", []),
        "domains_long": payload.get("_domains_long", []),
        # ── Summary stats (one entry per report plot/table) ──────────────
        "bgc_class_counts": payload.get("bgc_class_pie", []),
        "completeness_counts": payload.get("completeness_bar", []),
        "length_histogram": payload.get("length_histogram", []),
        "predictor_distribution": payload.get("predictor_distribution", []),
        "source_distribution": payload.get("source_distribution", []),
        "gcf_distribution": payload.get("gcf_distribution", []),
        "gcf_sunburst": payload.get("gcf_sunburst", []),
        "score_distributions": payload.get("score_distributions", []),
        "taxonomy_sunburst": payload.get("taxonomy_sunburst", []),
        "biome_sunburst": payload.get("biome_sunburst", []),
        "domain_composition": payload.get(
            "domain_composition",
            {
                "core_count": 0,
                "variable_count": 0,
                "rare_count": 0,
                "total_unique": 0,
                "rows": [],
            },
        ),
        "domain_goslim_matrix": payload.get(
            "domain_goslim_matrix",
            {"categories": [], "tiers": [], "cells": []},
        ),
        "assembly_stats": payload.get("assembly_stats", {}),
    }


def _empty_payload(now, expires_at) -> dict:
    return {
        "generated_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "n_ibgcs": 0,
        "n_assemblies": 0,
        "ibgc_rows": [],
        "domain_composition": {
            "core_count": 0,
            "variable_count": 0,
            "rare_count": 0,
            "total_unique": 0,
            "rows": [],
        },
        "gcf_distribution": [],
        "gcf_sunburst": [],
        "score_distributions": [
            {"label": "Novelty", "values": []},
            {"label": "Domain Novelty", "values": []},
        ],
        "completeness_bar": [],
        "bgc_class_pie": [],
        "length_histogram": [],
        "predictor_distribution": [],
        "source_distribution": [],
        "assembly_rows": [],
        "assembly_stats": {},
        "taxonomy_sunburst": [],
        "biome_sunburst": [],
        "domain_goslim_matrix": {"categories": [], "tiers": [], "cells": []},
        "_domains_long": [],
    }
