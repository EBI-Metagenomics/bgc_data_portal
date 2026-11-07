"""Detectors, consensus BGCs (cBGC), integrated BGCs (iBGC) and per-tool predictions."""

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import IntegerRangeField
from django.db import models

from .assembly import DashboardAssembly, DashboardContig
from .mixins import RangeFieldMixin


class DashboardDetector(models.Model):
    """BGC detection tool + version lookup."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Human-readable label, e.g. "antiSMASH v7.1"',
    )
    tool = models.CharField(max_length=255, help_text='Tool name, e.g. "antiSMASH"')
    version = models.CharField(max_length=50, help_text='Semver string, e.g. "7.1.0"')
    tool_name_code = models.CharField(
        max_length=3,
        help_text='3-letter uppercase code, e.g. "ANT"',
    )
    version_sort_key = models.PositiveIntegerField(
        default=0,
        help_text="Monotonic integer for DB-level version ordering",
    )

    class Meta:
        db_table = "discovery_detector"
        constraints = [
            models.UniqueConstraint(
                fields=["tool", "version"],
                name="uniq_detector_tool_version",
            ),
        ]

    def __str__(self):
        return self.name


class ConsensusBgc(RangeFieldMixin, models.Model):
    """Aggregated genomic region on a contig — the chained-overlap envelope
    that contains one or more iBGCs.

    Accession ``MGYB-XXXXXX`` is stable forever via ``AccessionRegistry``.
    Disjointness across cBGCs on the same contig is enforced by an
    exclusion constraint on ``(contig_id, bgc_range)``.
    """

    id = models.BigAutoField(primary_key=True)
    accession = models.CharField(max_length=20, unique=True, db_index=True)
    contig = models.ForeignKey(
        DashboardContig,
        on_delete=models.CASCADE,
        related_name="cbgcs",
        db_index=True,
    )
    bgc_range = IntegerRangeField(
        help_text="Half-open [start, end) genomic span; lower = 1-based start, upper = exclusive end",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discovery_cbgc"
        constraints = [
            ExclusionConstraint(
                name="excl_cbgc_overlap",
                expressions=[
                    ("contig", "="),
                    ("bgc_range", "&&"),
                ],
            ),
        ]

    def __str__(self):
        return self.accession


class IntegratedBgc(RangeFieldMixin, models.Model):
    """Integrated BGC — the core operational unit of the platform.

    Sits inside exactly one ``ConsensusBgc``. iBGCs within the same cBGC
    are strictly disjoint (DB-enforced via exclusion constraint).

    Accession ``MGYB-XXXXXX-YY`` is stable forever via ``AccessionRegistry``.

    CDS membership is decided by range overlap on the contig:
        ``ContigCds.cds_range && IntegratedBgc.bgc_range``
    Domain hits inherit from their CDS.

    Built from ``SourceBgcPrediction`` rows:
      * Validated predictions become standalone iBGCs regardless of tool
        or partial flag — ground truth, never merged with predictions.
      * Non-validated GECCO and SanntiS predictions on the same contig
        merge via transitive interval overlap (any positive intersection
        joins a component, regardless of ``is_partial``). The merged
        interval spans ``min(starts) → max(ends)``.
      * For each chain iBGC above, any non-validated antiSMASH prediction
        overlapping it has ``'antiSMASH'`` added to ``source_tools`` and
        gets ``integrated_bgc`` set to that iBGC (so ``claimed_by_tools``
        attribution is preserved). antiSMASH coordinates do not widen the
        chain interval.
      * Non-validated antiSMASH predictions that do not overlap any
        already-built iBGC on the same contig become their own iBGC.

    Clustering writes ``gene_cluster_family``, ``is_partial``,
    ``novelty_score`` and ``domain_novelty`` here. Source predictions do
    not duplicate these — they are derived from ``integrated_bgc`` on
    read.
    """

    id = models.BigAutoField(primary_key=True)
    accession = models.CharField(max_length=20, unique=True, db_index=True)
    cbgc = models.ForeignKey(
        ConsensusBgc,
        on_delete=models.CASCADE,
        related_name="ibgcs",
        db_index=True,
    )
    contig = models.ForeignKey(
        DashboardContig,
        on_delete=models.CASCADE,
        related_name="ibgcs",
        db_index=True,
        help_text="Denormalised from cbgc.contig for fast range-overlap queries",
    )
    bgc_range = IntegerRangeField(
        help_text="Half-open [start, end) genomic span on the contig",
    )

    source_tools = models.JSONField(
        default=list,
        help_text="Sorted, deduped tool names contributing, e.g. ['GECCO','SanntiS']",
    )

    bgc_class = models.CharField(
        max_length=32,
        blank=True,
        default="",
        db_index=True,
        help_text=(
            "Normalised product class — one of Polyketide / NRP / RiPP / "
            "Terpene / Saccharide / Alkaloid / Other / Hybrid(P+N) / Hybrid. "
            "Derived by unioning the classification_path of all source "
            "predictions (common_core.bgc_class.classify_ibgc)."
        ),
    )

    gene_cluster_family = models.CharField(
        max_length=512,
        blank=True,
        default="",
        db_index=True,
        help_text="ltree dot-path, e.g. 42.7.3 (leaf of the hierarchy)",
    )
    is_partial = models.BooleanField(
        default=False,
        help_text=(
            "True when the iBGC was not in the primary clustering pass and its "
            "GCF / novelty were projected from its top-K nearest primary iBGCs. "
            "False when it was clustered directly."
        ),
    )
    novelty_score = models.FloatField(
        null=True,
        blank=True,
        help_text="1 − max composite-Dice similarity to the nearest validated iBGC.",
    )
    domain_novelty = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Fraction of this iBGC's domains not shared by any other iBGC of the "
            "same leaf GCF. NULL for singleton GCFs and for iBGCs without any "
            "domains of the selected sources."
        ),
    )
    classification_run = models.ForeignKey(
        "ClusteringRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ibgcs",
    )
    classified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discovery_ibgc"
        constraints = [
            ExclusionConstraint(
                name="excl_ibgc_overlap_in_cbgc",
                expressions=[
                    ("cbgc", "="),
                    ("bgc_range", "&&"),
                ],
            ),
        ]
        indexes = [
            models.Index(fields=["gene_cluster_family"], name="idx_ibgc_gcf"),
        ]

    def __str__(self):
        return self.accession


class SourceBgcPrediction(RangeFieldMixin, models.Model):
    """One BGC prediction emitted by one detection tool on one contig.

    Provenance row, not a CDS/domain owner. CDS and domains live on the
    contig and are reached from an iBGC via range overlap. A source
    prediction's ``claimed_by_tools`` contribution is whatever overlap its
    ``bgc_range`` has with each CDS in its owning iBGC.

    Scoring and classification fields live on ``IntegratedBgc``; do
    not duplicate them here. ``integrated_bgc`` is NULL only for partials
    or predictions that fail to land in any iBGC at build time.

    ``prediction_accession`` is derived at ingest as
    ``{cbgc.accession}.{detector.tool_name_code}.{bgc_number:02d}``,
    e.g. ``MGYB-ABC123.ANT.01``.
    """

    id = models.BigAutoField(primary_key=True)

    assembly = models.ForeignKey(
        DashboardAssembly,
        on_delete=models.CASCADE,
        related_name="source_bgcs",
        db_index=True,
    )
    contig = models.ForeignKey(
        DashboardContig,
        on_delete=models.CASCADE,
        related_name="source_bgcs",
        db_index=True,
    )

    prediction_accession = models.CharField(max_length=50, db_index=True)
    bgc_range = IntegerRangeField(
        help_text="Half-open [start, end) genomic span on the contig"
    )

    classification_path = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text=(
            "Raw per-tool product class as staged (e.g. 'NRPS_T1PKS', "
            "'RiPP_like', 'NRP_Polyketide'). Shown verbatim on prediction "
            "hover; normalised into IntegratedBgc.bgc_class at iBGC level."
        ),
    )

    is_partial = models.BooleanField(default=False)
    is_validated = models.BooleanField(default=False)

    score = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Detector-native region score from the staged bgcs.tsv (SanntiS 1.0 "
            "mean ORF score, GECCO probability); NULL for detectors without one."
        ),
    )
    probability = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Detector BGC probability in [0, 1]: 1 - p_non_bgc for SanntiS 1.0 "
            "(RF post-filter), ProbabilityAverage for GECCO; NULL otherwise."
        ),
    )
    attributes = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Every GFF attribute of the prediction except ID, as staged in "
            "bgcs.tsv:attributes_json (SanntiS 1.0 bgc_class / n_orfs / npc_*, "
            "SanntiS 0.9 nearest_MiBIG, antiSMASH product ...). Display only."
        ),
    )

    detector = models.ForeignKey(
        DashboardDetector,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_bgcs",
        db_index=True,
    )

    cbgc = models.ForeignKey(
        ConsensusBgc,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_bgcs",
        db_index=True,
    )
    bgc_number = models.PositiveSmallIntegerField(
        default=0,
        help_text="2-digit incremental within (cbgc, detector); used in prediction_accession",
    )

    integrated_bgc = models.ForeignKey(
        IntegratedBgc,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_predictions",
        db_index=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discovery_source_bgc"
        constraints = [
            ExclusionConstraint(
                name="excl_source_bgc_overlap_per_detector",
                expressions=[
                    ("contig", "="),
                    ("detector", "="),
                    ("bgc_range", "&&"),
                ],
            ),
        ]
        indexes = [
            models.Index(fields=["assembly"], name="idx_sbgc_assembly"),
            models.Index(fields=["integrated_bgc"], name="idx_sbgc_ibgc"),
        ]

    def __str__(self):
        return self.prediction_accession
