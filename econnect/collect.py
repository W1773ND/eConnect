# -*- coding: utf-8 -*-
import logging
import string
from datetime import datetime, timedelta
import random
from threading import Thread

import requests
from currencies.models import Currency
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import Group
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.db.models import Sum
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.utils.http import urlquote
from django.utils.translation import gettext as _

from echo.utils import LOW_MAIL_LIMIT, notify_for_low_messaging_credit, notify_for_empty_messaging_credit
from ikwen.conf.settings import WALLETS_DB_ALIAS
from ikwen.core.constants import CONFIRMED
from ikwen.accesscontrol.backends import UMBRELLA
from ikwen.accesscontrol.models import SUDO
from ikwen.billing.models import Invoice, Payment, PAYMENT_CONFIRMATION, InvoiceEntry, Product, InvoiceItem, Donation, \
    SupportBundle, SupportCode, MoMoTransaction
from ikwen.billing.mtnmomo.views import MTN_MOMO
from ikwen.billing.utils import get_invoicing_config_instance, get_days_count, get_payment_confirmation_message, \
    share_payment_and_set_stats, get_next_invoice_number, refill_tsunami_messaging_bundle, get_subscription_model, \
    notify_event
from ikwen.core.models import Service
from ikwen.core.utils import add_database_to_settings, get_service_instance, add_event, get_mail_content, XEmailMessage
from echo.models import Balance

from econnect.models import Order

logger = logging.getLogger('ikwen')

Subscription = get_subscription_model()
SUBSCRIPTION_DURATION = 30  # Defaults to 1 month upon online payment. Admin can later extend expiry on the Subscription detail


def order_set_checkout(request, *args, **kwargs):
    service = get_service_instance()
    config = service.config
    invoice_id = request.POST['product_id']
    invoice = Invoice.objects.get(pk=invoice_id)

    buyer = request.user.username if request.user.is_authenticated() else 'anonymous'
    amount = invoice.amount
    model_name = 'billing.Invoice'
    invoice_id = invoice.id

    mean = request.GET.get('mean', MTN_MOMO)
    tx = MoMoTransaction.objects.using(WALLETS_DB_ALIAS) \
        .create(service_id=service.id, type=MoMoTransaction.CASH_OUT, amount=amount, phone='N/A',
                model=model_name, object_id=invoice_id, wallet=mean, username=buyer, is_running=True)
    notification_url = service.url + reverse('econnect:confirm_invoice_payment', args=(tx.id, ))
    cancel_url = service.url + reverse('econnect:my_creolink')  # Orange Money only
    return_url = service.url + reverse('billing:invoice_detail', args=(invoice.id,))
    gateway_url = getattr(settings, 'IKWEN_PAYMENT_GATEWAY_URL', 'http://momogateway.cyberlink.cm/v1')
    endpoint = gateway_url + '/request_payment'
    params = {
        'username': getattr(settings, 'IKWEN_PAYMENT_GATEWAY_USERNAME', 'econnect'),
        'amount': amount,
        'merchant_name': config.company_name,
        'notification_url': notification_url,
        'return_url': return_url,
        'cancel_url': cancel_url,
        'user_id': buyer
    }
    try:
        r = requests.get(endpoint, params)
        resp = r.json()
        token = resp.get('token')
        if token:
            next_url = gateway_url + '/checkoutnow/' + resp['token'] + '?mean=' + mean
        else:
            messages.error(request, resp['errors'])
            next_url = cancel_url
    except:
        logger.error("%s - Init payment flow failed with URL %s." % (service.project_name, r.url), exc_info=True)
        next_url = cancel_url
    return HttpResponseRedirect(next_url)


def confirm_invoice_payment(request, *args, **kwargs):
    status = request.GET['status']
    message = request.GET['message']
    operator_tx_id = request.GET['operator_tx_id']
    phone = request.GET['phone']
    tx_id = kwargs['tx_id']

    tx = MoMoTransaction.objects.using(WALLETS_DB_ALIAS).get(pk=tx_id)
    if not getattr(settings, 'DEBUG', False):
        tx_timeout = getattr(settings, 'IKWEN_PAYMENT_GATEWAY_TIMEOUT', 15) * 60
        expiry = tx.created_on + timedelta(seconds=tx_timeout)
        if datetime.now() > expiry:
            return HttpResponse("Transaction %s timed out." % tx_id)

    tx.status = status
    tx.message = message
    tx.processor_tx_id = operator_tx_id
    tx.phone = phone
    tx.is_running = False
    tx.save()
    if status != MoMoTransaction.SUCCESS:
        return HttpResponse("Notification for transaction %s received with status %s" % (tx_id, status))
    invoice = Invoice.objects.get(pk=tx.object_id)
    payment = Payment.objects.create(invoice=invoice, method=Payment.MOBILE_MONEY,
                                     amount=tx.amount, processor_tx_id=operator_tx_id)
    payment.save()
    invoice.paid = invoice.amount
    invoice.status = Invoice.PAID
    invoice.save()
    return HttpResponse("Notification for transaction %s received with status %s" % (tx_id, status))


def order_do_checkout(request, *args, **kwargs):
    invoice_id = request.session['object_id']
    invoice = Invoice.objects.get(pk=invoice_id)
    member = request.user
    now = datetime.now()
    duration = SUBSCRIPTION_DURATION
    expiry = now + timedelta(days=duration)
    subscription = invoice.subscription
    subscription.expiry = expiry
    subscription.status = Subscription.ACTIVE
    subscription.save()
    invoice.paid = invoice.amount
    invoice.status = Invoice.PAID
    invoice.save()
    order = subscription.order
    order.status = Invoice.PAID
    order.save()
    payment = Payment.objects.create(invoice=invoice, method=Payment.MOBILE_MONEY, amount=invoice.amount)
    service = get_service_instance()
    config = service.config

    if member.email:
        invoice_url = service.url + reverse('billing:invoice_detail', args=(invoice.id,))
        subject, message, sms_text = get_payment_confirmation_message(payment, member)
        html_content = get_mail_content(subject, message, template_name='billing/mails/notice.html',
                                        extra_context={'member_name': member.first_name, 'invoice': invoice,
                                                       'cta': _("View invoice"), 'invoice_url': invoice_url})
        sender = '%s <no-reply@%s>' % (config.company_name, service.domain)
        msg = XEmailMessage(subject, html_content, sender, [member.email])
        msg.content_subtype = "html"
        Thread(target=lambda m: m.send(), args=(msg,)).start()
    messages.success(request, _("Successful payment. Your subscription is now active."))
    return HttpResponseRedirect(request.session['return_url'])
