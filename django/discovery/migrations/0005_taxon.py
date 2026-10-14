"""Add ``Taxon`` and the rank-aware lineage link on ``DashboardContig``.

``DashboardContig.taxonomy_path`` is a rank-less dot-path (rank prefixes were
stripped and missing ranks skipped at ETL time), so rank cannot be inferred
from position. ``Taxon`` stores the canonical NCBI 8-rank lineage per taxid;
``DashboardContig.taxon`` points at the leaf and ``taxonomy_path_legacy``
keeps the pre-rewrite path for rollback.

Schema only: new empty table plus two nullable/defaulted columns, so it is
fast at pod start. Rows are filled by the ``apply_taxonomy_mapping`` command.
"""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


def _rank_fields():
    fields = []
    for rank in (
        "domain",
        "kingdom",
        "phylum",
        "class",
        "order",
        "family",
        "genus",
        "species",
    ):
        fields.append(
            (
                f"{rank}_name",
                models.CharField(blank=True, default="", max_length=255),
            )
        )
        fields.append((f"{rank}_taxid", models.IntegerField(blank=True, null=True)))
    return fields


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0004_ibgc_chemont"),
    ]

    operations = [
        migrations.CreateModel(
            name="Taxon",
            fields=[
                ("taxid", models.IntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                (
                    "rank",
                    models.CharField(help_text="NCBI rank of this node", max_length=32),
                ),
                (
                    "parent_taxid",
                    models.IntegerField(
                        blank=True,
                        help_text="Nearest canonical-rank ancestor",
                        null=True,
                    ),
                ),
                ("ltree_path", models.CharField(max_length=1024)),
                (
                    "deepest_informative_rank",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Deepest rank ignoring genus-less placeholder "
                        "species (e.g. 'Pseudomonadota bacterium' → phylum)",
                        max_length=16,
                    ),
                ),
                (
                    "taxdump_version",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                *_rank_fields(),
            ],
            options={
                "db_table": "discovery_taxon",
                "indexes": [
                    models.Index(fields=["phylum_taxid"], name="idx_taxon_phylum"),
                    models.Index(fields=["genus_taxid"], name="idx_taxon_genus"),
                ],
            },
        ),
        migrations.AddField(
            model_name="dashboardcontig",
            name="taxon",
            field=models.ForeignKey(
                blank=True,
                help_text="Rank-aware NCBI lineage; null until "
                "apply_taxonomy_mapping runs",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="contigs",
                to="discovery.taxon",
            ),
        ),
        migrations.AddField(
            model_name="dashboardcontig",
            name="taxonomy_path_legacy",
            field=models.CharField(
                blank=True,
                default="",
                help_text="taxonomy_path before apply_taxonomy_mapping rewrote it "
                "(kept for --revert)",
                max_length=1024,
            ),
        ),
    ]
