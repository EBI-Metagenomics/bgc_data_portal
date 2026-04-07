"""Add protein_sha256 field to DashboardCds for linking to ProteinEmbedding."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0008_validated_bgc_refactor"),
    ]

    operations = [
        migrations.AddField(
            model_name="dashboardcds",
            name="protein_sha256",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="SHA-256 hash of the amino acid sequence (links to ProteinEmbedding)",
                max_length=64,
            ),
        ),
        migrations.AddIndex(
            model_name="dashboardcds",
            index=models.Index(
                fields=["protein_sha256"],
                name="idx_dcds_prot_sha256",
            ),
        ),
    ]
