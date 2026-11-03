"""Drop the UMAP layout and the ChemOnt stack (destructive, migration B).

* ``CdsChemOnt`` (CHAMOIS per-CDS ChemOnt) and ``IbgcChemOnt``
  (ClassyFire classes of curated structures) are deleted.
* ``umap_x`` / ``umap_y`` / ``umap_projected`` go from iBGCs and clustering
  snapshots (``is_partial`` replaced ``umap_projected`` in 0008), and
  ``ClusteringRun.umap_version`` goes.
* The ``chemont_ic`` / ``chemont_sunburst`` ``PrecomputedStats`` rows are
  deleted.

Take the ``pg_dump`` backup listed in the removal plan before applying this
on production. Not reversible for data: reversing recreates empty columns and
tables only.
"""

from __future__ import annotations

from django.db import migrations

_CHEMONT_STATS = ("chemont_ic", "chemont_sunburst")


def _delete_chemont_stats(apps, schema_editor):
    PrecomputedStats = apps.get_model("discovery", "PrecomputedStats")
    PrecomputedStats.objects.filter(key__in=_CHEMONT_STATS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0009_drop_pgvector"),
    ]

    operations = [
        migrations.RunPython(_delete_chemont_stats, migrations.RunPython.noop),
        migrations.DeleteModel(name="CdsChemOnt"),
        migrations.DeleteModel(name="IbgcChemOnt"),
        migrations.RemoveField(model_name="integratedbgc", name="umap_x"),
        migrations.RemoveField(model_name="integratedbgc", name="umap_y"),
        migrations.RemoveField(model_name="integratedbgc", name="umap_projected"),
        migrations.RemoveField(model_name="ibgcclusteringsnapshot", name="umap_x"),
        migrations.RemoveField(model_name="ibgcclusteringsnapshot", name="umap_y"),
        migrations.RemoveField(
            model_name="ibgcclusteringsnapshot", name="umap_projected"
        ),
        migrations.RemoveField(model_name="clusteringrun", name="umap_version"),
    ]
