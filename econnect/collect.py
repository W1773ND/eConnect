# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, timedelta
from threading import Thread

from bson import ObjectId
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils.translation import gettext as _, get_language
from ikwen.billing.decorators import momo_gateway_request, momo_gateway_callback

from ikwen.billing.models import Invoice, Payment
from ikwen.billing.utils import get_payment_confirmation_message, get_subscription_model, generate_pdf_invoice, \
    get_invoicing_config_instance
from ikwen.core.utils import get_service_instance, get_mail_content, XEmailMessage

from econnect.forms import YUPCallbackForm

logger = logging.getLogger('ikwen')

Subscription = get_subscription_model()
SUBSCRIPTION_DURATION = 30  # Defaults to 1 month upon online payment. Admin can later extend expiry on the Subscription detail

YUP_APP = 'Yup App'


@momo_gateway_request
def order_set_checkout(request, *args, **kwargs):
    invoice_id = request.POST['product_id']
    invoice = Invoice.objects.get(pk=invoice_id)
    amount = invoice.amount
    if invoice.amount % 50 > 0:
        amount = (invoice.amount / 50 + 1) * 50  # Mobile Money Payment support only multiples of 50
    lang = get_language()

    notification_url = reverse('econnect:confirm_invoice_payment', args=(invoice.id, lang))
    return_url = reverse('billing:invoice_detail', args=(invoice.id, ))
    cancel_url = reverse('my_creolink')
    return invoice, amount, notification_url, return_url, cancel_url


@momo_gateway_callback
def confirm_invoice_payment(request, *args, **kwargs):
    tx = kwargs['tx']
    invoice = Invoice.objects.select_related().get(pk=tx.object_id)
    for val in [31, 30, 29, 28]:
        try:
            datetime(invoice.due_date.year, invoice.due_date.month, val)
            duration = val
            break
        except ValueError:
            continue
    expiry = invoice.due_date + timedelta(days=duration)
    subscription = invoice.subscription
    subscription.expiry = expiry
    subscription.status = Subscription.ACTIVE
    subscription.save()
    invoice.paid = invoice.amount
    invoice.status = Invoice.PAID
    invoice.save()
    try:
        order = subscription.order
        order.status = Invoice.PAID
        order.save()
    except:
        pass
    payment = Payment.objects.create(invoice=invoice, method=Payment.MOBILE_MONEY, amount=tx.amount,
                                     processor_tx_id=tx.processor_tx_id)
    notify_payment(payment)
    return HttpResponse("Notification for transaction %s received with status %s" % (tx.id, tx.status))


def notify_payment(payment):
    invoice = payment.invoice
    member = invoice.member
    service = get_service_instance()
    config = service.config

    invoicing_config = get_invoicing_config_instance()
    try:
        invoice_pdf_file = generate_pdf_invoice(invoicing_config, invoice)
    except:
        invoice_pdf_file = None

    if member.email:
        invoice_url = service.url + reverse('billing:invoice_detail', args=(invoice.id,))
        subject, message, sms_text = get_payment_confirmation_message(payment, member)
        html_content = get_mail_content(subject, message, template_name='billing/mails/notice.html',
                                        extra_context={'member_name': member.first_name, 'invoice': invoice,
                                                       'cta': _("View invoice"), 'invoice_url': invoice_url})
        sender = '%s <no-reply@%s>' % (config.company_name, service.domain)
        msg = XEmailMessage(subject, html_content, sender, [member.email])
        if invoice_pdf_file:
            msg.attach_file(invoice_pdf_file)
        msg.content_subtype = "html"
        Thread(target=lambda m: m.send(), args=(msg,)).start()


def process_yup_app_payment(request, *args, **kwargs):
    api_key = request.GET.get('api_key')
    if api_key != getattr(settings, 'YUP_APP_KEY') and api_key != getattr(settings, 'YUP_APP_TEST_KEY'):
        return HttpResponse(json.dumps({"error": "Invalid API Signature"}))
    form = YUPCallbackForm(request.GET)
    if form.is_valid():
        operator_tx_id = form.cleaned_data['transaction_id']
        invoice_id = form.cleaned_data['invoice_id']
        amount = form.cleaned_data['amount']
        try:
            invoice = Invoice.objects.get(pk=invoice_id)
            if api_key == getattr(settings, 'YUP_APP_KEY'):
                invoice.status = Invoice.PAID
                invoice.save()
                payment = Payment.objects.create(invoice=invoice, method=YUP_APP, amount=amount,
                                                 processor_tx_id=operator_tx_id)
                try:
                    notify_payment(payment)
                except:
                    pass
            else:
                payment = Payment(id=str(ObjectId()))
            response = {'success': True, 'payment_id': payment.id}
        except Invoice.DoesNotExist:
            response = {"error": "Invoice %s not found" % invoice_id}
    else:
        response = {'error': 'One or more parameters not found in your request'}
    return HttpResponse(json.dumps(response), 'content-type: text/json')
