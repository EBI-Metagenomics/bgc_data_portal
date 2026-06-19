"""Integration tests for the iBGC id-set token round-trip.

A Run Query result allow-list can be thousands of ids — too many to thread
back through the roster / map / count GET endpoints as an ``ibgc_ids`` CSV
without overflowing gunicorn's request line (HTTP 414). ``POST /ibgcs/idset/``
stashes the list server-side and returns a short token the GETs accept via
``ibgc_ids_token``. These tests pin the contract:

  * the token scopes the roster / count exactly like the inline CSV;
  * a stale / unknown token is a hard 404 (so the client re-runs rather than
    silently rendering the unfiltered catalogue);
  * id order is preserved so ``sort_by=similarity`` honours the caller's rank.
"""

from __future__ import annotations

import pytest
from tests.factories.discovery_models import IntegratedBgcFactory

from django.core.cache import cache
from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def ibgcs(db):
    """Three independent iBGCs to slice an allow-list out of."""
    return [IntegratedBgcFactory() for _ in range(3)]


def _mint(client, ids: list[int]):
    return client.post(
        "/api/discovery/ibgcs/idset/",
        data={"ibgc_ids": ids},
        content_type="application/json",
        HTTP_SEC_FETCH_SITE="same-origin",
    )


def _roster_ids(client, **params) -> list[int]:
    resp = client.get(
        "/api/discovery/ibgcs/roster/",
        {"page_size": 50, **params},
        HTTP_SEC_FETCH_SITE="same-origin",
    )
    assert resp.status_code == 200, resp.content
    return [it["id"] for it in resp.json()["items"]]


@pytest.mark.django_db
def test_mint_returns_token_and_count(client, ibgcs):
    ids = [b.id for b in ibgcs[:2]]
    resp = _mint(client, ids)
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["n_ibgcs"] == 2
    assert isinstance(body["token"], str) and len(body["token"]) == 32


@pytest.mark.django_db
def test_token_scopes_roster_like_csv(client, ibgcs):
    keep = [ibgcs[0].id, ibgcs[2].id]
    token = _mint(client, keep).json()["token"]

    via_token = set(_roster_ids(client, ibgc_ids_token=token))
    via_csv = set(_roster_ids(client, ibgc_ids=",".join(map(str, keep))))

    assert via_token == set(keep)
    assert via_token == via_csv
    assert ibgcs[1].id not in via_token


@pytest.mark.django_db
def test_token_scopes_count(client, ibgcs):
    keep = [ibgcs[0].id, ibgcs[1].id]
    token = _mint(client, keep).json()["token"]
    resp = client.get(
        "/api/discovery/ibgcs/count/",
        {"ibgc_ids_token": token},
        HTTP_SEC_FETCH_SITE="same-origin",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["exact_count"] == 2


@pytest.mark.django_db
def test_token_preserves_order_for_similarity_sort(client, ibgcs):
    # Reverse-id order so a plain id sort can't accidentally match it.
    ordered = [ibgcs[2].id, ibgcs[0].id, ibgcs[1].id]
    token = _mint(client, ordered).json()["token"]
    got = _roster_ids(client, ibgc_ids_token=token, sort_by="similarity")
    assert got == ordered


@pytest.mark.django_db
def test_expired_token_is_404(client, ibgcs):
    token = _mint(client, [ibgcs[0].id]).json()["token"]
    cache.delete(f"ibgcset:{token}")
    resp = client.get(
        "/api/discovery/ibgcs/roster/",
        {"ibgc_ids_token": token},
        HTTP_SEC_FETCH_SITE="same-origin",
    )
    assert resp.status_code == 404, resp.content


@pytest.mark.django_db
def test_empty_idset_is_rejected(client, ibgcs):
    resp = _mint(client, [])
    assert resp.status_code == 400, resp.content
