from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0010_remove_composite_score"),
    ]

    operations = [
        migrations.CreateModel(
            name="NaturalProductChemOntClass",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "chemont_id",
                    models.CharField(
                        help_text="ChemOnt ontology term ID, e.g. CHEMONTID:0000147",
                        max_length=30,
                    ),
                ),
                ("chemont_name", models.CharField(max_length=255)),
                ("probability", models.FloatField(default=1.0)),
                (
                    "natural_product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chemont_classes",
                        to="discovery.dashboardnaturalproduct",
                    ),
                ),
            ],
            options={
                "db_table": "discovery_np_chemont_class",
                "unique_together": {("natural_product", "chemont_id")},
            },
        ),
        migrations.AddIndex(
            model_name="naturalproductchemontclass",
            index=models.Index(
                fields=["chemont_id"], name="idx_npchemont_cid"
            ),
        ),
        migrations.AddIndex(
            model_name="naturalproductchemontclass",
            index=models.Index(
                fields=["natural_product"], name="idx_npchemont_np"
            ),
        ),
    ]
