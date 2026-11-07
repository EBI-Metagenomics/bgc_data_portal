"""Drop code paths nothing reads any more.

- ``IbgcNaturalProduct``: write-never since the ``load_natural_products``
  command was removed (3bdd091); the API no longer exposes it.
- ``PrecomputedStats``: no reader or writer (``DiscoveryStats`` is the live
  snapshot table).
- ``DashboardAssembly.pctl_*``: written by the score recompute, read by nothing.
- ``ClusteringRun.domain_vocab`` loses the never-used ``RAW`` choice.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0011_sanntis_v1_npclassifier"),
    ]

    operations = [
        migrations.DeleteModel(name="IbgcNaturalProduct"),
        migrations.DeleteModel(name="PrecomputedStats"),
        migrations.RemoveField(model_name="dashboardassembly", name="pctl_diversity"),
        migrations.RemoveField(model_name="dashboardassembly", name="pctl_novelty"),
        migrations.RemoveField(model_name="dashboardassembly", name="pctl_density"),
        migrations.AlterField(
            model_name="clusteringrun",
            name="domain_vocab",
            field=models.CharField(
                choices=[
                    ("IPR_PROJECTED", "IPR entry when available, else signature"),
                    (
                        "IPR_GAPFILLED",
                        "IPR-projected, plus Gene3D/PRINTS/ProSite hits that fill gaps",
                    ),
                ],
                default="IPR_PROJECTED",
                max_length=20,
            ),
        ),
    ]
