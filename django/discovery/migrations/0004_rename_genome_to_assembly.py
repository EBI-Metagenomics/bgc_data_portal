"""Rename DashboardGenome to DashboardAssembly.

Renames the model, table, fields, foreign keys, and indexes
from 'genome' nomenclature to 'assembly'.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0003_add_contig_and_sequence_tables"),
    ]

    operations = [
        # ── Rename model ─────────────────────────────────────────────────
        migrations.RenameModel(
            old_name="DashboardGenome",
            new_name="DashboardAssembly",
        ),
        # ── Rename table ─────────────────────────────────────────────────
        migrations.AlterModelTable(
            name="dashboardassembly",
            table="discovery_assembly",
        ),
        # ── Rename fields on DashboardAssembly ───────────────────────────
        migrations.RenameField(
            model_name="dashboardassembly",
            old_name="genome_size_mb",
            new_name="assembly_size_mb",
        ),
        migrations.RenameField(
            model_name="dashboardassembly",
            old_name="genome_quality",
            new_name="assembly_quality",
        ),
        # ── Rename FK fields on related models ───────────────────────────
        migrations.RenameField(
            model_name="dashboardcontig",
            old_name="genome",
            new_name="assembly",
        ),
        migrations.RenameField(
            model_name="dashboardbgc",
            old_name="genome",
            new_name="assembly",
        ),
        # ── Rename indexes on DashboardAssembly ──────────────────────────
        migrations.RenameIndex(
            model_name="dashboardassembly",
            old_name="idx_dg_composite_desc",
            new_name="idx_da_composite_desc",
        ),
        migrations.RenameIndex(
            model_name="dashboardassembly",
            old_name="idx_dg_novelty_desc",
            new_name="idx_da_novelty_desc",
        ),
        migrations.RenameIndex(
            model_name="dashboardassembly",
            old_name="idx_dg_diversity_desc",
            new_name="idx_da_diversity_desc",
        ),
        migrations.RenameIndex(
            model_name="dashboardassembly",
            old_name="idx_dg_density_desc",
            new_name="idx_da_density_desc",
        ),
        migrations.RenameIndex(
            model_name="dashboardassembly",
            old_name="idx_dg_tax_kingdom",
            new_name="idx_da_tax_kingdom",
        ),
        migrations.RenameIndex(
            model_name="dashboardassembly",
            old_name="idx_dg_tax_phylum",
            new_name="idx_da_tax_phylum",
        ),
        migrations.RenameIndex(
            model_name="dashboardassembly",
            old_name="idx_dg_tax_family",
            new_name="idx_da_tax_family",
        ),
        migrations.RenameIndex(
            model_name="dashboardassembly",
            old_name="idx_dg_tax_genus",
            new_name="idx_da_tax_genus",
        ),
        migrations.RenameIndex(
            model_name="dashboardassembly",
            old_name="idx_dg_organism",
            new_name="idx_da_organism",
        ),
        migrations.RenameIndex(
            model_name="dashboardassembly",
            old_name="idx_dg_biome",
            new_name="idx_da_biome",
        ),
        # ── Rename index on DashboardBgc ─────────────────────────────────
        migrations.RenameIndex(
            model_name="dashboardbgc",
            old_name="idx_db_genome_novelty",
            new_name="idx_db_assembly_novelty",
        ),
    ]
