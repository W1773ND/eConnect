from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Sum

from ikwen.accesscontrol.models import Member
from ikwen.core.context_processors import project_settings as ikwen_settings
from ikwen.core.constants import PENDING, PENDING_FOR_PAYMENT, STARTED
from ikwen.billing.models import Invoice, PaymentMean
from ikwen_webnode.blog.views import Comment

from echo.models import PopUp

from econnect.models import Order, REPORTED, Profile, CANCELED


def project_settings(request):
    """
    Adds utility project url and ikwen base url context variable to the context.
    """
    econnect_settings = ikwen_settings(request)
    econnect_settings['settings'].update({
        'GOOGLE_MAPS_API_KEY': getattr(settings, 'GOOGLE_MAPS_API_KEY'),
        'CREOLINK_MAPS_URL': getattr(settings, 'CREOLINK_MAPS_URL'),
    })
    try:
        econnect_settings['yup'] = PaymentMean.objects.get(slug='yup')
    except:
        pass
    return econnect_settings


def order_status(order_id):
    order = {}
    try:
        pending_order_qs = Order.objects.filter(status=PENDING)
        aggr = pending_order_qs.aggregate(Sum('cost'))
        total_pending_order = {'count': pending_order_qs.count(), 'cost': aggr['cost__sum']}
    except:
        total_pending_order = {'count': 0, 'amount': 0}
    try:
        pending_for_payment_order_qs = Order.objects.filter(status=PENDING_FOR_PAYMENT)
        aggr = pending_for_payment_order_qs.aggregate(Sum('cost'))
        total_pending_for_payment_order = {'count': pending_for_payment_order_qs.count(), 'cost': aggr['cost__sum']}
    except:
        total_pending_for_payment_order = {'count': 0, 'amount': 0}
    try:
        paid_order_qs = Order.objects.filter(status=Invoice.PAID)
        aggr = paid_order_qs.aggregate(Sum('cost'))
        total_paid_order = {'count': paid_order_qs.count(), 'cost': aggr['cost__sum']}
    except:
        total_paid_order = {'count': 0, 'amount': 0}
    try:
        reported_order_qs = Order.objects.filter(status=REPORTED)
        aggr = reported_order_qs.aggregate(Sum('cost'))
        total_reported_order = {'count': reported_order_qs.count(), 'cost': aggr['cost__sum']}
    except:
        total_reported_order = {'count': 0, 'amount': 0}
    try:
        canceled_order_qs = Order.objects.filter(status=CANCELED)
        aggr = canceled_order_qs.aggregate(Sum('cost'))
        total_canceled_order = {'count': canceled_order_qs.count(), 'cost': aggr['cost__sum']}
    except:
        total_canceled_order = {'count': 0, 'amount': 0}
    order['pending_order'] = total_pending_order
    order['pending_for_payment_order'] = total_pending_for_payment_order
    order['paid_order'] = total_paid_order
    order['reported_order'] = total_reported_order
    order['canceled_order'] = total_canceled_order
    return order


def community_stats(c):
    community = {}
    registered_member_count = Member.objects.exclude(is_ghost=True).count()
    unregistered_member_count = Member.objects.filter(is_ghost=True).count()
    community['registered_member_count'] = registered_member_count
    community['unregistered_member_count'] = unregistered_member_count
    return community


def billing_stats(c):
    billing = {}
    try:
        sent_invoice_qs = Invoice.objects.filter(status=Invoice.PENDING)
        aggr = sent_invoice_qs.aggregate(Sum('amount'))
        total_sent_invoice = {'count': sent_invoice_qs.count(), 'amount':aggr['amount__sum']}
    except:
        total_sent_invoice = {'count': 0, 'amount': 0}
    billing['sent_invoice'] = total_sent_invoice
    return billing


def pop_up(r):
    try:
        popup = PopUp.objects.filter(is_active=True)
    except PopUp.DoesNotExist:
        pass
    return popup


def customer_profile(request):
    profile = {}
    member = request.user
    if member.is_authenticated():
        try:
            user_profile = Profile.objects.get(member=member)
            profile['code_client'] = user_profile.code
        except Profile.DoesNotExist:
            pass
        pending_invoice_count = Invoice.objects.filter(member=member, status=PENDING).count()
        profile['pending_invoice_count'] = pending_invoice_count
    return profile


def comments(comment_id):
    comment ={}
    comment_qs = Comment.objects.all()
    comment['comment_count'] = comment_qs.count()
