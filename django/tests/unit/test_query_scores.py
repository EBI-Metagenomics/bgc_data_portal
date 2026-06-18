"""Compact, capped "scores" payloads for the four query types.

The dashboard polls these instead of the paginated roster so it can build a
result allow-list of up to ``DASHBOARD_RESULT_CAP`` iBGCs (ranked best-first)
plus the per-hit metric maps in a single lightweight response — the fix for
the bug where the default 25-row page left the roster stuck on one page and
buried exact matches. Each endpoint reuses ``_query_scores_payload``; these
tests pin the cap/total/ranking contract and the sequence metric passthrough.
"""

from __future__ import annotations

import json

import pytest

from discovery import api as discovery_api

from django.test import Client

SEQ_URL = "/api/discovery/query/ibgc-sequence/status/{}/scores/"
CHEM_URL = "/api/discovery/query/chemical/status/{}/scores/"
DOMAIN_URL = "/api/discovery/query/ibgc-domain/scores/"
ARCH_URL = "/api/discovery/query/ibgc-architecture/scores/"


@pytest.fixture
def client():
    return Client()


def _fake_async_result(result_dict):
    class _R:
        def __init__(self, task_id):
            pass

        def failed(self):
            return False

        def ready(self):
            return True

        result = result_dict

    return _R


# ── _query_scores_payload (pure) ─────────────────────────────────────────────


def test_payload_caps_total_and_preserves_order():
    # ranked_ids is already best-first; the helper must slice, not re-sort.
    resp = discovery_api._query_scores_payload(
        [3, 1, 2],
        similarity_lookup={3: 30.0, 1: 10.0, 2: 20.0},
        max_results=2,
    )
    assert resp.total_matched == 3
    assert resp.capped is True
    assert resp.cap == 2
    assert [r.id for r in resp.items] == [3, 1]


def test_payload_not_capped_when_under_limit():
    resp = discovery_api._query_scores_payload(
        [1, 2], similarity_lookup={1: 1.0, 2: 2.0}, max_results=10
    )
    assert resp.total_matched == 2
    assert resp.capped is False


def test_payload_max_results_bounded_by_dashboard_cap():
    ranked = list(range(10))
    resp = discovery_api._query_scores_payload(
        ranked,
        similarity_lookup={i: float(i) for i in ranked},
        max_results=10_000_000,
    )
    assert resp.cap == discovery_api.DASHBOARD_RESULT_CAP


# ── Sequence scores endpoint ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_sequence_scores_ranks_by_bitscore_and_caps(client, monkeypatch):
    result = {
        # Celery JSON-encodes int iBGC keys as strings.
        "11": {"bitscore": 100.0, "pident": 90.0, "qcoverage": 80.0, "protein_id": "p1"},
        "22": {"bitscore": 300.0, "pident": 100.0, "qcoverage": 100.0, "protein_id": "p2"},
        "33": {"bitscore": 200.0, "pident": 95.0, "qcoverage": 99.0, "protein_id": "p3"},
    }
    monkeypatch.setattr("discovery.cache_utils.fetch_job", _fake_async_result(result))

    resp = client.get(SEQ_URL.format("t") + "?max_results=2")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_matched"] == 3
    assert body["capped"] is True
    assert [i["id"] for i in body["items"]] == [22, 33]  # bitscore desc
    top = body["items"][0]
    assert top["similarity_score"] == pytest.approx(300.0)
    assert top["best_pident"] == pytest.approx(100.0)
    assert top["best_qcoverage"] == pytest.approx(100.0)
    assert top["best_hit_protein_id"] == "p2"


@pytest.mark.django_db
def test_sequence_scores_empty_result(client, monkeypatch):
    monkeypatch.setattr("discovery.cache_utils.fetch_job", _fake_async_result({}))
    resp = client.get(SEQ_URL.format("t"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_matched"] == 0
    assert body["capped"] is False
    assert body["items"] == []


@pytest.mark.django_db
def test_sequence_scores_pending_returns_503(client, monkeypatch):
    class _Pending:
        def __init__(self, task_id):
            pass

        def failed(self):
            return False

        def ready(self):
            return False

    monkeypatch.setattr("discovery.cache_utils.fetch_job", _Pending)
    assert client.get(SEQ_URL.format("t")).status_code == 503


# ── Chemical scores endpoint ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_chemical_scores_ranks_and_caps(client, monkeypatch):
    result = {"5": 0.2, "6": 0.9, "7": 0.5}
    monkeypatch.setattr("discovery.cache_utils.fetch_job", _fake_async_result(result))

    resp = client.get(CHEM_URL.format("t") + "?max_results=2")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_matched"] == 3
    assert body["capped"] is True
    assert [i["id"] for i in body["items"]] == [6, 7]  # similarity desc
    assert body["items"][0]["similarity_score"] == pytest.approx(0.9)


# ── Domain scores endpoint ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_domain_scores_binary_score_and_cap(client, monkeypatch):
    # Binary match → every hit scores 1.0. Mock the id resolver so the test
    # doesn't need ContigDomain fixtures.
    monkeypatch.setattr(
        "discovery.api._resolve_domain_ibgc_ids", lambda body: [10, 20, 30, 40]
    )
    body = {"domains_text": "PF00001", "logic": "and"}
    resp = client.post(
        DOMAIN_URL + "?max_results=3",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total_matched"] == 4
    assert payload["capped"] is True
    assert len(payload["items"]) == 3
    assert all(i["similarity_score"] == pytest.approx(1.0) for i in payload["items"])


# ── Architecture scores endpoint ─────────────────────────────────────────────


@pytest.mark.django_db
def test_architecture_scores_preserves_rank_and_caps(client, monkeypatch):
    # _architecture_top returns (ids, scores) already best-first.
    monkeypatch.setattr(
        "discovery.api._architecture_top",
        lambda body: ([7, 8, 9], [0.9, 0.6, 0.3]),
    )
    body = {"architecture": ["PF00001", "PF00002"], "weight": 0.5}
    resp = client.post(
        ARCH_URL + "?max_results=2",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total_matched"] == 3
    assert payload["capped"] is True
    assert [i["id"] for i in payload["items"]] == [7, 8]
    assert payload["items"][0]["similarity_score"] == pytest.approx(0.9)
