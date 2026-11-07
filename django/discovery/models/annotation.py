"""Contig-anchored CDS (with on-demand sequence) and their domain hits."""

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import IntegerRangeField
from django.db import models

from .assembly import DashboardContig
from .mixins import RangeFieldMixin, ZlibSequenceMixin


class ContigCds(RangeFieldMixin, models.Model):
    """A coding sequence on a contig.

    CDS live at the contig level (not per-BGC). The same gene called by
    multiple BGC tools is stored once. iBGC region views reach CDS via
    range overlap:
        ``ContigCds.objects.filter(contig=ibgc.contig,
                                   cds_range__overlap=ibgc.bgc_range)``
    """

    id = models.BigAutoField(primary_key=True)
    contig = models.ForeignKey(
        DashboardContig,
        on_delete=models.CASCADE,
        related_name="cds_list",
        db_index=True,
    )
    cds_range = IntegerRangeField(
        help_text="Half-open [start, end) genomic span on the contig"
    )
    strand = models.SmallIntegerField()

    protein_id_str = models.CharField(
        max_length=255,
        help_text="Display identifier (mgyp or protein_identifier)",
    )
    protein_length = models.IntegerField(default=0)
    gene_caller = models.CharField(max_length=100, blank=True, default="")
    cluster_representative = models.CharField(max_length=64, blank=True, default="")
    protein_sha256 = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="SHA-256 hash of the amino-acid sequence (pyhmmer search-index key)",
    )

    range_field = "cds_range"

    class Meta:
        db_table = "discovery_cds"
        constraints = [
            ExclusionConstraint(
                name="uniq_cds_contig_range_strand",
                expressions=[
                    ("contig", "="),
                    ("cds_range", "="),
                    ("strand", "="),
                ],
            ),
        ]
        indexes = [
            models.Index(fields=["protein_sha256"], name="idx_dcds_prot_sha256"),
        ]

    def __str__(self):
        return f"CDS {self.protein_id_str} on contig {self.contig_id}"


class CdsSequence(ZlibSequenceMixin, models.Model):
    """On-demand amino-acid sequence for a CDS — zlib-compressed."""

    cds = models.OneToOneField(
        ContigCds,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="seq",
    )
    data = models.BinaryField(help_text="zlib-compressed amino-acid sequence")

    class Meta:
        db_table = "discovery_cds_sequence"

    def __str__(self):
        return f"Sequence for CDS {self.cds_id}"


class ContigDomain(models.Model):
    """Domain hit on a contig CDS.

    The ``contig`` FK is denormalised from ``cds.contig`` so iBGC-scope
    domain queries can range-filter without a join:
        ``ContigDomain.objects.filter(cds__contig=ibgc.contig,
                                      cds__cds_range__overlap=ibgc.bgc_range)``
    Positions are protein-relative (amino-acid coordinates).
    """

    id = models.BigAutoField(primary_key=True)
    cds = models.ForeignKey(
        ContigCds,
        on_delete=models.CASCADE,
        related_name="domains",
    )
    contig = models.ForeignKey(
        DashboardContig,
        on_delete=models.CASCADE,
        related_name="domains",
        db_index=True,
    )

    domain_acc = models.CharField(max_length=50, db_index=True)
    domain_name = models.CharField(max_length=255)
    domain_description = models.TextField(blank=True, default="")
    ref_db = models.CharField(max_length=50, blank=True, default="")

    go_slim = models.JSONField(default=list, blank=True)
    interpro_entry_acc = models.CharField(max_length=20, blank=True, default="")
    interpro_entry_description = models.CharField(
        max_length=255, blank=True, default=""
    )
    go_terms = models.JSONField(default=list, blank=True)

    # Protein-relative (amino-acid) coordinates of the hit
    start_position = models.IntegerField(default=0)
    end_position = models.IntegerField(default=0)
    score = models.FloatField(null=True, blank=True)
    url = models.URLField(max_length=512, blank=True, default="")

    class Meta:
        db_table = "discovery_domain_hit"
        constraints = [
            models.UniqueConstraint(
                fields=["cds", "domain_acc", "start_position", "end_position"],
                name="uniq_domain_cds_acc_pos",
            ),
        ]
        indexes = [
            models.Index(fields=["domain_acc", "contig"], name="idx_dom_acc_contig"),
            models.Index(fields=["contig", "domain_acc"], name="idx_dom_contig_acc"),
            models.Index(
                fields=["contig", "ref_db", "domain_acc"],
                name="idx_dom_contig_ref_acc",
            ),
        ]

    def __str__(self):
        return f"{self.domain_acc} on CDS {self.cds_id}"
