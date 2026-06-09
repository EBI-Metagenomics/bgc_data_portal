"""Root conftest — shared fixtures across unit/, integration/, and e2e/ tests.

The legacy mgnify_bgcs fixtures (BgcFactory, ContigFactory, etc.) were
retired with the legacy app. v2 fixtures live next to the suites that
need them; importing here would couple unrelated tests.
"""

import pytest


@pytest.fixture(autouse=True)
def _relax_api_guards(settings):
    """Turn off the first-party API gate and per-IP throttling for the suite.

    The gate (discovery/security.py) admits only same-origin browser traffic,
    and the throttles (discovery/throttling.py) cap requests per client IP —
    neither of which the Django test client emulates, and the throttle's Redis
    counters would otherwise leak across tests. Existing endpoint tests hit the
    routes directly, so both guards are off by default; their behaviour is
    covered explicitly in ``tests/unit/test_first_party_gate.py`` and
    ``tests/unit/test_api_throttling.py``, which re-enable them.
    """
    settings.API_FIRST_PARTY_GATE_ENABLED = False
    settings.API_THROTTLE_ENABLED = False
