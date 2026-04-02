"""Helpers for PostgreSQL ltree queries on taxonomy_path fields."""

from discovery.models import DashboardContig


def filter_contigs_by_taxonomy(prefix: str):
    """Return a queryset of contig IDs matching a taxonomy ltree prefix.

    Uses the PostgreSQL ltree ``<@`` (descendant-of) operator.
    """
    return DashboardContig.objects.extra(
        where=["taxonomy_path::ltree <@ %s::ltree"],
        params=[prefix],
    )
