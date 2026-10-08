from django.conf import settings

def portal_meta(request):
    return {
        'PORTAL_VERSION': settings.PORTAL_VERSION,
        'PORTAL_LAST_MODIFIED': settings.PORTAL_LAST_MODIFIED,
        'PORTAL_SHORT_NAME': settings.PORTAL_SHORT_NAME,
        'PORTAL_LONG_NAME': settings.PORTAL_LONG_NAME,
        'PORTAL_COPYRIGHT': settings.PORTAL_COPYRIGHT,
    }
