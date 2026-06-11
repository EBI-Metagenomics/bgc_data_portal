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

from csp.decorators import csp_update
from debug_toolbar.toolbar import debug_toolbar_urls
from discovery.api import discovery_router
from ninja.openapi.docs import Redoc

from django.contrib import admin
from django.urls import path, re_path

from . import views
from .api import api as ninja_api

ninja_api.add_router("/discovery/", discovery_router)

handler404 = "bgc_data_portal.views.custom_404_view"


# ReDoc as an alternative API reference at /api/redoc (Swagger stays at
# /api/docs). django-ninja self-hosts the ReDoc bundle (script-src 'self'), but
# its template uses an inline init <script> and the bundle uses eval/new Function
# and blob web workers — so relax script-src for THIS view only, while the app
# keeps the strict policy. (worker-src 'self' blob: and style-src 'unsafe-inline'
# are already allowed globally.)
@csp_update({"script-src": ["'unsafe-inline'", "'unsafe-eval'"]})
def redoc_view(request):
    return Redoc().render_page(request, ninja_api)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("about/", views.about, name="about"),
    path("search/", views.keyword_search, name="keyword_search"),
    path("docs/", views.DocsView.as_view(), {"path": "index.html"}, name="docs_index"),
    path("docs/<path:path>", views.DocsView.as_view(), name="docs_file"),
    path("docs/<path:path>/", views.DocsView.as_view(), name="docs"),
    path("", views.landing_page, name="landing_page"),
    path("dashboard/", views.dashboard_spa, name="dashboard"),
    re_path(r"^dashboard/.*$", views.dashboard_spa),
    # /api/redoc must precede the ninja_api include (which owns the "api/" prefix).
    path("api/redoc", redoc_view, name="api_redoc"),
    path("api/", ninja_api.urls, name="api"),
] + debug_toolbar_urls()
