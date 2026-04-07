"""Schema simplification + register existing models (Detector, Region, Alias).

Registers DashboardDetector, DashboardRegion, RegionAccessionAlias into Django's
migration state (tables already exist in DB from seed_discovery_data), then:

- Assembly: remove assembly_quality, isolation_source, dominant_taxonomy_*,
  source_assembly_id
- Contig: add sequence_sha256 (unique), make accession/source_contig_id optional
- BGC: remove classification_l1/l2/l3, source_bgc_id, source_contig_id,
  contig_accession, detector_names; add detector FK, region FK, bgc_number;
  make contig NOT NULL; add composite unique constraint
- NaturalProduct: remove chemical_class_l1/l2/l3, producing_organism

All discovery tables are truncated before schema changes since data is always
bulk-loaded via load_discovery_data.
"""

from django.db import migrations, models
import django.db.models.deletion


def truncate_discovery_tables(apps, schema_editor):
    """Truncate all discovery tables so NOT NULL / unique changes apply cleanly."""
    tables = [
        "discovery_region_accession_alias",
        "discovery_bgc_embedding",
        "discovery_bgc_domain",
        "discovery_cds_sequence",
        "discovery_cds",
        "discovery_natural_product",
        "discovery_mibig_reference",
        "discovery_gcf",
        "discovery_precomputed_stats",
        "discovery_bgc",
        "discovery_region",
        "discovery_contig_sequence",
        "discovery_contig",
        "discovery_assembly",
        "discovery_detector",
        "discovery_bgc_class",
        "discovery_domain",
    ]
    with schema_editor.connection.cursor() as cursor:
        for table in tables:
            cursor.execute(
                "DO $$ BEGIN "
                f"  EXECUTE 'TRUNCATE TABLE {table} CASCADE'; "
                "EXCEPTION WHEN undefined_table THEN NULL; END $$;"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0006_taxonomy_to_contig"),
    ]

    operations = [
        # ── Truncate existing data ───────────────────────────────────────
        migrations.RunPython(truncate_discovery_tables, migrations.RunPython.noop),

        # ── Register existing models (tables already in DB) ──────────────
        # SeparateDatabaseAndState: state_operations update Django's internal
        # model registry; database_operations are empty since tables exist.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="DashboardDetector",
                    fields=[
                        ("id", models.AutoField(primary_key=True, serialize=False)),
                        ("name", models.CharField(
                            db_index=True, max_length=255, unique=True,
                            help_text='Human-readable label, e.g. "antiSMASH v7.1"',
                        )),
                        ("tool", models.CharField(
                            max_length=255, help_text='Tool name, e.g. "antiSMASH"',
                        )),
                        ("version", models.CharField(
                            max_length=50, help_text='Semver string, e.g. "7.1.0"',
                        )),
                        ("tool_name_code", models.CharField(
                            max_length=3, help_text='3-letter uppercase code, e.g. "ANT"',
                        )),
                        ("version_sort_key", models.PositiveIntegerField(
                            default=0,
                            help_text="Monotonic integer for DB-level version ordering",
                        )),
                    ],
                    options={"db_table": "discovery_detector"},
                ),
                migrations.AddConstraint(
                    model_name="dashboarddetector",
                    constraint=models.UniqueConstraint(
                        fields=["tool", "version"],
                        name="uniq_detector_tool_version",
                    ),
                ),
                migrations.CreateModel(
                    name="DashboardRegion",
                    fields=[
                        ("id", models.BigAutoField(
                            primary_key=True, serialize=False,
                        )),
                        ("contig", models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name="regions",
                            to="discovery.dashboardcontig",
                            db_index=True,
                        )),
                        ("start_position", models.IntegerField()),
                        ("end_position", models.IntegerField()),
                    ],
                    options={"db_table": "discovery_region"},
                ),
                migrations.AddConstraint(
                    model_name="dashboardregion",
                    constraint=models.UniqueConstraint(
                        fields=["contig", "start_position", "end_position"],
                        name="uniq_region_contig_pos",
                    ),
                ),
                migrations.AddIndex(
                    model_name="dashboardregion",
                    index=models.Index(
                        fields=["contig", "start_position", "end_position"],
                        name="idx_region_contig_pos",
                    ),
                ),
                migrations.CreateModel(
                    name="RegionAccessionAlias",
                    fields=[
                        ("id", models.AutoField(
                            primary_key=True, serialize=False,
                        )),
                        ("alias_accession", models.CharField(
                            db_index=True, max_length=50, unique=True,
                        )),
                        ("region", models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name="aliases",
                            to="discovery.dashboardregion",
                        )),
                    ],
                    options={"db_table": "discovery_region_accession_alias"},
                ),
            ],
            database_operations=[],
        ),

        # ── DashboardAssembly: remove fields ─────────────────────────────
        migrations.RemoveIndex(
            model_name="dashboardassembly",
            name="idx_da_dom_tax",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="dominant_taxonomy_path",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="dominant_taxonomy_label",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="assembly_quality",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="isolation_source",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="source_assembly_id",
        ),

        # ── DashboardContig: add sequence_sha256, alter fields ───────────
        migrations.AddField(
            model_name="dashboardcontig",
            name="sequence_sha256",
            field=models.CharField(
                db_index=True, max_length=64, unique=True, default="",
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="dashboardcontig",
            name="accession",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="dashboardcontig",
            name="source_contig_id",
            field=models.IntegerField(
                blank=True, db_index=True, null=True,
            ),
        ),

        # ── DashboardBgc: remove fields ──────────────────────────────────
        migrations.RemoveField(
            model_name="dashboardbgc",
            name="classification_l1",
        ),
        migrations.RemoveField(
            model_name="dashboardbgc",
            name="classification_l2",
        ),
        migrations.RemoveField(
            model_name="dashboardbgc",
            name="classification_l3",
        ),
        migrations.RemoveField(
            model_name="dashboardbgc",
            name="source_bgc_id",
        ),
        migrations.RemoveField(
            model_name="dashboardbgc",
            name="source_contig_id",
        ),
        migrations.RemoveField(
            model_name="dashboardbgc",
            name="contig_accession",
        ),
        migrations.RemoveField(
            model_name="dashboardbgc",
            name="detector_names",
        ),

        # ── DashboardBgc: alter contig FK (NOT NULL) ─────────────────────
        migrations.AlterField(
            model_name="dashboardbgc",
            name="contig",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bgcs",
                to="discovery.dashboardcontig",
                db_index=True,
            ),
        ),

        # ── DashboardBgc: add detector FK, region FK, bgc_number ────────
        # These fields exist in the DB table already (added by seed command)
        # but are not in Django's migration state. Use SeparateDatabaseAndState.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="dashboardbgc",
                    name="detector",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bgcs",
                        to="discovery.dashboarddetector",
                        db_index=True,
                    ),
                ),
                migrations.AddField(
                    model_name="dashboardbgc",
                    name="region",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bgcs",
                        to="discovery.dashboardregion",
                        db_index=True,
                    ),
                ),
                migrations.AddField(
                    model_name="dashboardbgc",
                    name="bgc_number",
                    field=models.PositiveSmallIntegerField(
                        default=0,
                        help_text="2-digit incremental within region + detector",
                    ),
                ),
            ],
            database_operations=[],
        ),

        # ── DashboardBgc: composite unique constraint ────────────────────
        # Use RunSQL since the constraint may or may not exist in the DB,
        # plus SeparateDatabaseAndState for state registration.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddConstraint(
                    model_name="dashboardbgc",
                    constraint=models.UniqueConstraint(
                        fields=[
                            "contig", "start_position",
                            "end_position", "detector",
                        ],
                        name="uniq_bgc_contig_pos_detector",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE discovery_bgc "
                        "ADD CONSTRAINT uniq_bgc_contig_pos_detector "
                        "UNIQUE (contig_id, start_position, end_position, detector_id)"
                    ),
                    reverse_sql=(
                        "ALTER TABLE discovery_bgc "
                        "DROP CONSTRAINT IF EXISTS uniq_bgc_contig_pos_detector"
                    ),
                ),
            ],
        ),

        # ── DashboardNaturalProduct: remove fields, swap index ───────────
        migrations.RemoveIndex(
            model_name="dashboardnaturalproduct",
            name="idx_dnp_class_l1",
        ),
        migrations.RemoveField(
            model_name="dashboardnaturalproduct",
            name="chemical_class_l1",
        ),
        migrations.RemoveField(
            model_name="dashboardnaturalproduct",
            name="chemical_class_l2",
        ),
        migrations.RemoveField(
            model_name="dashboardnaturalproduct",
            name="chemical_class_l3",
        ),
        migrations.RemoveField(
            model_name="dashboardnaturalproduct",
            name="producing_organism",
        ),
        migrations.AddIndex(
            model_name="dashboardnaturalproduct",
            index=models.Index(
                fields=["np_class_path"], name="idx_dnp_class_path",
            ),
        ),
    ]
