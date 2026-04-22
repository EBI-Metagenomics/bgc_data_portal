"""Unit tests for discovery.services.uploaded_assessment.

Focuses on the enrichment contract of ``compute_uploaded_assembly_assessment``:
each item in ``bgc_novelty_breakdown`` must carry the fields the frontend
BGC Roster panel renders — ``size_kb``, ``nearest_validated_accession``,
``nearest_validated_distance`` — because uploaded BGCs are ephemeral and
cannot be fetched back via the ``/bgcs/roster/`` endpoint.

Heavy database / pgvector calls are patched so the test does not need a
seeded DB or the pgvector extension.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


def _uploaded_data() -> dict:
    """Minimal in-memory payload shaped like upload_parser.parse_assembly_upload."""
    return {
        "accession": "GCA_TEST_0001",
        "organism_name": "Example sp.",
        "assembly_size_mb": 4.2,
        "is_type_strain": False,
        "bgcs": [
            {
                "index": 0,
                "contig_sha256": "a" * 64,
                "detector_name": "sanntis",
                "start_position": 100,
                "end_position": 2000,
                "classification_path": "Polyketide",
                "gene_cluster_family": "",
                "size_kb": 1.9,
                "is_partial": False,
                "domains": [{"domain_acc": "PF00001"}],
                "embedding": [0.0] * 960,
            },
            {
                "index": 1,
                "contig_sha256": "b" * 64,
                "detector_name": "sanntis",
                "start_position": 500,
                "end_position": 4500,
                "classification_path": "NRP",
                "gene_cluster_family": "",
                # size_kb omitted — enrichment must fall back to (end-start)/1000
                "is_partial": False,
                "domains": [{"domain_acc": "PF00002"}],
                "embedding": [0.0] * 960,
            },
        ],
        "contigs": [],
    }


@pytest.mark.django_db
def test_assembly_assessment_enriches_bgc_novelty_breakdown():
    """Every ``bgc_novelty_breakdown`` entry carries roster-rendering fields."""
    from discovery.services import uploaded_assessment as ua

    fake_nearest = [(111, 0.37)]  # (bgc_id, distance)

    with patch.object(
        ua, "_nearest_db_embeddings", return_value=fake_nearest
    ), patch.object(
        ua, "_find_nearest_gcf_for_vector", return_value=(None, None)
    ), patch.object(
        ua, "_compute_domain_novelty", return_value=0.25
    ), patch.object(
        ua, "_compute_umap_coords_single", return_value=(0.0, 0.0)
    ), patch.object(
        ua.DashboardBgc.objects, "filter"
    ) as bgc_filter, patch.object(
        ua.DashboardAssembly.objects, "count", return_value=1
    ), patch.object(
        ua.DashboardAssembly.objects, "filter"
    ) as asm_filter, patch.object(
        ua.PrecomputedStats.objects, "get",
        side_effect=ua.PrecomputedStats.DoesNotExist,
    ):
        # DashboardBgc.objects.filter(pk=…).values_list("bgc_accession", flat=True).first()
        # → return a fixed accession string so enrichment has a known value.
        bgc_filter.return_value.values_list.return_value.first.return_value = (
            "MIBIG_REF_42"
        )
        # exclude(classification_path="").values_list("classification_path", flat=True)
        bgc_filter.return_value.exclude.return_value.values_list.return_value = [
            "Polyketide.something",
            "NRP.other",
        ]
        # filter(is_validated=True).values(…) → validated_reference_points
        bgc_filter.return_value.values.return_value = []
        # filter(gene_cluster_family=…, assembly__is_type_strain=True).exists()
        bgc_filter.return_value.exists.return_value = False

        # DashboardAssembly.objects.filter(**kw).count() chain (used for
        # percentile ranks + db_rank + type_strain counts). Return 0 for all.
        asm_filter.return_value.count.return_value = 0
        asm_filter.return_value.values_list.return_value = []
        asm_filter.return_value.aggregate.return_value = {"db_mean": 0.0}

        result = ua.compute_uploaded_assembly_assessment(_uploaded_data())

    breakdown = result["bgc_novelty_breakdown"]
    assert len(breakdown) == 2

    for item in breakdown:
        assert "size_kb" in item
        assert "nearest_validated_accession" in item
        assert "nearest_validated_distance" in item
        assert item["nearest_validated_accession"] == "MIBIG_REF_42"
        assert item["nearest_validated_distance"] == pytest.approx(0.37)

    # size_kb carried through from the parsed row
    size_by_accession = {b["accession"]: b["size_kb"] for b in breakdown}
    assert size_by_accession["uploaded_bgc_0"] == pytest.approx(1.9)
    # size_kb falls back to (end_position - start_position) / 1000 when
    # the parsed row didn't supply it (second BGC: 4500 - 500 = 4000 bp).
    assert size_by_accession["uploaded_bgc_1"] == pytest.approx(4.0)


@pytest.mark.django_db
def test_assembly_assessment_handles_no_nearest_validated():
    """When the DB has no validated BGCs, enrichment fields are None / 0."""
    from discovery.services import uploaded_assessment as ua

    with patch.object(
        ua, "_nearest_db_embeddings", return_value=[]
    ), patch.object(
        ua, "_find_nearest_gcf_for_vector", return_value=(None, None)
    ), patch.object(
        ua, "_compute_domain_novelty", return_value=0.0
    ), patch.object(
        ua, "_compute_umap_coords_single", return_value=(0.0, 0.0)
    ), patch.object(
        ua.DashboardBgc.objects, "filter"
    ) as bgc_filter, patch.object(
        ua.DashboardAssembly.objects, "count", return_value=1
    ), patch.object(
        ua.DashboardAssembly.objects, "filter"
    ) as asm_filter, patch.object(
        ua.PrecomputedStats.objects, "get",
        side_effect=ua.PrecomputedStats.DoesNotExist,
    ):
        bgc_filter.return_value.values_list.return_value.first.return_value = None
        bgc_filter.return_value.exclude.return_value.values_list.return_value = []
        bgc_filter.return_value.values.return_value = []
        bgc_filter.return_value.exists.return_value = False
        asm_filter.return_value.count.return_value = 0
        asm_filter.return_value.values_list.return_value = []
        asm_filter.return_value.aggregate.return_value = {"db_mean": 0.0}

        data = _uploaded_data()
        data["bgcs"] = data["bgcs"][:1]
        result = ua.compute_uploaded_assembly_assessment(data)

    item = result["bgc_novelty_breakdown"][0]
    assert item["nearest_validated_accession"] is None
    assert item["nearest_validated_distance"] is None
    assert item["size_kb"] == pytest.approx(1.9)
