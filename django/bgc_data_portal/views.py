# Copyright 2024 EMBL - European Bioinformatics Institute
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Project-level views.

Trimmed in the v2 refactor: legacy ``search``/``results``/``bgc_page``/
``download_bgc``/``download_results_tsv`` handlers are gone — those
surfaces lived under ``/legacy/*`` and were retired with the
``mgnify_bgcs`` app. The remaining views serve the static portal pages
(landing, about, docs) and the React SPA at ``/dashboard/``.
"""

import logging
import os

from csp.decorators import csp_update
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils._os import safe_join
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

log = logging.getLogger(__name__)
numeric_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
log.setLevel(numeric_level)


# The docs are static Quarto-generated HTML. Quarto needs a markedly looser CSP
# than the app, and it's all relaxed for THIS view only (content is built by us
# and served same-origin, so the risk is low) while the app + SPA keep the strict
# policy. Quarto uses:
#   * inline <script> blocks (Headroom, nav, search)        -> 'unsafe-inline'
#   * a mermaid/OJS runtime that uses eval/new Function      -> 'unsafe-eval'
#   * ES modules + styles + fonts inlined as data: URIs      -> data: in
#     script-src / style-src / font-src
# (style-src/font-src already allow 'self'+VF globally; we only add data: here.)
@method_decorator(
    csp_update(
        {
            "script-src": ["'unsafe-inline'", "'unsafe-eval'", "data:"],
            "style-src": ["data:"],
            "font-src": ["data:"],
        }
    ),
    name="dispatch",
)
class DocsView(TemplateView):
    def get(self, request, path="index.html", *args, **kwargs):
        docs_root = os.path.join(settings.BASE_DIR, "docs", "_site")
        # ``path`` is user-controlled (``<path:path>`` route); ``safe_join``
        # raises ``SuspiciousFileOperation`` for any path that escapes
        # ``docs_root`` (e.g. ``../../settings.py``), blocking path traversal.
        try:
            file_path = safe_join(docs_root, path)
        except SuspiciousFileOperation:
            raise Http404("File not found")
        if os.path.isfile(file_path):
            return FileResponse(open(file_path, "rb"))
        raise Http404("File not found")


def landing_page(request):
    """Render the landing page."""
    return render(request, "landing_page.html")


def keyword_search(request):
    """Resolve a landing-page keyword and redirect into the dashboard.

    Replaces the legacy ``search`` view retired in the v2 refactor. The
    discovery keyword resolver maps the term to the best-matching filter
    (BGC/assembly/domain accession, BGC class, detector, biome, taxonomy,
    organism, natural product) and falls back to the free-text ``search``
    param. The resulting ``/dashboard/?…&auto_run=true`` URL is consumed by
    the SPA's URL-sync hook, which hydrates the filter store and runs the
    query on arrival.
    """
    from discovery.services.keyword_resolver import resolve_keyword

    result = resolve_keyword(request.GET.get("keyword", ""))
    return redirect(result["redirect_url"])


def about(request):
    """Render the about page."""
    return render(request, "about.html")


def dashboard_spa(request):
    """Serve the React SPA for the Discovery Platform."""
    return render(request, "dashboard.html", {
        "FORCE_SCRIPT_NAME": settings.FORCE_SCRIPT_NAME,
        "DEBUG": settings.DEBUG,
    })


def custom_404_view(request, exception):
    """Custom 404 error view."""
    return render(request, "404.html", status=404)
