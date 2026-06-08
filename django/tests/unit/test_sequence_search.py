"""Sequence (phmmer) search: async dispatch + result mapping.

Guards the regression that made the feature return nothing for a perfect
match (e.g. searching a protein of BGC0002713):

  * the endpoint must hand off to Celery (202 + task_id) and poll, and
  * the status handler must consume the task's result **as iBGC-keyed**
    metrics — the task already collapses matched CDS to their owning iBGC
    via a contig + range-overlap join. The original bug re-collapsed those
    iBGC ids through ``SourceBgcPrediction`` (filtering the source-BGC id
    space by iBGC PKs), which dropped every hit. This is the same drift the
    chemical search hit; see ``test_chemical_search.py``.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client

from tests.factories.discovery_models import (
    ContigCdsFactory,
    IntegratedBgcFactory,
    SourceBgcPredictionFactory,
)

POST_URL = "/api/discovery/query/sequence/"
STATUS_URL = "/api/discovery/query/ibgc-sequence/status/{}/"

# A short but valid amino-acid query — content is irrelevant here because the
# phmmer call is mocked at the task boundary; we only exercise the API layer.
QUERY_SEQ = "MKNAVQIVNEALNQGITLFVADNRLQYETNRDSIP"


@pytest.fixture
def client():
    return Client()


def _post(client, sequence, **overrides):
    body = {"sequence": sequence}
    body.update(overrides)
    return client.post(
        POST_URL,
        data=json.dumps(body),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_post_dispatches_and_returns_202(client, monkeypatch):
    class _Dispatched:
        id = "task-abc"

    monkeypatch.setattr(
        "discovery.tasks.sequence_similarity_search.delay",
        lambda *a, **k: _Dispatched(),
    )

    resp = _post(client, QUERY_SEQ)

    assert resp.status_code == 202
    assert resp.json()["task_id"] == "task-abc"


@pytest.mark.django_db
def test_post_rejects_empty_sequence(client):
    assert _post(client, "   ").status_code == 400


@pytest.mark.django_db
def test_post_rejects_oversized_sequence(client):
    assert _post(client, "A" * 5001).status_code == 400


@pytest.mark.django_db
def test_post_rejects_out_of_range_threshold(client):
    assert _post(client, QUERY_SEQ, min_pident=150.0).status_code == 400


@pytest.mark.django_db
def test_status_surfaces_ibgc_keyed_hit(client, monkeypatch):
    """The task returns ``{iBGC id: {bitscore, pident, qcoverage, protein_id}}``.

    The status endpoint must surface that iBGC in the roster carrying the
    bitscore as ``similarity_score`` plus the per-hit protein metadata — the
    id space is iBGC, not source-prediction PK.

    The iBGC id is forced high (no ``SourceBgcPrediction`` shares it) so the
    old ``filter(id__in=[ibgc_id])`` re-collapse would resolve to nothing and
    return an empty roster — in production iBGC and source-prediction PKs
    never coincide. (A fresh test DB would otherwise mint both as id=1 and
    mask the bug.)
    """
    ibgc = IntegratedBgcFactory(id=900_001, start_pos=1000, end_pos=5000)
    SourceBgcPredictionFactory(
        contig=ibgc.contig,
        integrated_bgc=ibgc,
        start_pos=1000,
        end_pos=5000,
    )
    ContigCdsFactory(
        contig=ibgc.contig,
        start_pos=1100,
        end_pos=1400,
        protein_id_str="MGYP000000000001",
    )

    class _FakeResult:
        def __init__(self, task_id):
            pass

        def failed(self):
            return False

        def ready(self):
            return True

        # Celery JSON-encodes int keys as strings — mimic that.
        result = {
            str(ibgc.id): {
                "bitscore": 1234.5,
                "pident": 100.0,
                "qcoverage": 100.0,
                "protein_id": "MGYP000000000001",
            }
        }

    monkeypatch.setattr("celery.result.AsyncResult", _FakeResult)

    resp = client.get(STATUS_URL.format("task-xyz"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total_count"] == 1
    item = body["items"][0]
    assert item["id"] == ibgc.id
    assert item["similarity_score"] == pytest.approx(1234.5)
    assert item["best_hit_protein_id"] == "MGYP000000000001"
    assert item["best_pident"] == pytest.approx(100.0)
    assert item["best_qcoverage"] == pytest.approx(100.0)


@pytest.mark.django_db
def test_status_does_not_recollapse_via_source_predictions(client, monkeypatch):
    """Regression: an iBGC id that collides with an unrelated source-prediction
    PK must still resolve to *its own* iBGC, never the source prediction's
    parent.

    The original bug fed iBGC ids into ``SourceBgcPrediction.filter(id__in=…)``.
    A decoy source prediction is given a PK equal to ``target``'s iBGC id but
    pointed at ``other``, so the buggy re-collapse would surface ``other``
    instead of ``target``.
    """
    target = IntegratedBgcFactory(id=900_001, start_pos=1000, end_pos=5000)
    SourceBgcPredictionFactory(
        contig=target.contig, integrated_bgc=target, start_pos=1000, end_pos=5000
    )
    # Decoy: a source prediction whose PK collides with ``target``'s iBGC id
    # but belongs to a *different* iBGC. Under the bug, looking the iBGC id up
    # in the source-BGC table hits this row and resolves to ``other``.
    other = IntegratedBgcFactory(id=900_002, start_pos=1000, end_pos=5000)
    SourceBgcPredictionFactory(
        id=900_001,
        contig=other.contig,
        integrated_bgc=other,
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

        result = {
            str(target.id): {
                "bitscore": 500.0,
                "pident": 95.0,
                "qcoverage": 90.0,
                "protein_id": "MGYP000000000042",
            }
        }

    monkeypatch.setattr("celery.result.AsyncResult", _FakeResult)

    resp = client.get(STATUS_URL.format("task-collide"))

    assert resp.status_code == 200
    body = resp.json()
    ids = [i["id"] for i in body["items"]]
    assert ids == [target.id]


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

    monkeypatch.setattr("celery.result.AsyncResult", _FakeResult)

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

    monkeypatch.setattr("celery.result.AsyncResult", _FakeResult)

    resp = client.get(STATUS_URL.format("task-pending"))
    assert resp.status_code == 503


@pytest.mark.django_db
def test_status_failed_returns_500(client, monkeypatch):
    class _FakeResult:
        def __init__(self, task_id):
            pass

        def failed(self):
            return True

        def ready(self):
            return True

        result = RuntimeError("Protein search index not built")

    monkeypatch.setattr("celery.result.AsyncResult", _FakeResult)

    resp = client.get(STATUS_URL.format("task-failed"))
    assert resp.status_code == 500
