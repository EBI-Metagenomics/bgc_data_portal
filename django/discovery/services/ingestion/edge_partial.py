"""Gene-margin contig-edge rule for ``SourceBgcPrediction.is_partial``.

The ETL flags a call partial only when it touches the exact first or last base
of its contig. Whether a call reaches that base depends on the gene caller:
Pyrodigal on metagenomes emits truncated edge genes that run to the contig end,
while the catalogue gene calls stop a few hundred bp short. The same biology was
therefore flagged in one dataset and not in the other.

This module recomputes the flag from geometry, the same way for every detector
and gene caller:

    A non-validated call is partial when, on either side, the stretch between
    its outermost gene and the contig end could hold at most ``gene_margin``
    more genes:

        min(left_gap, right_gap) < (gene_margin + 1) × gene_bp

* The *outermost gene* is the outermost CDS overlapping the call (a call
  boundary often falls inside a gene, and a truncated edge gene starts at 0).
* ``gene_bp`` is the median genomic span of the CDS overlapping the call, so
  eukaryote genes (longer, with introns) get a proportionally wider margin.
  Calls with no stored CDS fall back to ``FALLBACK_GENE_BP``.
* ``gene_margin=0``: partial when not even one complete gene fits beyond the
  call; ``gene_margin=1`` (default): one complete gene of slack is still edge.
* Validated predictions (MIBiG) are never partial.

The rule is a superset of the ETL's exact-edge test (gap 0) and is recomputed
from scratch, so it is idempotent and a different margin can be applied later.
Only genes inside BGC calls are stored, so the gap is measured in bp and scaled
by the call's own gene size rather than by counting genes beyond the call.

Range convention: the loader stores ``[start, end_position + 1)``; an element
ending on the contig's last base therefore has ``upper = length + 1``.
"""

from __future__ import annotations

import logging

from django.db import connection, transaction

log = logging.getLogger(__name__)

DEFAULT_GENE_MARGIN = 1
FALLBACK_GENE_BP = 1_000

_RULE_CTE = """
WITH geom AS (
    SELECT sb.id,
           d.tool,
           sb.is_partial AS old,
           sb.is_validated,
           LEAST(lower(sb.bgc_range), COALESCE(x.first_lo, lower(sb.bgc_range)))
               AS left_gap,
           CASE WHEN c.length > 0 THEN GREATEST(
               0,
               c.length + 1
                 - GREATEST(upper(sb.bgc_range), COALESCE(x.last_hi, upper(sb.bgc_range)))
           ) END AS right_gap,
           COALESCE(x.gene_bp, %(fallback)s) AS gene_bp
      FROM discovery_source_bgc sb
      JOIN discovery_contig c ON c.id = sb.contig_id
      LEFT JOIN discovery_detector d ON d.id = sb.detector_id
      LEFT JOIN LATERAL (
          SELECT min(lower(cd.cds_range)) AS first_lo,
                 max(upper(cd.cds_range)) AS last_hi,
                 percentile_cont(0.5) WITHIN GROUP (
                     ORDER BY upper(cd.cds_range) - lower(cd.cds_range)
                 ) AS gene_bp
            FROM discovery_cds cd
           WHERE cd.contig_id = sb.contig_id
             AND cd.cds_range && sb.bgc_range
      ) x ON true
), rule AS (
    SELECT id, tool, old,
           (NOT is_validated
            AND LEAST(left_gap, right_gap) < (%(margin)s + 1) * gene_bp) AS new
      FROM geom
)
"""


def mark_edge_partials(
    *, gene_margin: int = DEFAULT_GENE_MARGIN, dry_run: bool = False
) -> dict:
    """Recompute ``is_partial`` on every source prediction; return per-tool counts.

    Returns ``{"gene_margin", "dry_run", "changed", "by_tool": {tool: {...}}}``
    where each tool entry has ``calls``, ``partial_before``, ``partial_after``,
    ``set`` (false→true) and ``cleared`` (true→false).
    """
    if gene_margin < 0:
        raise ValueError("gene_margin must be >= 0")
    params = {"margin": int(gene_margin), "fallback": FALLBACK_GENE_BP}
    summary_sql = (
        _RULE_CTE
        + """
SELECT COALESCE(tool, '?'),
       count(*),
       count(*) FILTER (WHERE old),
       count(*) FILTER (WHERE new),
       count(*) FILTER (WHERE new AND NOT old),
       count(*) FILTER (WHERE old AND NOT new)
  FROM rule GROUP BY 1 ORDER BY 1
"""
    )
    update_sql = (
        _RULE_CTE
        + """
UPDATE discovery_source_bgc sb
   SET is_partial = rule.new
  FROM rule
 WHERE rule.id = sb.id AND rule.new IS DISTINCT FROM sb.is_partial
"""
    )
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(summary_sql, params)
        by_tool = {
            tool: {
                "calls": n,
                "partial_before": before,
                "partial_after": after,
                "set": set_,
                "cleared": cleared,
            }
            for tool, n, before, after, set_, cleared in cur.fetchall()
        }
        changed = 0
        if not dry_run:
            cur.execute(update_sql, params)
            changed = cur.rowcount
    result = {
        "gene_margin": gene_margin,
        "dry_run": dry_run,
        "changed": changed,
        "by_tool": by_tool,
    }
    log.info("mark_edge_partials: %s", result)
    return result
