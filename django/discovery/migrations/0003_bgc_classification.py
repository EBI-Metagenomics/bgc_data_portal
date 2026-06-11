"""Add raw + normalised BGC product-class fields.

``SourceBgcPrediction.classification_path`` stores the raw per-tool product
class as staged (shown on prediction hover). ``IntegratedBgc.bgc_class`` holds
the normalised label derived by unioning an iBGC's predictions
(``common_core.bgc_class.classify_ibgc``) and feeds the "BGC Class" filter.

Both are added nullable-safe (blank default "") so the migration is a no-op on
existing rows; the values are backfilled by re-ingestion + the score/stats
recompute.
"""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0002_compact_gcf_paths"),
    ]

    operations = [
        migrations.AddField(
            model_name="sourcebgcprediction",
            name="classification_path",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text=(
                    "Raw per-tool product class as staged (e.g. 'NRPS_T1PKS', "
                    "'RiPP_like', 'NRP_Polyketide'). Shown verbatim on "
                    "prediction hover; normalised into IntegratedBgc.bgc_class "
                    "at iBGC level."
                ),
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="integratedbgc",
            name="bgc_class",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text=(
                    "Normalised product class — one of Polyketide / NRP / RiPP "
                    "/ Terpene / Saccharide / Alkaloid / Other / Hybrid(P+N) / "
                    "Hybrid. Derived by unioning the classification_path of all "
                    "source predictions (common_core.bgc_class.classify_ibgc)."
                ),
                max_length=32,
            ),
        ),
    ]
