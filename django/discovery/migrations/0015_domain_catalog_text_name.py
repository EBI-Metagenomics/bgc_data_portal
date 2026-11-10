"""Widen ``discovery_domain.name`` to text.

``_rebuild_catalog_tables`` copies ``ContigDomain.domain_name`` (text since
0014) into the domain catalog; IPS6 CDD names longer than 255 characters made
``build_integrated_bgcs`` fail there. varchar → text is catalogue-only.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0014_domain_hit_text_names"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dashboarddomain",
            name="name",
            field=models.TextField(),
        ),
    ]
