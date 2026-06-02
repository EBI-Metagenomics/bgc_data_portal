"""API-level integration tests for the iBGC discovery endpoints.

Hits the real ``/api/discovery/*`` routes through the Django test client
against a factory-seeded DB. This is the layer that was missing: the Phase 2f
rename left stale field references in api.py (``bgcs`` vs ``source_bgcs``,
``cds__bgc`` on the now-contig-anchored CDS, ``ibgc_architecture([list])``,
dropped ``representative_bgc_id``), and nothing exercised these endpoints with
data — the schema-less dev DB had masked every one.

Covers the endpoints the v2 dashboard loads on the golden path:
roster, detail, region, and the detector / chemont-class filter dropdowns.
"""

from __future__ import annotations

import re

import pytest
from django.test import Client

from discovery.models import CdsChemOnt
from tests.factories.discovery_models import (
    ContigCdsFactory,
    ContigDomainFactory,
    DashboardDetectorFactory,
    IntegratedBgcFactory,
    SourceBgcPredictionFactory,
)

_C = "[0-9ABCDEFGHJKMNPQRSTVWXYZ]"
IBGC_RE = re.compile(rf"^MGYB-{_C}{{6}}-{_C}{{2}}$")
CBGC_RE = re.compile(rf"^MGYB-{_C}{{6}}$")


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def seeded_ibgc(db):
    """A clustered iBGC: validated antiSMASH source prediction, an overlapping
    CDS with a PFAM domain + a ChemOnt class — enough to drive every endpoint
    under test through its real (range-overlap) query paths."""
    ibgc = IntegratedBgcFactory(start_pos=1000, end_pos=5000)
    ibgc.gene_cluster_family = "cluster.0001.0000.0000"
    ibgc.save(update_fields=["gene_cluster_family"])

    detector = DashboardDetectorFactory(
        name="antiSMASH v7", tool="antiSMASH", tool_name_code="ANT"
    )
    SourceBgcPredictionFactory(
        contig=ibgc.contig,
        integrated_bgc=ibgc,
        detector=detector,
        is_validated=True,
        is_partial=False,
        start_pos=1000,
        end_pos=5000,
    )
    cds = ContigCdsFactory(contig=ibgc.contig, start_pos=1100, end_pos=1400)
    ContigDomainFactory(cds=cds, ref_db="PFAM", domain_acc="PF00001")
    CdsChemOnt.objects.create(
        cds=cds,
        chemont_id="CHEMONTID:0001",
        chemont_name="Terpenes",
        probability=0.9,
        weight=0.5,
    )
    return ibgc


@pytest.mark.django_db
def test_roster_emits_stable_accessions(client, seeded_ibgc):
    resp = client.get("/api/discovery/ibgcs/roster/", {"page": 1, "page_size": 50})
    assert resp.status_code == 200, resp.content
    items = resp.json()["items"]
    row = next((it for it in items if it["id"] == seeded_ibgc.id), None)
    assert row is not None, "seeded iBGC missing from roster"
    # The regression: these used to be "" / None because the serializer never
    # set them.
    assert IBGC_RE.match(row["accession"]), row["accession"]
    assert CBGC_RE.match(row["cbgc_accession"]), row["cbgc_accession"]
    assert row["accession"] == seeded_ibgc.accession


@pytest.mark.django_db
def test_detail_returns_200_with_accessions_and_architecture(client, seeded_ibgc):
    # Previously 500: ibgc_architecture([member ids]) passed a list where a
    # single id was expected, and the response carried a dropped field.
    resp = client.get(f"/api/discovery/ibgcs/{seeded_ibgc.id}/")
    assert resp.status_code == 200, resp.content
    d = resp.json()
    assert d["accession"] == seeded_ibgc.accession
    assert CBGC_RE.match(d["cbgc_accession"]), d["cbgc_accession"]
    assert d["region_endpoint_url"] == f"/api/discovery/ibgcs/{seeded_ibgc.id}/region/"
    assert "representative_bgc_id" not in d
    # Range-overlap domain architecture picked up the PFAM domain.
    accs = {item["domain_acc"] for item in d["domain_architecture"]}
    assert "PF00001" in accs
    assert len(d["member_bgcs"]) == 1


@pytest.mark.django_db
def test_region_endpoint_attributes_tools_per_cds(client, seeded_ibgc):
    resp = client.get(f"/api/discovery/ibgcs/{seeded_ibgc.id}/region/")
    assert resp.status_code == 200, resp.content
    d = resp.json()
    assert d["ibgc_accession"] == seeded_ibgc.accession
    assert CBGC_RE.match(d["cbgc_accession"])
    assert len(d["cds_list"]) >= 1
    # The overlapping CDS is claimed by the antiSMASH source prediction.
    assert any("antiSMASH" in cds["claimed_by_tools"] for cds in d["cds_list"])


@pytest.mark.django_db
def test_filter_detectors_endpoint(client, seeded_ibgc):
    # Previously 500: Count("bgcs") — the reverse relation is source_bgcs.
    resp = client.get("/api/discovery/filters/detectors/", {"page": 1, "page_size": 20})
    assert resp.status_code == 200, resp.content
    tools = {it["tool"]: it["count"] for it in resp.json()["items"]}
    assert tools.get("antiSMASH", 0) >= 1


@pytest.mark.django_db
def test_filter_chemont_classes_endpoint(client, seeded_ibgc):
    # Previously 500: Count("cds__bgc") — CDS are contig-anchored in v2.
    resp = client.get("/api/discovery/filters/chemont-classes/")
    assert resp.status_code == 200, resp.content
    ids = {node["chemont_id"] for node in resp.json()}
    assert "CHEMONTID:0001" in ids


@pytest.fixture
def polyketide_ibgc(db):
    """An iBGC whose contig carries a domain annotated as a polyketide
    synthase — the data target for the landing-page free-text keyword
    fallback (``domain_text``)."""
    ibgc = IntegratedBgcFactory(start_pos=1000, end_pos=5000)
    cds = ContigCdsFactory(contig=ibgc.contig, start_pos=1100, end_pos=1400)
    ContigDomainFactory(
        cds=cds,
        domain_acc="PF00109",
        domain_name="ketoacyl-synt",
        domain_description="Beta-ketoacyl synthase, polyketide synthase domain",
    )
    return ibgc


@pytest.mark.django_db
def test_roster_domain_text_matches_domain_annotations(client, polyketide_ibgc):
    # Free-text keyword like "Polyketide" must match via the iBGC's domain
    # annotations (name / description / InterPro), not just organism name.
    resp = client.get(
        "/api/discovery/ibgcs/roster/",
        {"page": 1, "page_size": 50, "domain_text": "polyketide"},
    )
    assert resp.status_code == 200, resp.content
    ids = {it["id"] for it in resp.json()["items"]}
    assert polyketide_ibgc.id in ids


@pytest.mark.django_db
def test_roster_domain_text_excludes_non_matching(client, polyketide_ibgc):
    resp = client.get(
        "/api/discovery/ibgcs/roster/",
        {"page": 1, "page_size": 50, "domain_text": "nonexistent-term-xyz"},
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["items"] == []
