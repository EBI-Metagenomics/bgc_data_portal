"""Record the iBGC similarity metric per ``ClusteringRun`` and add ``DomainEnrichment``.

ADR 0003: iBGC similarity moves from binary composite Dice to an IDF ×
enrichment weighted cosine over a gap-filled vocabulary. Existing runs keep
``similarity_metric="dice"`` and the thresholds they were built with
(``prune_below=0.05``, ``min_projection_similarity=0.1``), so rollback to
them is unchanged. ``DomainEnrichment`` holds the frozen, versioned
enrichment table.

Schema only: four defaulted columns plus one new empty table, so it is fast
at pod start. Rows are filled by ``build_domain_enrichment``.
"""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0005_taxon"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clusteringrun",
            name="domain_vocab",
            field=models.CharField(
                choices=[
                    ("RAW", "Raw signature accessions"),
                    ("IPR_PROJECTED", "IPR entry when available, else signature"),
                    (
                        "IPR_GAPFILLED",
                        "IPR-projected, plus Gene3D/PRINTS/ProSite hits that fill gaps",
                    ),
                ],
                default="IPR_PROJECTED",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="clusteringrun",
            name="similarity_metric",
            field=models.CharField(
                choices=[
                    ("dice", "Binary composite Dice"),
                    ("cosine_idf_enrich", "IDF × enrichment weighted cosine"),
                ],
                default="dice",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="clusteringrun",
            name="enrichment_version",
            field=models.CharField(
                blank=True,
                default="",
                help_text="DomainEnrichment.version used for the feature weights; "
                "'' for Dice",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="clusteringrun",
            name="prune_below",
            field=models.FloatField(
                default=0.05,
                help_text="Similarity-graph edges below this are dropped before kNN",
            ),
        ),
        migrations.AddField(
            model_name="clusteringrun",
            name="min_projection_similarity",
            field=models.FloatField(
                default=0.1,
                help_text="Partial iBGCs whose summed top-k similarity is below "
                "this stay unprojected",
            ),
        ),
        migrations.CreateModel(
            name="DomainEnrichment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("version", models.CharField(db_index=True, max_length=50)),
                (
                    "vocab",
                    models.CharField(
                        choices=[
                            ("RAW", "Raw signature accessions"),
                            (
                                "IPR_PROJECTED",
                                "IPR entry when available, else signature",
                            ),
                            (
                                "IPR_GAPFILLED",
                                "IPR-projected, plus Gene3D/PRINTS/ProSite hits "
                                "that fill gaps",
                            ),
                        ],
                        help_text="Label vocabulary the version was learned on",
                        max_length=20,
                    ),
                ),
                (
                    "datasets",
                    models.JSONField(
                        default=list,
                        help_text="AssemblySource names the version was learned on "
                        "(sorted)",
                    ),
                ),
                ("label", models.CharField(max_length=50)),
                (
                    "n_core",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Core CDS (inside GECCO/SanntiS iBGCs) carrying "
                        "the label",
                    ),
                ),
                (
                    "n_flank",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Flank CDS (outside any iBGC, or antiSMASH "
                        "overhang) carrying it",
                    ),
                ),
                ("weight", models.FloatField()),
            ],
            options={
                "db_table": "discovery_domain_enrichment",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("version", "label"),
                        name="uniq_domain_enrichment_version_label",
                    )
                ],
            },
        ),
    ]
