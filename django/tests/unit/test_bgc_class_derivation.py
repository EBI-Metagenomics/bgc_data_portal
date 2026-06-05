"""iBGC product-class derivation, catalog rebuild and filter wiring.

``recompute_ibgc_classes`` unions every source prediction's
``classification_path`` per iBGC and stores the normalised label on
``IntegratedBgc.bgc_class`` (logic lives in ``common_core.bgc_class``). The
"BGC Class" filter matches that column, with "Hybrid" subsuming "Hybrid(P+N)".
"""

from __future__ import annotations

import pytest

from discovery.models import DashboardBgcClass
from discovery.services.scores import _rebuild_catalog_tables, recompute_ibgc_classes
from tests.factories.discovery_models import (
    DashboardDetectorFactory,
    IntegratedBgcFactory,
    SourceBgcPredictionFactory,
)

pytestmark = pytest.mark.django_db


def _attach(ibgc, tool, tool_code, raw):
    detector = DashboardDetectorFactory(
        name=f"{tool} {raw}", tool=tool, tool_name_code=tool_code
    )
    return SourceBgcPredictionFactory(
        contig=ibgc.contig,
        integrated_bgc=ibgc,
        detector=detector,
        classification_path=raw,
        start_pos=ibgc.bgc_range.lower,
        end_pos=ibgc.bgc_range.upper,
    )


def test_single_tool_single_class():
    ibgc = IntegratedBgcFactory()
    _attach(ibgc, "antiSMASH", "ANT", "T1PKS")
    recompute_ibgc_classes()
    ibgc.refresh_from_db()
    assert ibgc.bgc_class == "Polyketide"


def test_union_across_tools_yields_hybrid_pn():
    # antiSMASH says Polyketide, GECCO says NRP -> union -> Hybrid(P+N)
    ibgc = IntegratedBgcFactory()
    _attach(ibgc, "antiSMASH", "ANT", "T1PKS")
    _attach(ibgc, "GECCO", "GEC", "NRP")
    recompute_ibgc_classes()
    ibgc.refresh_from_db()
    assert ibgc.bgc_class == "Hybrid(P+N)"


def test_other_only_is_other():
    ibgc = IntegratedBgcFactory()
    _attach(ibgc, "GECCO", "GEC", "Unknown")
    recompute_ibgc_classes()
    ibgc.refresh_from_db()
    assert ibgc.bgc_class == "Other"


def test_no_classification_path_stays_blank():
    ibgc = IntegratedBgcFactory()
    _attach(ibgc, "antiSMASH", "ANT", "")
    recompute_ibgc_classes()
    ibgc.refresh_from_db()
    assert ibgc.bgc_class == ""


def test_catalog_rebuild_counts_distinct_ibgcs_per_label():
    a = IntegratedBgcFactory()
    b = IntegratedBgcFactory()
    c = IntegratedBgcFactory()
    _attach(a, "antiSMASH", "ANT", "terpene")
    _attach(b, "antiSMASH", "ANT", "terpene")
    _attach(c, "antiSMASH", "ANT", "NRPS_T1PKS")  # Hybrid(P+N)
    recompute_ibgc_classes()
    _rebuild_catalog_tables()

    counts = dict(DashboardBgcClass.objects.values_list("name", "bgc_count"))
    assert counts.get("Terpene") == 2
    assert counts.get("Hybrid(P+N)") == 1
    # Blank labels never reach the catalog.
    assert "" not in counts
