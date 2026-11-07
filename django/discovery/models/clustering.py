"""Clustering runs, enrichment weights, the GCF hierarchy and rollback snapshots."""

from django.db import models

from .bgc import IntegratedBgc


class ClusteringRun(models.Model):
    """One iBGC composite similarity → KNN graph → hierarchical CPM Leiden run.

    ``similarity_metric`` records how iBGC × iBGC similarity was scored
    (ADR 0003): binary composite Dice (older runs) or the IDF × enrichment
    weighted cosine, whose per-feature weights are persisted with the run's
    artefacts so every consumer scores with the same weights.

    Parameters + counts only. The hierarchy itself lives in ``DashboardGCF``
    rows; per-iBGC leaf paths live on ``IntegratedBgc.gene_cluster_family``.
    Re-running with identical inputs yields the same ``sha256`` and so the
    same ``pk`` (idempotent via ``update_or_create``).
    """

    created_at = models.DateTimeField(auto_now_add=True)

    domain_sources = models.JSONField(
        default=list,
        help_text="Domain ref_db sources used (upper-case), e.g. ['PFAM','NCBIFAM']",
    )
    DOMAIN_VOCAB_IPR_PROJECTED = "IPR_PROJECTED"
    DOMAIN_VOCAB_IPR_GAPFILLED = "IPR_GAPFILLED"
    DOMAIN_VOCAB_CHOICES = (
        (DOMAIN_VOCAB_IPR_PROJECTED, "IPR entry when available, else signature"),
        (
            DOMAIN_VOCAB_IPR_GAPFILLED,
            "IPR-projected, plus Gene3D/PRINTS/ProSite hits that fill gaps",
        ),
    )
    domain_vocab = models.CharField(
        max_length=20,
        choices=DOMAIN_VOCAB_CHOICES,
        default=DOMAIN_VOCAB_IPR_PROJECTED,
    )
    score_weights = models.JSONField(
        default=list,
        help_text="(w_domain, w_adjacency) for the composite score, e.g. [0.5, 0.5]",
    )
    # Values match common_core.clustering.similarity.SIMILARITY_METRICS so
    # they pass through the HPC tarball unchanged.
    SIMILARITY_DICE = "dice"
    SIMILARITY_COSINE_IDF_ENRICH = "cosine_idf_enrich"
    SIMILARITY_METRIC_CHOICES = (
        (SIMILARITY_DICE, "Binary composite Dice"),
        (SIMILARITY_COSINE_IDF_ENRICH, "IDF × enrichment weighted cosine"),
    )
    similarity_metric = models.CharField(
        max_length=32,
        choices=SIMILARITY_METRIC_CHOICES,
        default=SIMILARITY_DICE,
    )
    enrichment_version = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="DomainEnrichment.version used for the feature weights; '' for Dice",
    )
    idf_exponent = models.FloatField(
        default=1.0,
        help_text="Feature weight = idf ** idf_exponent × enrichment (ADR 0003 "
        "amendment); 1.0 for Dice and for cosine runs built before it",
    )
    prune_below = models.FloatField(
        default=0.05,
        help_text="Similarity-graph edges below this are dropped before kNN",
    )
    min_projection_similarity = models.FloatField(
        default=0.1,
        help_text="Partial iBGCs whose summed top-k similarity is below this "
        "stay unprojected",
    )
    knn_k = models.PositiveSmallIntegerField()
    leiden_resolutions = models.JSONField(
        default=list,
        help_text="CPM resolution_parameter values, coarsest first",
    )
    seed = models.PositiveIntegerField(default=42)

    n_proteins = models.PositiveIntegerField(default=0)
    n_ibgcs = models.PositiveIntegerField(default=0)
    n_levels = models.PositiveSmallIntegerField(default=0)
    n_root_communities = models.PositiveIntegerField(default=0)
    n_leaf_communities = models.PositiveIntegerField(default=0)

    igraph_version = models.CharField(max_length=50, blank=True, default="")
    leidenalg_version = models.CharField(max_length=50, blank=True, default="")
    scipy_version = models.CharField(max_length=50, blank=True, default="")

    sha256 = models.CharField(max_length=64, unique=True)

    class Meta:
        db_table = "discovery_clustering_run"
        ordering = ["-created_at"]

    def __str__(self):
        return f"ClusteringRun {self.pk} ({self.created_at:%Y-%m-%d})"


class DomainEnrichment(models.Model):
    """Frozen BGC-core vs flank enrichment weight per domain label (ADR 0003).

    ``weight = max(0.05, sigmoid(log2(p_core / p_flank)))`` with the
    pseudocount split by set size, learned on genome catalogues by
    ``manage.py build_domain_enrichment``. A ``version`` is built once and
    never changed in place: re-learning means a new version, a new
    clustering run and a fresh benchmark check. Labels are in ``vocab`` (the
    ``ClusteringRun.domain_vocab`` the version was built with); a run may only
    use a version of its own vocabulary. Labels absent from a version weigh
    0.5. ``vocab`` and ``datasets`` are the same on every row of a version.
    """

    version = models.CharField(max_length=50, db_index=True)
    vocab = models.CharField(
        max_length=20,
        choices=ClusteringRun.DOMAIN_VOCAB_CHOICES,
        help_text="Label vocabulary the version was learned on",
    )
    datasets = models.JSONField(
        default=list,
        help_text="AssemblySource names the version was learned on (sorted)",
    )
    label = models.CharField(max_length=50)
    n_core = models.PositiveIntegerField(
        default=0, help_text="Core CDS (inside GECCO/SanntiS iBGCs) carrying the label"
    )
    n_flank = models.PositiveIntegerField(
        default=0,
        help_text="Flank CDS (outside any iBGC, or antiSMASH overhang) carrying it",
    )
    weight = models.FloatField()

    class Meta:
        db_table = "discovery_domain_enrichment"
        constraints = [
            models.UniqueConstraint(
                fields=["version", "label"], name="uniq_domain_enrichment_version_label"
            ),
        ]

    def __str__(self):
        return f"{self.label} @ {self.version}: {self.weight:.3f}"


class DashboardGCF(models.Model):
    """A node in the hierarchical Leiden tree for a ``ClusteringRun``.

    One row per node at every level. The full ``family_path`` ltree string
    identifies the node uniquely; ``parent_path`` points at the immediate
    parent (empty string for level-0 roots).
    """

    id = models.AutoField(primary_key=True)
    clustering_run = models.ForeignKey(
        ClusteringRun,
        on_delete=models.CASCADE,
        related_name="gcfs",
        db_index=True,
    )
    family_path = models.CharField(
        max_length=512,
        db_index=True,
        help_text="ltree dot-path identifying this node, e.g. 42.7.3",
    )
    parent_path = models.CharField(
        max_length=512,
        blank=True,
        default="",
        db_index=True,
        help_text="Immediate parent's family_path; empty string for level-0 roots",
    )
    level = models.PositiveSmallIntegerField(
        help_text="Depth in the hierarchy (0 = coarsest root level)",
    )
    representative_ibgc = models.ForeignKey(
        IntegratedBgc,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="represented_gcfs",
    )

    member_count = models.IntegerField(
        default=0,
        help_text="Total iBGCs whose leaf path is a descendant of this node (or equal at leaves)",
    )
    validated_count = models.IntegerField(default=0)
    mean_novelty = models.FloatField(default=0.0)
    descendant_count = models.IntegerField(
        default=0,
        help_text="Number of immediate child nodes (0 for leaves)",
    )

    class Meta:
        db_table = "discovery_gcf"
        verbose_name = "GCF"
        verbose_name_plural = "GCFs"
        constraints = [
            models.UniqueConstraint(
                fields=["clustering_run", "family_path"],
                name="uniq_gcf_run_path",
            ),
        ]
        indexes = [
            models.Index(fields=["clustering_run", "level"], name="idx_gcf_run_level"),
            models.Index(
                fields=["clustering_run", "parent_path"], name="idx_gcf_run_parent"
            ),
        ]

    def __str__(self):
        return self.family_path


class IbgcClusteringSnapshot(models.Model):
    """Frozen per-iBGC classification at import time, for rollback.

    The HPC importer writes one row per primary or partial iBGC before
    overwriting the live columns on ``IntegratedBgc``. The
    ``set_active_clustering_run`` command reads these to restore a previous
    run's state without recomputing.
    """

    id = models.BigAutoField(primary_key=True)
    clustering_run = models.ForeignKey(
        ClusteringRun,
        on_delete=models.CASCADE,
        related_name="ibgc_snapshots",
    )
    ibgc = models.ForeignKey(
        IntegratedBgc,
        on_delete=models.CASCADE,
        related_name="clustering_snapshots",
    )
    is_partial = models.BooleanField(default=False)
    gene_cluster_family = models.CharField(max_length=512, blank=True, default="")
    novelty_score = models.FloatField(null=True, blank=True)
    domain_novelty = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "discovery_ibgc_clustering_snapshot"
        constraints = [
            models.UniqueConstraint(
                fields=["clustering_run", "ibgc"],
                name="uniq_snapshot_run_ibgc",
            ),
        ]
        indexes = [
            models.Index(fields=["clustering_run"], name="idx_snapshot_run"),
        ]

    def __str__(self):
        return f"snapshot(run={self.clustering_run_id}, ibgc={self.ibgc_id})"
