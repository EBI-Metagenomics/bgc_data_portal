"""Per-client-IP rate limiting (discovery/throttling.py).

The suite-wide autouse fixture disables throttling; these tests re-enable it,
shrink the default tier to a tiny limit, and point the throttle at a private
in-memory cache (so they never touch the shared Redis) to prove that requests
over the limit get HTTP 429 and that disabling the flag bypasses it.
"""

from __future__ import annotations

import pytest
from django.core.cache.backends.locmem import LocMemCache
from django.test import Client

from discovery import throttling

# Open (un-gated) endpoint -> exercises the router-level default throttle.
URL = "/api/discovery/ibgcs/ids/"


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def tiny_default_throttle(settings, monkeypatch):
    """Enable throttling with a 2-request limit on an isolated, empty cache."""
    settings.API_THROTTLE_ENABLED = True
    # LocMemCache shares storage by name across instances, so clear on setup.
    loc = LocMemCache("throttle-test", {})
    loc.clear()
    monkeypatch.setattr(throttling.default_throttle, "cache", loc)
    monkeypatch.setattr(throttling.default_throttle, "num_requests", 2)
    monkeypatch.setattr(throttling.default_throttle, "duration", 60)


@pytest.mark.django_db
def test_requests_within_limit_pass(client, tiny_default_throttle):
    assert client.get(URL).status_code == 200
    assert client.get(URL).status_code == 200


@pytest.mark.django_db
def test_request_over_limit_is_throttled(client, tiny_default_throttle):
    assert client.get(URL).status_code == 200
    assert client.get(URL).status_code == 200
    resp = client.get(URL)
    assert resp.status_code == 429


@pytest.mark.django_db
def test_throttle_disabled_bypasses(client, settings, monkeypatch):
    settings.API_THROTTLE_ENABLED = False
    loc = LocMemCache("throttle-test-disabled", {})
    loc.clear()
    monkeypatch.setattr(throttling.default_throttle, "cache", loc)
    monkeypatch.setattr(throttling.default_throttle, "num_requests", 1)
    monkeypatch.setattr(throttling.default_throttle, "duration", 60)
    for _ in range(5):
        assert client.get(URL).status_code == 200
