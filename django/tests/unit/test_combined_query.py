"""Combined multi-criterion query — orchestration + endpoints.

One query carries several scoring criteria (e.g. domain-AND + domain-ARCH +
sequence); the engine AND-intersects their iBGC id sets, narrows by the standard
filters, and surfaces one sortable column per criterion (keyed by the criterion's
stable per-instance id) in the roster and the Variables map.

These tests pin: the intersection + per-criterion score payloads, distinct
columns/labels for two criteria of the same type, the primary-criterion cap
ordering, synchronous request validation, and the status/scores poll contract.
The heavy resolvers (phmmer / scoring cache) are stubbed — they have their own
tests — so these stay DB-light and deterministic.
"""

from __future__ import annotations

import json

import pytest

from discovery.services import query as q
from discovery.services.query import combined as combined_mod
from tests.factories.discovery_models import IntegratedBgcFactory

from django.test import Client


@pytest.fixture
def client():
    return Client()


def _result(scores, ctype="domain", metrics=None):
    return q.CriterionResult(
        scores=scores,
        metrics=metrics or q.CRITERION_METRICS[ctype],
        total_matched=len(scores),
    )


def _stub_resolvers(monkeypatch, results):
    """Patch ``resolve_criterion`` to return ``results`` in criteria order."""
    it = iter(results)
    monkeypatch.setattr(combined_mod, "resolve_criterion", lambda ctype, params: next(it))


# ── run_combined_query (orchestration) ───────────────────────────────────────


def test_intersection_and_per_criterion_scores(monkeypatch):
    _stub_resolvers(
        monkeypatch,
        [
            _result({1: {"value": 0.9}, 2: {"value": 0.3}, 3: {"value": 0.6}}),
            _result({2: {"value": 1.0}, 3: {"value": 1.0}, 9: {"value": 1.0}}),
        ],
    )
    out = q.run_combined_query(
        [
            {"id": "d1", "type": "domain", "params": {"domains_text": "PF1"}},
            {"id": "d2", "type": "domain", "params": {"domains_text": "PF2"}},
        ],
        {},
    )
    # Intersection of {1,2,3} and {2,3,9} = {2,3}.
    assert set(out["ordered_ids"]) == {2, 3}
    assert out["total_matched"] == 2
    assert out["capped"] is False
    # Every surviving id carries a score for BOTH criteria.
    assert out["scores_by_id"]["2"] == {"d1": {"value": 0.3}, "d2": {"value": 1.0}}
    assert out["scores_by_id"]["3"] == {"d1": {"value": 0.6}, "d2": {"value": 1.0}}
    # Ordered by the primary (first) criterion's value, best-first.
    assert out["ordered_ids"] == [3, 2]


def test_two_same_type_criteria_get_distinct_labelled_columns(monkeypatch):
    _stub_resolvers(
        monkeypatch,
        [_result({1: {"value": 1.0}}), _result({1: {"value": 1.0}})],
    )
    out = q.run_combined_query(
        [
            {"id": "a", "type": "domain", "params": {"logic": "and", "threshold": 0.5}},
            {"id": "b", "type": "domain", "params": {"logic": "or"}},
        ],
        {},
    )
    cols = {c["id"]: c for c in out["criteria"]}
    assert set(cols) == {"a", "b"}
    # Same-type criteria share a base label; the #n suffix disambiguates them.
    assert cols["a"]["label"] == "Domain sim. #1"
    assert cols["b"]["label"] == "Domain sim. #2"


def test_cap_keeps_top_by_primary_criterion(monkeypatch):
    _stub_resolvers(
        monkeypatch,
        [_result({1: {"value": 0.9}, 2: {"value": 0.3}, 3: {"value": 0.6}})],
    )
    out = q.run_combined_query(
        [{"id": "d1", "type": "domain", "params": {"domains_text": "PF1"}}],
        {},
        cap=2,
    )
    assert out["total_matched"] == 3
    assert out["capped"] is True
    assert out["ordered_ids"] == [1, 3]  # top-2 by value, best-first


def test_sequence_criterion_carries_submetric_columns(monkeypatch):
    _stub_resolvers(
        monkeypatch,
        [
            _result(
                {
                    5: {
                        "value": 300.0,
                        "pident": 99.0,
                        "qcoverage": 95.0,
                        "best_hit_protein_id": "p5",
                    }
                },
                ctype="sequence",
            )
        ],
    )
    out = q.run_combined_query(
        [{"id": "s1", "type": "sequence", "params": {"sequence": "MKT"}}], {}
    )
    metric_keys = [m["key"] for m in out["criteria"][0]["metrics"]]
    assert metric_keys == ["value", "pident", "qcoverage"]
    assert out["scores_by_id"]["5"]["s1"]["pident"] == 99.0


def test_filters_narrow_the_intersection(monkeypatch):
    _stub_resolvers(
        monkeypatch, [_result({1: {"value": 1.0}, 2: {"value": 1.0}})]
    )
    # Drop id 2 at the filter stage.
    monkeypatch.setattr(
        combined_mod, "_filter_candidate_ids", lambda ids, filters: {1}
    )
    out = q.run_combined_query(
        [{"id": "d1", "type": "domain", "params": {"domains_text": "PF1"}}],
        {"validated_only": True},
    )
    assert out["ordered_ids"] == [1]
    assert out["total_matched"] == 1


def test_unknown_criterion_type_raises(monkeypatch):
    with pytest.raises(q.CriterionError):
        q.run_combined_query([{"id": "x", "type": "bogus", "params": {}}], {})


# ── POST /query/combined/ (synchronous validation + dispatch) ─────────────────

POST_URL = "/api/discovery/query/combined/"


class _FakeTask:
    """Stand-in for the django-tasks ``combined_query`` task (avoids patching the
    real Task descriptor, which doesn't support attribute monkeypatching)."""

    def __init__(self):
        self.calls = []

    def enqueue(self, criteria, filters):
        self.calls.append((criteria, filters))
        return type("_R", (), {"id": "task-xyz"})()


def _post(client, body):
    return client.post(
        POST_URL, data=json.dumps(body), content_type="application/json"
    )


@pytest.mark.django_db
def test_post_rejects_empty_criteria(client):
    assert _post(client, {"criteria": []}).status_code == 400


@pytest.mark.django_db
def test_post_rejects_duplicate_ids(client):
    body = {
        "criteria": [
            {"id": "x", "type": "domain", "params": {"domains_text": "PF1"}},
            {"id": "x", "type": "domain", "params": {"domains_text": "PF2"}},
        ]
    }
    assert _post(client, body).status_code == 400


@pytest.mark.django_db
def test_post_rejects_unknown_type(client):
    body = {"criteria": [{"id": "x", "type": "bogus", "params": {}}]}
    assert _post(client, body).status_code == 400


@pytest.mark.django_db
def test_post_rejects_domain_without_text(client):
    body = {"criteria": [{"id": "x", "type": "domain", "params": {"domains_text": ""}}]}
    assert _post(client, body).status_code == 400


@pytest.mark.django_db
def test_post_dispatches_and_cleans_sequence(client, monkeypatch):
    fake = _FakeTask()
    monkeypatch.setattr("discovery.tasks.combined_query", fake)
    body = {
        "criteria": [
            {
                "id": "s1",
                "type": "sequence",
                "params": {"sequence": ">hdr\nMKT\nVLA\n"},
            }
        ],
        "filters": {"validated_only": True},
    }
    resp = _post(client, body)
    assert resp.status_code == 202
    assert resp.json()["task_id"] == "task-xyz"
    # FASTA header stripped + lines joined before enqueue.
    criteria, filters = fake.calls[0]
    assert criteria[0]["params"]["sequence"] == "MKTVLA"
    assert filters["validated_only"] is True


# ── GET status / scores (poll contract) ──────────────────────────────────────


def _ready(result_dict):
    class _R:
        def __init__(self, task_id):
            pass

        def failed(self):
            return False

        def ready(self):
            return True

        result = result_dict

    return _R


def _cached_result(ids):
    """Build a cached combined result over real iBGC ``ids`` (two criteria)."""
    return {
        "criteria": [
            {
                "id": "d1",
                "type": "domain",
                "label": "Domain (AND 1)",
                "metrics": [{"key": "value", "label": "Match frac.", "sortable": True}],
            },
            {
                "id": "s1",
                "type": "sequence",
                "label": "Sequence",
                "metrics": [
                    {"key": "value", "label": "Bitscore", "sortable": True},
                    {"key": "pident", "label": "Identity %", "sortable": True},
                    {"key": "qcoverage", "label": "Query cov. %", "sortable": True},
                ],
            },
        ],
        "scores_by_id": {
            str(ids[0]): {
                "d1": {"value": 0.5},
                "s1": {"value": 100.0, "pident": 80.0, "qcoverage": 70.0},
            },
            str(ids[1]): {
                "d1": {"value": 1.0},
                "s1": {"value": 300.0, "pident": 99.0, "qcoverage": 95.0},
            },
        },
        "ordered_ids": [ids[1], ids[0]],  # primary (d1) best-first
        "total_matched": 2,
        "capped": False,
        "cap": 5000,
        "warnings": [],
    }


@pytest.mark.django_db
def test_status_returns_roster_with_per_criterion_scores(client, monkeypatch):
    a = IntegratedBgcFactory(start_pos=1100, end_pos=4000)
    b = IntegratedBgcFactory(start_pos=1100, end_pos=4000)
    ids = [a.id, b.id]
    monkeypatch.setattr("discovery.cache_utils.fetch_job", _ready(_cached_result(ids)))

    resp = client.get(f"/api/discovery/query/combined/status/task/")
    assert resp.status_code == 200
    body = resp.json()
    # Column descriptors propagate.
    assert [c["id"] for c in body["criteria"]] == ["d1", "s1"]
    # Default sort = primary criterion (d1) desc → b (1.0) before a (0.5).
    assert [it["id"] for it in body["items"]] == [b.id, a.id]
    top = body["items"][0]
    assert top["scores"]["d1"]["value"] == pytest.approx(1.0)
    assert top["scores"]["s1"]["pident"] == pytest.approx(99.0)


@pytest.mark.django_db
def test_status_sorts_by_criterion_submetric(client, monkeypatch):
    a = IntegratedBgcFactory(start_pos=1100, end_pos=4000)
    b = IntegratedBgcFactory(start_pos=1100, end_pos=4000)
    ids = [a.id, b.id]
    monkeypatch.setattr("discovery.cache_utils.fetch_job", _ready(_cached_result(ids)))

    # Sort ascending by the sequence criterion's pident → a (80) before b (99).
    resp = client.get(
        "/api/discovery/query/combined/status/task/?sort_by=score:s1:pident&order=asc"
    )
    assert resp.status_code == 200
    assert [it["id"] for it in resp.json()["items"]] == [a.id, b.id]


@pytest.mark.django_db
def test_status_pending_returns_503(client, monkeypatch):
    class _Pending:
        def __init__(self, task_id):
            pass

        def failed(self):
            return False

        def ready(self):
            return False

    monkeypatch.setattr("discovery.cache_utils.fetch_job", _Pending)
    assert client.get("/api/discovery/query/combined/status/t/").status_code == 503


@pytest.mark.django_db
def test_scores_endpoint_returns_token_and_scores(client, monkeypatch):
    a = IntegratedBgcFactory(start_pos=1100, end_pos=4000)
    b = IntegratedBgcFactory(start_pos=1100, end_pos=4000)
    ids = [a.id, b.id]
    monkeypatch.setattr("discovery.cache_utils.fetch_job", _ready(_cached_result(ids)))

    resp = client.get("/api/discovery/query/combined/status/task/scores/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_matched"] == 2
    assert body["capped"] is False
    assert isinstance(body["ibgc_ids_token"], str) and body["ibgc_ids_token"]
    assert {row["id"] for row in body["items"]} == {a.id, b.id}
    assert [c["id"] for c in body["criteria"]] == ["d1", "s1"]
