"""Add ``is_partial`` to iBGCs and clustering snapshots (additive, migration A).

``is_partial`` replaces ``umap_projected`` as the "not in the primary
clustering pass; GCF / novelty projected from top-K primary neighbours" flag,
ahead of dropping the UMAP layout (0010). Backfilled from ``umap_projected``
so readers can switch before the UMAP columns go.

Additive and reversible; the backfill touches only rows with
``umap_projected = true`` (~150k of ~400k iBGCs on the 2026-10 corpus).
"""

from __future__ import annotations

from django.db import migrations, models

_HELP = (
    "True when the iBGC was not in the primary clustering pass and its "
    "GCF / novelty were projected from its top-K nearest primary iBGCs. "
    "False when it was clustered directly."
)


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0007_clustering_idf_exponent"),
    ]

    operations = [
        migrations.AddField(
            model_name="integratedbgc",
            name="is_partial",
            field=models.BooleanField(default=False, help_text=_HELP),
        ),
        migrations.AddField(
            model_name="ibgcclusteringsnapshot",
            name="is_partial",
            field=models.BooleanField(default=False),
        ),
        migrations.RunSQL(
            sql=[
                "UPDATE discovery_ibgc SET is_partial = TRUE WHERE umap_projected;",
                "UPDATE discovery_ibgc_clustering_snapshot SET is_partial = TRUE "
                "WHERE umap_projected;",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
