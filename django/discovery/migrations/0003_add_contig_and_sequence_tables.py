"""Add DashboardContig, ContigSequence, CdsSequence models.

Introduces contig storage with zlib-compressed sequences in a separate
on-demand table. Adds contig FK to DashboardBgc. Moves DashboardCds amino
acid sequences to a dedicated CdsSequence table.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0002_dashboard_models"),
    ]

    operations = [
        # ── DashboardContig ──────────────────────────────────────────────
        migrations.CreateModel(
            name="DashboardContig",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "genome",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contigs",
                        to="discovery.dashboardgenome",
                    ),
                ),
                ("accession", models.CharField(db_index=True, max_length=255)),
                ("length", models.IntegerField(default=0)),
                (
                    "source_contig_id",
                    models.IntegerField(db_index=True, unique=True),
                ),
            ],
            options={
                "db_table": "discovery_contig",
            },
        ),
        # ── ContigSequence ───────────────────────────────────────────────
        migrations.CreateModel(
            name="ContigSequence",
            fields=[
                (
                    "contig",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="seq",
                        serialize=False,
                        to="discovery.dashboardcontig",
                    ),
                ),
                (
                    "data",
                    models.BinaryField(
                        help_text="zlib-compressed nucleotide sequence"
                    ),
                ),
            ],
            options={
                "db_table": "discovery_contig_sequence",
            },
        ),
        # ── Add contig FK to DashboardBgc ────────────────────────────────
        migrations.AddField(
            model_name="dashboardbgc",
            name="contig",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bgcs",
                to="discovery.dashboardcontig",
            ),
        ),
        # ── CdsSequence ─────────────────────────────────────────────────
        migrations.CreateModel(
            name="CdsSequence",
            fields=[
                (
                    "cds",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="seq",
                        serialize=False,
                        to="discovery.dashboardcds",
                    ),
                ),
                (
                    "data",
                    models.BinaryField(
                        help_text="zlib-compressed amino acid sequence"
                    ),
                ),
            ],
            options={
                "db_table": "discovery_cds_sequence",
            },
        ),
        # ── Remove old sequence field from DashboardCds ──────────────────
        migrations.RemoveField(
            model_name="dashboardcds",
            name="sequence",
        ),
    ]
