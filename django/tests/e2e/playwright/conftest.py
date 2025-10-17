import os
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--e2e-base-url",
        action="store",
        dest="e2e_base_url",
        default=None,
        help="Base URL for E2E tests (e.g., https://bgc-portal-dev.mgnify.org)",
    )


@pytest.fixture(scope="session")
def e2e_base_url(pytestconfig) -> str:
    # Priority: CLI option > env var > default dev host
    cli_val = pytestconfig.getoption("e2e_base_url")
    env_val = os.environ.get("E2E_BASE_URL")
    base = cli_val or env_val or "https://bgc-portal-dev.mgnify.org"
    return base.rstrip("/")
