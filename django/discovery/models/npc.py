"""NPClassifier ontology (pathway -> superclass -> class) and per-BGC / per-iBGC labels."""

from django.db import models

from .bgc import IntegratedBgc, SourceBgcPrediction


class NpcTerm(models.Model):
    """One NPClassifier ontology term (``NPC:<level>:<slug>``).

    The vocabulary is the frozen NPClassifier index SanntiS 1.0 ships, vendored
    in ``common_core.npc`` and loaded by ``load_npc_ontology``. It is a DAG: a
    few superclasses hang under two pathways (``NpcTermEdge``), so search
    expands a selected term to its descendants through the edges rather than
    through a materialised path.
    """

    LEVELS = ("pathway", "superclass", "class")

    term_id = models.CharField(max_length=128, primary_key=True)
    level = models.CharField(max_length=16, db_index=True)
    name = models.CharField(max_length=255)
    ontology_version = models.CharField(max_length=64)

    class Meta:
        db_table = "discovery_npc_term"
        indexes = [
            models.Index(fields=["level", "name"], name="idx_npc_term_level_name")
        ]

    def __str__(self):
        return f"{self.level}:{self.name}"


class NpcTermEdge(models.Model):
    """``child`` is one level below ``parent`` (class → superclass → pathway)."""

    id = models.AutoField(primary_key=True)
    child = models.ForeignKey(
        NpcTerm, on_delete=models.CASCADE, related_name="parent_edges"
    )
    parent = models.ForeignKey(
        NpcTerm, on_delete=models.CASCADE, related_name="child_edges"
    )

    class Meta:
        db_table = "discovery_npc_term_edge"
        constraints = [
            models.UniqueConstraint(fields=["child", "parent"], name="uniq_npc_edge"),
        ]


class SourceBgcNpcLabel(models.Model):
    """NPClassifier label of one source prediction (``bgc_np_classes.tsv`` row).

    ``source`` is ``predicted`` (SanntiS 1.0: pathway(s) at or above threshold,
    top superclass) or ``curated`` (MIBiG compound labels). ``confident`` is the
    detector's abstention verdict (SanntiS ``npc_pathway_confident`` /
    ``npc_superclass != unassigned``; always true for curated labels).
    """

    SOURCE_PREDICTED = "predicted"
    SOURCE_CURATED = "curated"

    id = models.BigAutoField(primary_key=True)
    source_bgc = models.ForeignKey(
        SourceBgcPrediction, on_delete=models.CASCADE, related_name="npc_labels"
    )
    term = models.ForeignKey(
        NpcTerm, on_delete=models.CASCADE, related_name="source_labels"
    )
    rank = models.PositiveSmallIntegerField(default=1)
    score = models.FloatField(null=True, blank=True)
    confident = models.BooleanField(default=False)
    source = models.CharField(max_length=16, default=SOURCE_PREDICTED)

    class Meta:
        db_table = "discovery_source_bgc_npc_label"
        constraints = [
            models.UniqueConstraint(
                fields=["source_bgc", "term", "source"], name="uniq_sbgc_npc_label"
            ),
        ]
        indexes = [models.Index(fields=["term"], name="idx_sbgc_npc_term")]


class IbgcNpcLabel(models.Model):
    """NPClassifier label of an iBGC: the union of its source predictions' labels.

    Rebuilt by ``aggregate_ibgc_npc_labels`` after ``build_integrated_bgcs``:
    one row per (iBGC, term) with the best score, ``confident`` when any member
    label is confident, and the contributing detector tools / sources. The
    ``npc_terms`` filter, the iBGC detail badges and the NPC sunburst read this
    table.
    """

    id = models.BigAutoField(primary_key=True)
    ibgc = models.ForeignKey(
        IntegratedBgc, on_delete=models.CASCADE, related_name="npc_labels"
    )
    term = models.ForeignKey(
        NpcTerm, on_delete=models.CASCADE, related_name="ibgc_labels"
    )
    score = models.FloatField(null=True, blank=True)
    confident = models.BooleanField(default=False)
    sources = models.JSONField(
        default=list, help_text='e.g. ["predicted"] or ["curated"]'
    )
    detector_tools = models.JSONField(default=list, help_text='e.g. ["SanntiS"]')
    n_predictions = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "discovery_ibgc_npc_label"
        constraints = [
            models.UniqueConstraint(
                fields=["ibgc", "term"], name="uniq_ibgc_npc_label"
            ),
        ]
        indexes = [
            models.Index(fields=["term", "confident"], name="idx_ibgc_npc_term_conf"),
            models.Index(fields=["ibgc"], name="idx_ibgc_npc_ibgc"),
        ]
