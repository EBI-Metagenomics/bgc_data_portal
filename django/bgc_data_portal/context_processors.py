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

from django.conf import settings


def use_matomo(request):
    """
    Context processor: whether Matomo analytics should be used, plus the
    prefix-aware URL of the API docs (``api_docs_url``) shared by the templates.
    """
    # Honour a reverse-proxy prefix (SCRIPT_NAME / FORCE_SCRIPT_NAME) so the
    # link works both at ``/api/docs`` and ``/finn-srv/mgnify-bgcs/api/docs``.
    api_docs_url = f"{request.META.get('SCRIPT_NAME', '')}/api/docs"
    try:
        use_matomo = settings.MATOMO_URL and settings.MATOMO_SITE_ID
    except AttributeError:
        use_matomo = False
    return {"use_matomo": use_matomo, "api_docs_url": api_docs_url}
