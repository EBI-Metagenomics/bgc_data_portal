"""Move taxonomy from Assembly to Contig.

Adds taxonomy_path to DashboardContig, adds dominant_taxonomy_path and
dominant_taxonomy_label to DashboardAssembly, removes individual taxonomy
columns from DashboardAssembly.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0005_add_assembly_source_and_type"),
    ]

    operations = [
        # ── Add taxonomy_path to DashboardContig ─────────────────────────
        migrations.AddField(
            model_name="dashboardcontig",
            name="taxonomy_path",
            field=models.CharField(
                blank=True,
                default="",
                help_text="ltree dot-path, e.g. Bacteria.Actinomycetota.Actinomycetia...",
                max_length=1024,
            ),
        ),
        migrations.AddIndex(
            model_name="dashboardcontig",
            index=models.Index(
                fields=["taxonomy_path"], name="idx_dcontig_tax_path"
            ),
        ),
        # ── Add dominant taxonomy to DashboardAssembly ───────────────────
        migrations.AddField(
            model_name="dashboardassembly",
            name="dominant_taxonomy_path",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Most common taxonomy_path among contigs, or empty if mixed",
                max_length=1024,
            ),
        ),
        migrations.AddField(
            model_name="dashboardassembly",
            name="dominant_taxonomy_label",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Species name or 'Mixed (N taxa)'",
                max_length=255,
            ),
        ),
        migrations.AddIndex(
            model_name="dashboardassembly",
            index=models.Index(
                fields=["dominant_taxonomy_path"], name="idx_da_dom_tax"
            ),
        ),
        # ── Remove individual taxonomy columns from DashboardAssembly ────
        migrations.RemoveIndex(
            model_name="dashboardassembly",
            name="idx_da_tax_kingdom",
        ),
        migrations.RemoveIndex(
            model_name="dashboardassembly",
            name="idx_da_tax_phylum",
        ),
        migrations.RemoveIndex(
            model_name="dashboardassembly",
            name="idx_da_tax_family",
        ),
        migrations.RemoveIndex(
            model_name="dashboardassembly",
            name="idx_da_tax_genus",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="taxonomy_path",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="taxonomy_kingdom",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="taxonomy_phylum",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="taxonomy_class",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="taxonomy_order",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="taxonomy_family",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="taxonomy_genus",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="taxonomy_species",
        ),
        # ── GiST index for ltree queries on contig taxonomy ──────────────
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS idx_dcontig_tax_ltree ON discovery_contig USING gist ((taxonomy_path::ltree));",
            reverse_sql="DROP INDEX IF EXISTS idx_dcontig_tax_ltree;",
        ),
    ]
