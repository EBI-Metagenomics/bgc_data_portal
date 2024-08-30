from django.conf import settings


def use_matomo(request):
    try:
        return {"use_matomo": settings.MATOMO_URL and settings.MATOMO_SITE_ID}
    except AttributeError:
        return {"use_matomo": False}


def base_path(request):
    return {
        'base_path': settings.FORCE_SCRIPT_NAME
    }