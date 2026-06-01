"""Add InterPro entry + GO terms columns to BgcDomain.

Captures the InterPro entry that each signature maps to (col 11 of the
InterProScan TSV, populated when ``--iprlookup`` is on) and the list of
GO term accessions associated with that signature (col 13 of the
InterProScan TSV, populated when ``--goterms`` is on).

Backfilled as empty / empty-list for existing rows; the ETL loader
populates them from the next ingestion.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0020_drop_embeddings"),
    ]

    operations = [
        migrations.AddField(
            model_name="bgcdomain",
            name="interpro_entry_acc",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="bgcdomain",
            name="interpro_entry_description",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="bgcdomain",
            name="go_terms",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
