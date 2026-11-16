"""Root conftest: fixtures shared by the unit, integration and e2e suites."""

import pytest


@pytest.fixture(autouse=True)
def _locmem_cache(settings):
    """Use an in-memory cache for every test.

    Production uses the Postgres DatabaseCache, which needs the ``django_cache``
    table and DB access; unit tests that touch ``django.core.cache`` (asset
    uploads, report tokens, idset tokens) must not depend on either.
    """
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    from django.core.cache import cache

    cache.clear()


@pytest.fixture(autouse=True)
def _relax_api_guards(settings):
    """Turn off the first-party API gate and per-IP throttling for the suite.

    The gate (discovery/security.py) admits only same-origin browser traffic,
    and the throttles (discovery/throttling.py) cap requests per client IP —
    neither of which the Django test client emulates, and the throttle's cache
    counters would otherwise leak across tests. Existing endpoint tests hit the
    routes directly, so both guards are off by default; their behaviour is
    covered explicitly in ``tests/unit/test_first_party_gate.py`` and
    ``tests/unit/test_api_throttling.py``, which re-enable them.
    """
    settings.API_FIRST_PARTY_GATE_ENABLED = False
    settings.API_THROTTLE_ENABLED = False
