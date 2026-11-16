"""Key clustering snapshots on the iBGC accession instead of the row id.

``build_integrated_bgcs`` recreates every IntegratedBgc row; the old FK
cascaded the snapshots away, so ``set_active_clustering_run`` could not roll
back after a rebuild. Accessions are stable through the registry.
"""

from django.db import migrations, models


def copy_accessions(apps, schema_editor):
    Snapshot = apps.get_model("discovery", "IbgcClusteringSnapshot")
    IntegratedBgc = apps.get_model("discovery", "IntegratedBgc")
    accession_of = dict(IntegratedBgc.objects.values_list("id", "accession"))
    batch = []
    for snap in Snapshot.objects.only("id", "ibgc_id").iterator():
        snap.ibgc_accession = accession_of.get(snap.ibgc_id, "")
        batch.append(snap)
        if len(batch) >= 5000:
            Snapshot.objects.bulk_update(batch, ["ibgc_accession"])
            batch = []
    if batch:
        Snapshot.objects.bulk_update(batch, ["ibgc_accession"])


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0012_drop_unused_tables_and_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="ibgcclusteringsnapshot",
            name="ibgc_accession",
            field=models.CharField(db_index=True, default="", max_length=20),
            preserve_default=False,
        ),
        migrations.RunPython(copy_accessions, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="ibgcclusteringsnapshot",
            name="uniq_snapshot_run_ibgc",
        ),
        migrations.RemoveField(model_name="ibgcclusteringsnapshot", name="ibgc"),
        migrations.AddConstraint(
            model_name="ibgcclusteringsnapshot",
            constraint=models.UniqueConstraint(
                fields=("clustering_run", "ibgc_accession"),
                name="uniq_snapshot_run_ibgc_accession",
            ),
        ),
    ]
