"""NPClassifier labels: ontology loading, iBGC aggregation, search expansion.

The ontology (pathway → superclass → class, a DAG) is the frozen NPClassifier
index SanntiS 1.0 ships, vendored in ``common_core.npc``. ``load_npc_ontology``
mirrors it into ``NpcTerm`` / ``NpcTermEdge``; search and the tree use the
in-process copy for expansion (772 terms) and the DB for counts.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from functools import lru_cache

from common_core.npc import ONTOLOGY_VERSION, Ontology, load_ontology
from django.db import connection, transaction

from discovery.models import IbgcNpcLabel, NpcTerm, NpcTermEdge

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def ontology() -> Ontology:
    return load_ontology()


def load_npc_ontology() -> dict[str, int]:
    """Upsert the vendored ontology into ``NpcTerm`` / ``NpcTermEdge`` (idempotent)."""
    ont = ontology()
    terms = [
        NpcTerm(
            term_id=t.term_id,
            level=t.level,
            name=t.name,
            ontology_version=ONTOLOGY_VERSION,
        )
        for t in ont.terms.values()
    ]
    with transaction.atomic():
        NpcTerm.objects.bulk_create(
            terms,
            batch_size=500,
            update_conflicts=True,
            unique_fields=["term_id"],
            update_fields=["level", "name", "ontology_version"],
        )
        edges = [
            NpcTermEdge(child_id=child, parent_id=parent)
            for child, parents in ont.parents.items()
            for parent in parents
        ]
        NpcTermEdge.objects.bulk_create(edges, batch_size=500, ignore_conflicts=True)
    counts = {"terms": NpcTerm.objects.count(), "edges": NpcTermEdge.objects.count()}
    log.info("NPClassifier ontology %s loaded: %s", ONTOLOGY_VERSION, counts)
    return counts


def expand_term_ids(term_ids: Iterable[str]) -> set[str]:
    """Selected terms plus every descendant (what the ``npc_terms`` filter matches)."""
    return ontology().descendants([t.strip() for t in term_ids if t and t.strip()])


def parse_term_csv(value: str | None) -> list[str]:
    return [t.strip() for t in (value or "").split(",") if t.strip()]


def aggregate_ibgc_npc_labels() -> int:
    """Rebuild ``IbgcNpcLabel`` from the source predictions wired to iBGCs.

    One row per (iBGC, term): best score, ``confident`` when any member label is
    confident, the distinct label sources and detector tools, and the number of
    contributing predictions. Returns the number of rows written.
    """
    with transaction.atomic():
        IbgcNpcLabel.objects.all().delete()
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO discovery_ibgc_npc_label
                    (ibgc_id, term_id, score, confident, sources,
                     detector_tools, n_predictions)
                SELECT
                    s.integrated_bgc_id,
                    l.term_id,
                    MAX(l.score),
                    BOOL_OR(l.confident),
                    COALESCE(jsonb_agg(DISTINCT l.source), '[]'::jsonb),
                    COALESCE(jsonb_agg(DISTINCT d.tool)
                             FILTER (WHERE d.tool IS NOT NULL), '[]'::jsonb),
                    COUNT(*)
                FROM discovery_source_bgc_npc_label l
                JOIN discovery_source_bgc s ON s.id = l.source_bgc_id
                LEFT JOIN discovery_detector d ON d.id = s.detector_id
                WHERE s.integrated_bgc_id IS NOT NULL
                GROUP BY s.integrated_bgc_id, l.term_id
                """)
            n = cur.rowcount
    log.info("Aggregated %d iBGC NPClassifier labels", n)
    return n


def term_counts(confident_only: bool) -> dict[str, int]:
    """Distinct iBGCs labelled with each term (direct labels, not descendants)."""
    qs = IbgcNpcLabel.objects.all()
    if confident_only:
        qs = qs.filter(confident=True)
    counts: dict[str, int] = {}
    with connection.cursor() as cur:
        cur.execute(
            "SELECT term_id, COUNT(DISTINCT ibgc_id) FROM discovery_ibgc_npc_label"
            + (" WHERE confident" if confident_only else "")
            + " GROUP BY term_id"
        )
        for term_id, n in cur.fetchall():
            counts[term_id] = int(n)
    return counts


def npc_tree() -> list[dict]:
    """Ontology tree with per-term iBGC counts (``count``, ``confident_count``).

    Multi-parent superclasses appear under each parent; the one orphan superclass
    of index v1 is listed after the pathways. Counts are direct labels of the
    term; selecting a node in the filter also matches its descendants.
    """
    all_counts = term_counts(confident_only=False)
    conf_counts = term_counts(confident_only=True)

    def decorate(node: dict) -> dict:
        tid = node["term_id"]
        return {
            "term_id": tid,
            "level": node["level"],
            "name": node["name"],
            "count": all_counts.get(tid, 0),
            "confident_count": conf_counts.get(tid, 0),
            "children": [decorate(c) for c in node["children"]],
        }

    return [decorate(n) for n in ontology().tree()]


def build_npc_sunburst(ibgc_qs, confident_only: bool = True) -> list[dict]:
    """Flat sunburst nodes (id, label, parent, count) over the NPClassifier DAG.

    Each label counts once per (iBGC, term) at the term node and at every
    ancestor chain node, so pathways hold the sum of their superclasses. A
    multi-parent superclass contributes to each parent chain, keyed by the
    chain so the sunburst stays a tree.
    """
    ont = ontology()
    qs = IbgcNpcLabel.objects.filter(ibgc__in=ibgc_qs)
    if confident_only:
        qs = qs.filter(confident=True)
    nodes: dict[str, dict] = {}
    for term_id in qs.values_list("term_id", flat=True).iterator():
        if term_id not in ont:
            continue
        for path in ont.paths(term_id):
            for depth, tid in enumerate(path):
                node_id = "/".join(path[: depth + 1])
                parent_id = "/".join(path[:depth]) if depth else ""
                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id,
                        "label": ont.terms[tid].name,
                        "parent": parent_id,
                        "count": 0,
                    }
                nodes[node_id]["count"] += 1
    return list(nodes.values())
