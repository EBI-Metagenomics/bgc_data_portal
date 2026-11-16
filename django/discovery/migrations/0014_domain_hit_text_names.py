"""Widen ``discovery_domain_hit`` name columns to text.

IPS6 (InterPro 107) reports some CDD signature names longer than 255
characters (e.g. cd17292, 303 chars), which made ``load_discovery_data`` fail
with ``value too long for type character varying(255)``. varchar → text is a
catalogue-only change in PostgreSQL (no table rewrite).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0013_snapshot_keyed_on_accession"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contigdomain",
            name="domain_name",
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name="contigdomain",
            name="interpro_entry_description",
            field=models.TextField(blank=True, default=""),
        ),
    ]
