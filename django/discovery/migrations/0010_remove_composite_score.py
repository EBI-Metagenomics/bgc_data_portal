"""Remove composite_score from DashboardAssembly and related index."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0009_dashboardcds_protein_sha256"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="dashboardassembly",
            name="idx_da_composite_desc",
        ),
        migrations.RemoveField(
            model_name="dashboardassembly",
            name="composite_score",
        ),
    ]
