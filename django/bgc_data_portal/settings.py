"""
Django settings for bgc_data_portal project.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from csp.constants import NONE, SELF
from django.core.exceptions import ImproperlyConfigured

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment helpers


# Core settings
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DJANGO_DEBUG", default="False").lower() == "true"

IS_COLLECTSTATIC = "collectstatic" in sys.argv

# Allowed hosts
ALLOWED_HOSTS_ENV = os.getenv("ALLOWED_HOSTS", "")
if not ALLOWED_HOSTS_ENV:
    if DEBUG or IS_COLLECTSTATIC:
        ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
    else:
        raise ImproperlyConfigured("Set the ALLOWED_HOSTS environment variable")
else:
    ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_ENV.split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS = [
    x.strip() for x in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()
]
CORS_TRUSTED_ORIGINS = [
    x.strip() for x in os.getenv("CORS_TRUSTED_ORIGINS", "").split(",") if x.strip()
]

# First-party API gate (see discovery/security.py). When enabled, UI-only and
# abuse-prone Discovery endpoints accept only same-origin browser traffic
# (the SPA), rejecting external programmatic callers with 403. The curated
# public API stays open. Disabled automatically in the test suite.
API_FIRST_PARTY_GATE_ENABLED = (
    os.getenv("API_FIRST_PARTY_GATE_ENABLED", "true").lower() == "true"
)

# Per-client-IP rate limiting (see discovery/throttling.py). Rates are
# "<count>/<period>" with period one of s|m|h|d; tune per deployment via env
# without code changes. Counters live in the default cache (Postgres
# DatabaseCache, shared across workers/pods). Disabled in the test suite.
API_THROTTLE_ENABLED = os.getenv("API_THROTTLE_ENABLED", "true").lower() == "true"
API_THROTTLE_RATES = {
    "default": os.getenv("API_THROTTLE_DEFAULT", "300/m"),
    "search": os.getenv("API_THROTTLE_SEARCH", "30/m"),
    "upload": os.getenv("API_THROTTLE_UPLOAD", "20/h"),
}
# Number of trusted reverse proxies in front of Django (k8s ingress, LB).
# Django-Ninja's throttle keys on the client IP it derives from
# X-Forwarded-For; without this count it uses the whole header, which a client
# can spoof to get a fresh throttle bucket per request. The chart sets it to 1
# (the ingress); leave it unset only in local dev (no proxy).
_ninja_num_proxies = os.getenv("NINJA_NUM_PROXIES")
if _ninja_num_proxies:
    NINJA_NUM_PROXIES = int(_ninja_num_proxies)
elif not DEBUG and not IS_COLLECTSTATIC and "pytest" not in sys.modules:
    raise ImproperlyConfigured(
        "Set NINJA_NUM_PROXIES to the number of reverse proxies in front of "
        "Django (1 behind the k8s ingress); the per-IP throttle depends on it"
    )

# Allow overriding the externally mounted base path (used for URL reversing, static paths, etc.)
# Default remains the production prefix to keep existing behaviour, but can be overridden in dev.
FORCE_SCRIPT_NAME = os.getenv("DJANGO_FORCE_SCRIPT_NAME", "")

# Django always sits behind the k8s ingress (or runserver in dev), so trust the
# proxy's Host and X-Forwarded-Proto. Do not expose gunicorn directly.
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    # Only the Django admin uses session/CSRF cookies; mark them Secure.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

STATIC_URL = f"{FORCE_SCRIPT_NAME}/static/"

# Internal IPs
INTERNAL_IPS = ["127.0.0.1"]


def _show_debug_toolbar(request):
    """Gate the debug toolbar so it never interferes with automation.

    Off entirely under pytest (the toolbar middleware crashes the Django test
    client while rendering) and whenever a request opts out via the
    ``X-No-Debug-Toolbar`` header — the e2e browser context sends it so the
    toolbar's fixed overlay doesn't swallow Playwright clicks.
    """
    if not DEBUG or "pytest" in sys.modules:
        return False
    return not request.headers.get("X-No-Debug-Toolbar")


DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": _show_debug_toolbar}

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "ninja",
    "matomo",
    "django_tasks",
    "django_tasks_db",
    "csp",
    "discovery",
]

if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "csp.middleware.CSPMiddleware",
]

if DEBUG:
    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]

ROOT_URLCONF = "bgc_data_portal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "bgc_data_portal", "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "bgc_data_portal.context_processors.use_matomo",
            ],
        },
    },
]

WSGI_APPLICATION = "bgc_data_portal.wsgi.application"

# Database
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        conn_max_age=600,
    )
}

# Background tasks — django-tasks with the Postgres-backed django-tasks-db
# backend (no broker, no Redis result store). The DB-poll worker claims rows
# with SELECT … FOR UPDATE SKIP LOCKED, so multiple worker pods are safe.
# Two queues: "default" (searches, uploads, stats) and "scores" (long
# recomputes). Run a worker with:
#   python manage.py db_worker --queue-name default,scores
TASKS = {
    "default": {
        "BACKEND": "django_tasks_db.DatabaseBackend",
        "QUEUES": ["default", "scores"],
    }
}


# Domain reference databases accepted by the Evaluate Asset / asset-upload flow.
# Must match ref_db_allowlist in mgnify-bgcs-etl/config/load/merge_staged_tsvs.yaml
# so uploaded assets are compared against the same subset of domains that is
# actually loaded into the Discovery DB.
ALLOWED_DOMAIN_REF_DBS: tuple[str, ...] = ("PFAM", "TIGRFAM", "NCBIFAM")

# Filesystem destination for post-clustering analysis artifacts (TSV + Plotly HTMLs).
# Each ClusteringRun writes to <CLUSTERING_ARTIFACTS_DIR>/<run_sha[:12]>/.
CLUSTERING_ARTIFACTS_DIR: Path = Path(
    os.environ.get(
        "CLUSTERING_ARTIFACTS_DIR",
        BASE_DIR / "data" / "clustering_artifacts",
    )
)

# On-disk phmmer protein search DB (FASTA + .ssi + VERSION).
# Lives on the shared PVC so every db_worker pod can read it.
PROTEIN_SEARCH_INDEX_DIR: Path = Path(
    os.environ.get(
        "PROTEIN_SEARCH_INDEX_DIR",
        BASE_DIR / "data" / "protein_search",
    )
)

# Intra-query parallelism for the phmmer scan. A single sequence query is split
# across this many threads, each scanning a slice of the resident protein block
# (pyhmmer releases the GIL during the C search), giving near-linear speedup.
# One worker handles one task at a time, but that task uses all the pod's
# cores. NB: pyhmmer's own `cpus=` param
# parallelises across *queries*, so it does nothing for a single query — the
# split is done by us. Defaults to the pod's core count, capped at 8.
PROTEIN_SEARCH_CPUS: int = int(
    os.environ.get("PROTEIN_SEARCH_CPUS", str(min((os.cpu_count() or 1), 8)))
)


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
# STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # NOT the same as STATICFILES_DIRS

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Default primary key
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Caching — Postgres-backed DatabaseCache (no Redis). Counters/payloads are
# small JSON; the table is shared across gunicorn workers and pods, and
# DatabaseCache culls on write + checks expiry on read. Create the backing
# table once with `python manage.py createcachetable`.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": os.getenv("DJANGO_CACHE_TABLE", "django_cache"),
        "OPTIONS": {
            # Cap growth; the high-churn keys are asset:*/report:* (TTL-bounded).
            "MAX_ENTRIES": int(os.getenv("DJANGO_CACHE_MAX_ENTRIES", "50000")),
        },
    }
}
CACHE_TIMEOUT = 60 * 60 * 24 * 7  # 1 week

# Staging dir for the large (~100 MB) asset-upload tarball. Parked on the shared
# RWX PVC (NOT the cache) so the worker pod — a separate pod with its own FS —
# can read what the web pod wrote. Defaults under MEDIA_ROOT's PVC.
UPLOAD_STAGING_DIR: Path = Path(
    os.environ.get("UPLOAD_STAGING_DIR", BASE_DIR / "data" / "upload_staging")
)

# Matomo
MATOMO_URL = os.getenv("MATOMO_URL")
MATOMO_SITE_ID = (
    int(os.getenv("MATOMO_SITE_ID")) if os.getenv("MATOMO_SITE_ID") else None
)

# Content Security Policy (CSP) — enforced by csp.middleware.CSPMiddleware.
#
# Scoped to the app's real resource origins:
#   * 'self'                     — Django pages, the React SPA bundle, /api, static
#   * assets.emblstatic.net      — EMBL Visual Framework CSS/JS + its woff/svg assets
#   * MATOMO_URL                 — analytics tracker + beacon, only when configured
# Fonts are self-hosted (static/css/fonts.css), so no Google Fonts origins are
# needed. 'unsafe-inline' is required for styles (VF + Plotly inject <style> blocks
# and inline style="" attributes) — a known, accepted limitation of those libs.
# Scripts deliberately avoid 'unsafe-inline'/'unsafe-eval' except for the Matomo
# inline bootstrap, which is only allowed when Matomo is enabled.
#
# Roll-out safety: set CSP_REPORT_ONLY=true to emit the policy as
# Content-Security-Policy-Report-Only (logs violations without blocking) while
# validating the dashboard, then unset to enforce.
_VF_HOST = "https://assets.emblstatic.net"

# The EMBL VF hero/masthead background images (e.g. roundels.png) are served
# through the embl.org cloudimg proxy, not emblstatic — without these the hero
# falls back to its bare green background colour.
_EMBL_IMG_HOSTS = ["https://acxngcvroo.cloudimg.io", "https://www.embl.org"]

# The EMBL VF global header's "content hub" widget fetches notifications and
# ontology patterns from these EMBL services (with a github.io fallback). Without
# them the header's notification bell silently fails (no impact on the app data).
_EMBL_CONNECT_HOSTS = [
    "https://www.embl.org",
    "https://wwwdev.embl.org",
    "https://embl-communications.github.io",
]

_csp_script = [SELF, _VF_HOST]
_csp_style = [SELF, _VF_HOST, "'unsafe-inline'"]
_csp_font = [SELF, _VF_HOST]
_csp_img = [SELF, "data:", _VF_HOST, *_EMBL_IMG_HOSTS]
_csp_connect = [SELF, *_EMBL_CONNECT_HOSTS]

if MATOMO_URL:
    _csp_script += [MATOMO_URL, "'unsafe-inline'"]
    _csp_img.append(MATOMO_URL)
    _csp_connect.append(MATOMO_URL)

_CSP_DIRECTIVES = {
    "default-src": [SELF],
    "script-src": _csp_script,
    "style-src": _csp_style,
    "font-src": _csp_font,
    "img-src": _csp_img,
    "connect-src": _csp_connect,
    "worker-src": [SELF, "blob:"],  # SPA may spin up web workers from blob URLs
    "object-src": [NONE],  # no <object>/<embed>/<applet>
    "base-uri": [SELF],  # block <base> tag hijacking
    "frame-ancestors": [SELF],  # clickjacking protection
}

if os.getenv("CSP_REPORT_ONLY", "false").lower() == "true":
    CONTENT_SECURITY_POLICY_REPORT_ONLY = {"DIRECTIVES": _CSP_DIRECTIVES}
else:
    CONTENT_SECURITY_POLICY = {"DIRECTIVES": _CSP_DIRECTIVES}

# Logging

DJANGO_MANAGED_LOG_LEVEL = "DEBUG" if DEBUG else "INFO"
# LOG_LEVEL overrides the DEBUG-derived default for the app and Django loggers.
LOG_LEVEL = os.getenv("LOG_LEVEL", DJANGO_MANAGED_LOG_LEVEL).upper()
# Django logs every SQL statement at DEBUG when DEBUG=True; with bulk loads
# that is tens of GB per run. Opt in with DJANGO_SQL_LOG_LEVEL=DEBUG.
SQL_LOG_LEVEL = os.getenv("DJANGO_SQL_LOG_LEVEL", "INFO").upper()


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            # Pass-through; the logger levels below decide what is emitted.
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": SQL_LOG_LEVEL,
            "propagate": False,
        },
        "psycopg": {"level": "INFO"},
        # django-debug-toolbar 5.0.1's history_sidebar view renders
        # panel_content.html without `toolbar` in context, producing noisy
        # VariableDoesNotExist DEBUG traces on every page reload. Harmless —
        # the template falls back to the lazy-load branch as intended.
        "django.template": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
