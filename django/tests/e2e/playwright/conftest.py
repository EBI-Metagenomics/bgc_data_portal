import os
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--e2e-v2-base-url",
        action="store",
        dest="e2e_v2_base_url",
        default=None,
        help=(
            "Base URL for the v2 Discovery dashboard E2E suite "
            "(test_v2_discovery_journey). Defaults to http://localhost:8000."
        ),
    )


@pytest.fixture(scope="session")
def e2e_v2_base_url(pytestconfig) -> str:
    """Base URL for the v2 iBGC-first dashboard.

    The React SPA mounts at ``/dashboard/`` (the ``dashboard_spa`` view; ``/``
    is the separate landing page). Defaults to ``http://localhost:8080/dashboard``
    — the Skaffold local port-forward (``django:80 -> :8080``, see
    skaffold.yaml). Pass ``--e2e-v2-base-url`` (or set ``E2E_V2_BASE_URL``) to
    point at a deployed instance; include the ``/dashboard`` path.
    """
    cli_val = pytestconfig.getoption("e2e_v2_base_url")
    env_val = os.environ.get("E2E_V2_BASE_URL")
    base = cli_val or env_val or "http://localhost:8080/dashboard"
    return base.rstrip("/")
