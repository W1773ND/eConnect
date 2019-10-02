from django.conf import settings
from ikwen.core.context_processors import project_settings as ikwen_settings
from ikwen.core.constants import PENDING, PENDING_FOR_PAYMENT
from ikwen.billing.models import Invoice

from econnect.models import Order, REPORTED, CANCELED


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


def order_status(order_id):
    order = {}
    pending_order_list = Order.objects.filter(status=PENDING)
    pending_for_payment_order_list = Order.objects.filter(status=PENDING_FOR_PAYMENT)
    paid_order_list = Order.objects.filter(status=Invoice.PAID)
    reported_order_list = Order.objects.filter(status=REPORTED)
    canceled_order_list = Order.objects.filter(status=CANCELED)
    order['pending_order_list'] = pending_order_list
    order['pending_for_payment_order_list'] = pending_for_payment_order_list
    order['paid_order_list'] = paid_order_list
    order['reported_order_list'] = reported_order_list
    order['canceled_order_list'] = canceled_order_list
    return order
