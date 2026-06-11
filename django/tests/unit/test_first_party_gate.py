"""First-party API gate behaviour (discovery/security.py).

The gate keeps UI-only / abuse-prone endpoints reachable from the same-origin
SPA while rejecting external programmatic callers. These tests re-enable the
gate (the suite-wide autouse fixture turns it off) and assert both directions:
browser-shaped requests pass, bare API requests get 403, and the curated
public endpoints are never gated.
"""

from __future__ import annotations

import pytest

from django.test import Client


@pytest.fixture(autouse=True)
def _enable_gate(settings):
    settings.API_FIRST_PARTY_GATE_ENABLED = True
    settings.ALLOWED_HOSTS = ["testserver", "localhost"]


@pytest.fixture
def client():
    return Client()


# A gated GET that needs no seeded data (returns [] on an empty DB).
GATED_URL = "/api/discovery/filters/bgc-classes/"
# A curated, always-open endpoint.
OPEN_URL = "/api/discovery/ibgcs/ids/"


@pytest.mark.django_db
def test_bare_request_is_rejected(client):
    """No Fetch-Metadata, no Origin/Referer (curl/requests) -> 403."""
    resp = client.get(GATED_URL)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_same_origin_fetch_passes(client):
    """Browser SPA fetch() stamps Sec-Fetch-Site: same-origin -> allowed."""
    resp = client.get(GATED_URL, HTTP_SEC_FETCH_SITE="same-origin")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_cross_site_request_is_rejected(client):
    resp = client.get(GATED_URL, HTTP_SEC_FETCH_SITE="cross-site")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_trusted_referer_fallback_passes(client):
    """Older browsers without Fetch-Metadata fall back to Origin/Referer."""
    resp = client.get(GATED_URL, HTTP_REFERER="http://testserver/dashboard/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_untrusted_origin_is_rejected(client):
    resp = client.get(GATED_URL, HTTP_ORIGIN="http://evil.example.com")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_open_endpoint_is_not_gated(client):
    """Curated public endpoints stay reachable without any browser signal."""
    resp = client.get(OPEN_URL)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_gate_disabled_allows_bare_request(client, settings):
    settings.API_FIRST_PARTY_GATE_ENABLED = False
    resp = client.get(GATED_URL)
    assert resp.status_code == 200
