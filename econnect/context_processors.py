from django.conf import settings
from ikwen.core.context_processors import project_settings as ikwen_settings


def project_settings(request):
    """
    Adds utility project url and ikwen base url context variable to the context.
    """
    econnect_settings = ikwen_settings(request)
    econnect_settings['settings'].update({
        'GOOGLE_MAPS_API_KEY': getattr(settings, 'GOOGLE_MAPS_API_KEY'),
        'CREOLINK_MAPS_URL': getattr(settings, 'CREOLINK_MAPS_URL'),
        'LOCAL_MAPS_URL': getattr(settings, 'LOCAL_MAPS_URL'),
    })
    return econnect_settings
