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
    Context processor to determine if Matomo analytics should be used.
    """
    try:
        return {"use_matomo": settings.MATOMO_URL and settings.MATOMO_SITE_ID}
    except AttributeError:
        return {"use_matomo": False}


def base_path(request):
    """
    Context processor to provide the base path for the application.
    """
    return {"base_path": settings.FORCE_SCRIPT_NAME}
