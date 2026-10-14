"""Rank-aware reading of contig taxonomy.

``DashboardContig.taxonomy_path`` is rank-less: absent ranks are skipped, so
depth does not identify rank (e.g. ``Bacteria.Pseudomonadati.Pseudomonadota``
has the kingdom at depth 1). Ranks come from the linked ``Taxon`` when the
contig has one; otherwise we fall back to the historical positional guess.
"""

from __future__ import annotations

from collections.abc import Iterable

RANKS: tuple[str, ...] = (
    "domain",
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
)

# Positional guess for contigs not yet linked to a Taxon. Matches what the
# report has always assumed (domain at depth 0, phylum at depth 1).
POSITIONAL_RANKS: tuple[str, ...] = (
    "domain",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
)

RankedLabels = list[tuple[str, str]]


def positional_ranked_labels(path: str) -> RankedLabels:
    parts = [p for p in (path or "").split(".") if p]
    return [
        (POSITIONAL_RANKS[i] if i < len(POSITIONAL_RANKS) else f"rank_{i}", label)
        for i, label in enumerate(parts)
    ]


def taxon_ranked_labels(taxon) -> RankedLabels:
    """Pair ``taxon.ltree_path`` labels with the ranks that are present."""
    present = [r for r in RANKS if getattr(taxon, f"{r}_taxid") is not None]
    labels = [p for p in taxon.ltree_path.split(".") if p]
    if len(present) != len(labels):
        return positional_ranked_labels(taxon.ltree_path)
    return list(zip(present, labels))


def ranked_labels_by_taxon(taxon_ids: Iterable[int | None]) -> dict[int, RankedLabels]:
    """One query: ``{taxon_id: [(rank, label), ...]}`` for the given ids."""
    from discovery.models import Taxon

    ids = {t for t in taxon_ids if t is not None}
    if not ids:
        return {}
    return {
        t.taxid: taxon_ranked_labels(t) for t in Taxon.objects.filter(taxid__in=ids)
    }


def ranked_labels(
    path: str, taxon_id: int | None, lookup: dict[int, RankedLabels]
) -> RankedLabels:
    if taxon_id is not None and taxon_id in lookup:
        return lookup[taxon_id]
    return positional_ranked_labels(path)


def phylum_label(path: str, taxon_id: int | None, lookup: dict[int, RankedLabels]):
    """Phylum ltree label, or ``None`` when the lineage has no phylum."""
    if not path and taxon_id is None:
        return None
    for rank, label in ranked_labels(path, taxon_id, lookup):
        if rank == "phylum":
            return label
    return None
