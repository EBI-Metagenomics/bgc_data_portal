"""Helpers for PostgreSQL ltree queries on taxonomy_path fields."""

import re

from ninja.errors import HttpError

from discovery.models import DashboardContig

_LTREE_PATH = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$")


def filter_contigs_by_taxonomy(prefix: str):
    """Return a queryset of contigs under a taxonomy ltree prefix (``<@``).

    An invalid label would make Postgres raise (a 500), so it is rejected
    here with a 400 instead.
    """
    if not _LTREE_PATH.match(prefix):
        raise HttpError(
            400, "taxonomy_path must be an ltree path like Bacteria.Firmicutes"
        )
    return DashboardContig.objects.extra(
        where=["taxonomy_path::ltree <@ %s::ltree"],
        params=[prefix],
    )
