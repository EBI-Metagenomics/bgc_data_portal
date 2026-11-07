"""SQL fragments shared by the raw-SQL query paths."""

# ``discovery_cds c`` -> the iBGC(s) it belongs to: same contig, CDS span
# overlaps the iBGC span (GiST on ``bgc_range``).
IBGC_CDS_JOIN = """
    JOIN discovery_ibgc i
      ON i.contig_id = c.contig_id
     AND i.bgc_range && c.cds_range
"""

# Domain hit -> its CDS -> the iBGC(s); aliases ``d`` / ``c`` / ``i``.
IBGC_DOMAIN_HIT_JOIN = (
    """
    FROM discovery_domain_hit d
    JOIN discovery_cds c ON c.id = d.cds_id
"""
    + IBGC_CDS_JOIN
)
