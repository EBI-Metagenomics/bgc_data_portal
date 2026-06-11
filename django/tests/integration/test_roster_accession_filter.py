"""Integration tests for the unified ``accession`` filter on the iBGC roster.

The Accessions filter is a single smart field: the backend auto-detects the
accession kind (iBGC / region, source prediction, cBGC, assembly, contig,
protein) and applies the matching join. Protein / contig matches are clipped
to the iBGC's genomic span so a hit elsewhere on the shared contig does not
leak unrelated iBGCs.
"""

from __future__ import annotations

import pytest
from tests.factories.discovery_models import (
    ContigCdsFactory,
    DashboardDetectorFactory,
    IntegratedBgcFactory,
    SourceBgcPredictionFactory,
)

from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def ibgc(db):
    """A clustered iBGC spanning 1000–5000 with one in-span CDS and one
    out-of-span CDS on the same contig (for the range-clip assertion)."""
    bgc = IntegratedBgcFactory(start_pos=1000, end_pos=5000)
    detector = DashboardDetectorFactory(
        name="antiSMASH v7", tool="antiSMASH", tool_name_code="ANT"
    )
    SourceBgcPredictionFactory(
        contig=bgc.contig,
        integrated_bgc=bgc,
        detector=detector,
        is_validated=True,
        is_partial=False,
        start_pos=1000,
        end_pos=5000,
        prediction_accession=f"{bgc.cbgc.accession}.ANT.01",
    )
    # In-span protein.
    ContigCdsFactory(
        contig=bgc.contig,
        start_pos=1100,
        end_pos=1400,
        protein_id_str="MGYP000000000001",
    )
    # Same contig, outside the iBGC span — must NOT make the iBGC match a
    # protein query for its id (range clip).
    ContigCdsFactory(
        contig=bgc.contig,
        start_pos=8000,
        end_pos=8300,
        protein_id_str="MGYP000000000999",
    )
    return bgc


def _roster_ids(client, accession: str) -> set[int]:
    resp = client.get(
        "/api/discovery/ibgcs/roster/", {"accession": accession, "page_size": 50}
    )
    assert resp.status_code == 200, resp.content
    return {it["id"] for it in resp.json()["items"]}


@pytest.mark.django_db
def test_accession_matches_ibgc(client, ibgc):
    assert ibgc.id in _roster_ids(client, ibgc.accession)


@pytest.mark.django_db
def test_accession_ibgc_is_case_insensitive(client, ibgc):
    assert ibgc.id in _roster_ids(client, ibgc.accession.lower())


@pytest.mark.django_db
def test_accession_matches_cbgc_parent(client, ibgc):
    assert ibgc.id in _roster_ids(client, ibgc.cbgc.accession)


@pytest.mark.django_db
def test_accession_matches_source_prediction(client, ibgc):
    assert ibgc.id in _roster_ids(client, f"{ibgc.cbgc.accession}.ANT.01")


@pytest.mark.django_db
def test_accession_matches_assembly(client, ibgc):
    acc = ibgc.contig.assembly.assembly_accession
    assert ibgc.id in _roster_ids(client, acc)


@pytest.mark.django_db
def test_accession_matches_contig(client, ibgc):
    assert ibgc.id in _roster_ids(client, ibgc.contig.accession)


@pytest.mark.django_db
def test_accession_matches_in_span_protein(client, ibgc):
    assert ibgc.id in _roster_ids(client, "MGYP000000000001")


@pytest.mark.django_db
def test_accession_protein_is_clipped_to_ibgc_span(client, ibgc):
    # The CDS named MGYP…999 sits outside the iBGC's bgc_range, so even though
    # it shares the contig, the iBGC must not surface for that protein.
    assert ibgc.id not in _roster_ids(client, "MGYP000000000999")


@pytest.mark.django_db
def test_accession_unknown_value_matches_nothing(client, ibgc):
    assert ibgc.id not in _roster_ids(client, "MGYB-ZZZZZZ-ZZ")
