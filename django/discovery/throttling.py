"""Per-client-IP rate limiting for the Discovery API.

Layered on top of the first-party gate (``discovery/security.py``): the gate
keeps external programmatic callers out of UI-only endpoints, while these
throttles cap request *volume* per client IP for everyone — same-origin browser
traffic and the curated public endpoints alike — so a single client can't hammer
the service (scraping, runaway loops, DoS).

Why not Ninja's ``AnonRateThrottle``: it returns no cache key (skips throttling)
for any request whose ``request.auth`` is set, and the first-party gate sets
``request.auth = True`` as a marker — which would disable throttling on exactly
the gated endpoints. These classes key on client IP unconditionally.

Tiers (rates from ``settings.API_THROTTLE_RATES``, env-tunable):
  * default — every Discovery endpoint (generous; never bothers a real UI user)
  * search  — the compute-heavy query endpoints (sequence/chemical dispatch,
              similar-iBGC, architecture, domain)
  * upload  — ephemeral asset upload (strictest; writes + Celery + Redis)

Throttle state lives in the default Django cache (Redis), so counters are shared
across gunicorn workers and pods. Client IP resolution honours
``NINJA_NUM_PROXIES`` — set it to the number of trusted reverse proxies in front
of Django so the real client IP is read from ``X-Forwarded-For`` rather than a
spoofable left-most value. Disabled wholesale with ``API_THROTTLE_ENABLED =
False`` (the test suite does this; see ``tests/conftest.py``).
"""

from __future__ import annotations

from typing import Optional

from django.conf import settings
from ninja.throttling import SimpleRateThrottle


class _IPRateThrottle(SimpleRateThrottle):
    """Throttle keyed purely on client IP, ignoring the gate's auth marker."""

    def get_cache_key(self, request) -> Optional[str]:
        if not getattr(settings, "API_THROTTLE_ENABLED", True):
            return None  # disabled -> allow_request short-circuits to True
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class DefaultIPThrottle(_IPRateThrottle):
    scope = "ip_default"


class SearchIPThrottle(_IPRateThrottle):
    scope = "ip_search"


class UploadIPThrottle(_IPRateThrottle):
    scope = "ip_upload"


_rates = settings.API_THROTTLE_RATES

# Module-level instances passed to Ninja. Reused across requests per Ninja's
# design (safe under process-based gunicorn workers, which serve one request at
# a time per process).
default_throttle = DefaultIPThrottle(_rates["default"])
search_throttle = SearchIPThrottle(_rates["search"])
upload_throttle = UploadIPThrottle(_rates["upload"])
