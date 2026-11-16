"""First-party access gate for UI-only / abuse-prone Discovery endpoints.

The Discovery SPA is served from the *same origin* as the API, so genuine
browser traffic carries Fetch-Metadata (``Sec-Fetch-Site``) and/or an
``Origin`` / ``Referer`` whose host is one of the site's own hosts. External
programmatic clients (curl, requests, httpx, notebooks) send none of these by
default, so they are rejected with ``403``.

This is deliberately *not* a secret-token / login auth — the public portal has
no user accounts. Its job is narrow: keep endpoints that only exist to drive
the web UI (filter dropdowns, plot coordinate feeds, the shortlist-report
cache, stats panels) and the compute-/upload-heavy endpoints off the public
*programmatic* surface, while leaving the SPA fully functional. The curated,
documented API (roster ids, iBGC/assembly detail, downloads, accession
resolve, …) stays open.

Apply it per-operation via ``auth=first_party_gate``. It can be turned off
wholesale with ``API_FIRST_PARTY_GATE_ENABLED = False`` (the test suite does
this; see ``tests/conftest.py``).

Note: ``Sec-Fetch-*`` are forbidden header names, so page JavaScript cannot
forge them — but a non-browser client obviously can set any header it likes.
This raises the bar against casual scraping and removes these routes from the
advertised docs; it is not a defence against a determined caller. Real
abuse-resistance for the upload/search endpoints still wants rate limiting.
"""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from ninja.errors import HttpError

# Fetch-Metadata site values we treat as first-party.
#   same-origin / same-site -> SPA fetch() calls (the normal path)
#   none                     -> user-initiated browser navigation (typed URL,
#                               bookmark, an in-app download opened in a new tab)
_ALLOWED_FETCH_SITES = {"same-origin", "same-site", "none"}

_FORBIDDEN_DETAIL = "This endpoint is restricted to the BGC portal web app."


def _trusted_hosts() -> set[str]:
    """Hostnames that count as first-party for the Origin/Referer fallback."""
    hosts: set[str] = set()
    for entry in settings.ALLOWED_HOSTS or []:
        hosts.add(entry.lstrip(".").lower())
    for origin in list(getattr(settings, "CSRF_TRUSTED_ORIGINS", [])) + list(
        getattr(settings, "CORS_TRUSTED_ORIGINS", [])
    ):
        netloc = urlparse(origin).netloc
        if netloc:
            hosts.add(netloc.split("@")[-1].split(":")[0].lower())
    return hosts


def _host_is_trusted(url_value: str) -> bool:
    """True when the host of an ``Origin``/``Referer`` URL is first-party."""
    if not url_value:
        return False
    netloc = urlparse(url_value).netloc
    if not netloc:
        return False
    host = netloc.split("@")[-1].split(":")[0].lower()
    trusted = _trusted_hosts()
    return "*" in trusted or host in trusted


class FirstPartyGate:
    """Django-Ninja auth callable admitting only first-party browser traffic."""

    # Surfaced as the OpenAPI security scheme name on any documented gated op.
    openapi_scheme = "first_party"

    def __call__(self, request):
        if not getattr(settings, "API_FIRST_PARTY_GATE_ENABLED", True):
            return True

        site = request.headers.get("Sec-Fetch-Site")
        if site is not None:
            if site in _ALLOWED_FETCH_SITES:
                return True
            # Explicit cross-site request from a real browser -> reject.
            raise HttpError(403, _FORBIDDEN_DETAIL)

        # No Fetch-Metadata (older browser / non-browser). Fall back to
        # validating the Origin or Referer host against the site's own hosts.
        for header in ("Origin", "Referer"):
            value = request.headers.get(header)
            if value and _host_is_trusted(value):
                return True

        raise HttpError(403, _FORBIDDEN_DETAIL)


# Module-level singleton to pass as ``auth=`` on gated operations.
first_party_gate = FirstPartyGate()
