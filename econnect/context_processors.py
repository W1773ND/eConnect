from django.conf import settings
from ikwen.core.context_processors import project_settings as ikwen_settings


def project_settings(request):
    """
    Adds utility project url and ikwen base url context variable to the context.
    """
    econnect_settings = ikwen_settings(request)
    econnect_settings['settings'].update({
        'GOOGLE_MAPS_API_KEY': getattr(settings, 'GOOGLE_MAPS_API_KEY'),
    })
    return econnect_settings
