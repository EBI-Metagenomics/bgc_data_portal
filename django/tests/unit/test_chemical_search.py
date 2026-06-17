"""Chemical (ChemOnt/ClassyFire) search: async dispatch + result mapping.

Guards the two regressions that made the feature return nothing:
  * the endpoint must hand off to a background task (202 + task_id) and poll, and
  * the status handler must map the task's **iBGC** ids back to their source
    predictions via ``integrated_bgc_id`` — not filter SourceBgcPrediction by
    iBGC ids (the original bug).
"""

from __future__ import annotations

import json

import pytest
from tests.factories.discovery_models import (
    ContigCdsFactory,
    IntegratedBgcFactory,
    SourceBgcPredictionFactory,
)

from django.test import Client

POST_URL = "/api/discovery/query/chemical/"
STATUS_URL = "/api/discovery/query/chemical/status/{}/"


@pytest.fixture
def client():
    return Client()


def _post(client, smiles, threshold=0.5):
    return client.post(
        POST_URL,
        data=json.dumps({"smiles": smiles, "similarity_threshold": threshold}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_post_dispatches_and_returns_202(client, monkeypatch):
    class _Dispatched:
        id = "task-abc"

    monkeypatch.setattr(
        "discovery.tasks.chemical_similarity_search.enqueue",
        lambda *a, **k: _Dispatched(),
    )

    resp = _post(client, "CCO")  # ethanol — valid SMILES

    assert resp.status_code == 202
    assert resp.json()["task_id"] == "task-abc"


@pytest.mark.django_db
def test_post_rejects_invalid_smiles(client):
    assert _post(client, "not-a-molecule!!!").status_code == 400


@pytest.mark.django_db
def test_post_rejects_empty_smiles(client):
    assert _post(client, "   ").status_code == 400


@pytest.mark.django_db
def test_status_returns_scored_ibgcs(client, monkeypatch):
    """The task returns {iBGC id: score}; the status endpoint must surface that
    iBGC in the roster carrying its score (id-space = iBGC, not source PK)."""
    ibgc = IntegratedBgcFactory(start_pos=1000, end_pos=5000)
    SourceBgcPredictionFactory(
        contig=ibgc.contig,
        integrated_bgc=ibgc,
        start_pos=1000,
        end_pos=5000,
    )

    class _FakeResult:
        def __init__(self, task_id):
            pass

        def failed(self):
            return False

        def ready(self):
            return True

        # Celery JSON-encodes int keys as strings — mimic that.
        result = {str(ibgc.id): 0.77}

    monkeypatch.setattr("discovery.cache_utils.fetch_job", lambda tid: _FakeResult(tid))

    resp = client.get(STATUS_URL.format("task-xyz"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total_count"] == 1
    item = body["items"][0]
    assert item["id"] == ibgc.id
    assert item["similarity_score"] == pytest.approx(0.77)


@pytest.mark.django_db
def test_status_empty_result_is_empty_roster(client, monkeypatch):
    class _FakeResult:
        def __init__(self, task_id):
            pass

        def failed(self):
            return False

        def ready(self):
            return True

        result = {}

    monkeypatch.setattr("discovery.cache_utils.fetch_job", lambda tid: _FakeResult(tid))

    resp = client.get(STATUS_URL.format("task-none"))

    assert resp.status_code == 200
    assert resp.json()["pagination"]["total_count"] == 0


@pytest.mark.django_db
def test_status_pending_returns_503(client, monkeypatch):
    class _FakeResult:
        def __init__(self, task_id):
            pass

        def failed(self):
            return False

        def ready(self):
            return False

    monkeypatch.setattr("discovery.cache_utils.fetch_job", lambda tid: _FakeResult(tid))

    resp = client.get(STATUS_URL.format("task-pending"))
    assert resp.status_code == 503


# ── task scoring (classify → IC → range-overlap → Lin BMA → threshold) ───────


class _FakeOntology:
    def get_ancestor_ids(self, tid):
        return {tid}


@pytest.mark.django_db
def test_task_scores_overlapping_ibgc_above_threshold(monkeypatch):
    """A query sharing an iBGC's ChemOnt term scores 1.0 (identical) and is
    returned keyed by the iBGC id."""
    from common_core.chemont.classyfire_client import ClassyFireResult
    from discovery.models import CdsChemOnt, PrecomputedStats
    from discovery.tasks import chemical_similarity_search

    term = "CHEMONTID:0001"
    ibgc = IntegratedBgcFactory(start_pos=1000, end_pos=5000)
    cds = ContigCdsFactory(contig=ibgc.contig, start_pos=1100, end_pos=1400)
    CdsChemOnt.objects.create(
        cds=cds,
        chemont_id=term,
        chemont_name="Terpenes",
        probability=0.9,
        weight=0.5,
    )
    PrecomputedStats.objects.update_or_create(
        key="chemont_ic", defaults={"data": {term: 2.0}}
    )

    monkeypatch.setattr(
        "common_core.chemont.ontology.get_ontology", lambda: _FakeOntology()
    )
    monkeypatch.setattr(
        "common_core.chemont.classyfire_client.classify",
        lambda *a, **k: ClassyFireResult(inchikey="x", chemont_ids=[term]),
    )
    # Force a cache miss so the (patched) classifier is used.
    monkeypatch.setattr("django.core.cache.cache.get", lambda *a, **k: None)
    monkeypatch.setattr("django.core.cache.cache.set", lambda *a, **k: None)

    result = chemical_similarity_search.call("CCO", 0.5)

    assert result == {ibgc.id: 1.0}


@pytest.mark.django_db
def test_task_raises_when_ic_cache_missing(monkeypatch):
    """No precomputed IC must fail loudly, not silently return empty."""
    from common_core.chemont.classyfire_client import ClassyFireResult
    from discovery.models import PrecomputedStats
    from discovery.tasks import chemical_similarity_search

    PrecomputedStats.objects.filter(key="chemont_ic").delete()
    monkeypatch.setattr(
        "common_core.chemont.ontology.get_ontology", lambda: _FakeOntology()
    )
    monkeypatch.setattr(
        "common_core.chemont.classyfire_client.classify",
        lambda *a, **k: ClassyFireResult(inchikey="x", chemont_ids=["CHEMONTID:0001"]),
    )
    monkeypatch.setattr("django.core.cache.cache.get", lambda *a, **k: None)
    monkeypatch.setattr("django.core.cache.cache.set", lambda *a, **k: None)

    # Running synchronously surfaces the failure by raising (no result store).
    with pytest.raises(RuntimeError):
        chemical_similarity_search.call("CCO", 0.5)
