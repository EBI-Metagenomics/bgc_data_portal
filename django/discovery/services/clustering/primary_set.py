"""The primary (directly clustered) iBGC set, shared by export and scoring cache.

An iBGC is primary when

1. at least one of its source predictions is non-partial or validated, and
2. its span is below ``MAX_PRIMARY_IBGC_BP`` — unless it is validated.

Everything else is exported as a partial and gets its family / novelty
projected from its top-K primary neighbours, so it still reaches the portal but
cannot shape the similarity graph. The size cap keeps very long predictions
(typically several neighbouring clusters called as one, up to ~1.7 Mb) from
acting as hubs; curated MIBiG entries are exempt (e.g. plant clusters).

``export_clustering_inputs`` and the scoring-cache rebuild must agree on this
set, so both call :func:`clusterable_ibgc_ids`.
"""

from __future__ import annotations

from django.db import connection

MAX_PRIMARY_IBGC_BP = 200_000

_SQL = """
SELECT i.id
  FROM discovery_ibgc i
 WHERE EXISTS (
           SELECT 1 FROM discovery_source_bgc sb
            WHERE sb.integrated_bgc_id = i.id
              AND (NOT sb.is_partial OR sb.is_validated))
   AND (upper(i.bgc_range) - lower(i.bgc_range) < %(max_bp)s
        OR EXISTS (
           SELECT 1 FROM discovery_source_bgc v
            WHERE v.integrated_bgc_id = i.id AND v.is_validated))
 ORDER BY i.id
"""


def clusterable_ibgc_ids(*, max_bp: int = MAX_PRIMARY_IBGC_BP) -> list[int]:
    """Sorted ids of the primary iBGCs (see module docstring)."""
    with connection.cursor() as cur:
        cur.execute(_SQL, {"max_bp": int(max_bp)})
        return [r[0] for r in cur.fetchall()]
