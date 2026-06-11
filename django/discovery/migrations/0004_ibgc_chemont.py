"""Add ``IbgcChemOnt`` — per-iBGC ChemOnt classes from characterised structures.

Populated by running ClassyFire on ``IbgcNaturalProduct`` SMILES (the
``classify_ibgc_natural_products`` command). Complements the gene-based
``CdsChemOnt`` (CHAMOIS) predictions; the chemical-similarity search and the
ChemOnt IC computation pool both sources per iBGC. New empty table, so the
migration is a no-op on existing data until the classifier command runs.
"""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0003_bgc_classification"),
    ]

    operations = [
        migrations.CreateModel(
            name="IbgcChemOnt",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("chemont_id", models.CharField(max_length=30)),
                (
                    "chemont_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("inchikey", models.CharField(blank=True, default="", max_length=27)),
                (
                    "ibgc",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="structure_chemont",
                        to="discovery.integratedbgc",
                    ),
                ),
            ],
            options={
                "db_table": "discovery_ibgc_chemont",
            },
        ),
        migrations.AddConstraint(
            model_name="ibgcchemont",
            constraint=models.UniqueConstraint(
                fields=["ibgc", "chemont_id"], name="uniq_ibgcchemont_ibgc_cid"
            ),
        ),
        migrations.AddIndex(
            model_name="ibgcchemont",
            index=models.Index(fields=["chemont_id"], name="idx_ibgcchemont_cid"),
        ),
        migrations.AddIndex(
            model_name="ibgcchemont",
            index=models.Index(fields=["ibgc"], name="idx_ibgcchemont_ibgc"),
        ),
    ]
