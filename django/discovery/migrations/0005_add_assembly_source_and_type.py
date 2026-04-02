"""Add AssemblySource lookup table, source FK, and assembly_type field."""

from django.db import migrations, models
import django.db.models.deletion


def seed_initial_sources(apps, schema_editor):
    AssemblySource = apps.get_model("discovery", "AssemblySource")
    for name in ["MGnify", "GTDB", "NCBI", "MIBiG"]:
        AssemblySource.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0004_rename_genome_to_assembly"),
    ]

    operations = [
        # ── AssemblySource lookup table ──────────────────────────────────
        migrations.CreateModel(
            name="AssemblySource",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
            options={
                "db_table": "discovery_assembly_source",
            },
        ),
        # Seed initial values
        migrations.RunPython(seed_initial_sources, migrations.RunPython.noop),
        # ── Add source FK to DashboardAssembly ───────────────────────────
        migrations.AddField(
            model_name="dashboardassembly",
            name="source",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assemblies",
                to="discovery.assemblysource",
            ),
        ),
        # ── Add assembly_type field ──────────────────────────────────────
        migrations.AddField(
            model_name="dashboardassembly",
            name="assembly_type",
            field=models.SmallIntegerField(
                choices=[(1, "metagenome"), (2, "genome"), (3, "region")],
                db_index=True,
                default=2,
            ),
        ),
    ]
