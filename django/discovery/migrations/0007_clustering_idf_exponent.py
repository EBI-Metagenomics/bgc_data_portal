"""Record the IDF exponent of a ``cosine_idf_enrich`` run's feature weights.

ADR 0003 amendment (Phase 4 go / no-go on the full portal corpus): feature
weights become ``idf ** p × enrichment`` with ``p = 0.5`` for new cosine
runs. Existing runs — Dice, and cosine runs built with full IDF — get
``idf_exponent = 1.0``, which is what they were built with.

Schema only: one defaulted column, fast at pod start.
"""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0006_clustering_similarity_metric"),
    ]

    operations = [
        migrations.AddField(
            model_name="clusteringrun",
            name="idf_exponent",
            field=models.FloatField(
                default=1.0,
                help_text="Feature weight = idf ** idf_exponent × enrichment (ADR 0003 "
                "amendment); 1.0 for Dice and for cosine runs built before it",
            ),
        ),
    ]
