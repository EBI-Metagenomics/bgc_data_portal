import os
import pytest


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Send ``X-No-Debug-Toolbar`` on every request so the dev debug-toolbar's
    fixed overlay never intercepts Playwright clicks (see settings
    ``_show_debug_toolbar``)."""
    return {
        **browser_context_args,
        "extra_http_headers": {"X-No-Debug-Toolbar": "1"},
    }


@pytest.fixture(autouse=True)
def _suppress_welcome_tour(page):
    """Pre-set the onboarding flag so the first-visit welcome dialog never
    opens — its modal overlay otherwise swallows clicks. Mirrors
    ``onboarding-store``'s ``bgc-discovery-welcome-seen`` localStorage key.
    Runs on every navigation, before the app's scripts read it."""
    page.add_init_script(
        "window.localStorage.setItem('bgc-discovery-welcome-seen', 'true');"
    )
    return page


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
