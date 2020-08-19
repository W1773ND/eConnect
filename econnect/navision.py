# -*- coding: utf-8 -*-
import logging
from datetime import datetime

import requests
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _

from ikwen.core.models import Country, Service
from ikwen.core.utils import get_mail_content, get_service_instance
from ikwen.accesscontrol.models import Member
from ikwen.billing.models import Invoice, InvoiceItem, InvoiceEntry
from ikwen.billing.utils import get_invoice_generated_message, generate_pdf_invoice, get_invoicing_config_instance

from econnect.models import Profile, Subscription

logger = logging.getLogger('ikwen')


def import_clients():
    endpoint = "https://api.businesscentral.dynamics.com/v2.0/7d95b71e-1303-4858-a5b8-d3918d7b4b40/Sandbox/ODataV4" \
               "/Company('TEST%20CREOLINK%20-%20NEW')/PostedServiceInvoice"
    headers = {'Authorization': 'Basic ' + getattr(settings, 'NAVISION_AUTH_HEADER')}

    try:
        r = requests.get(endpoint, headers=headers, verify=False, timeout=300)
        resp = r.json()
        assets = resp['value']
        try:
            cameroon = Country.objects.get(iso2__iexact='cm')
        except:
            cameroon = Country.objects.create(name='Cameroon', iso2='CM', iso3='CMR')
        for val in assets:
            client_code = val['Customer_No']
            city = val['City']
            tokens = val['Name'].split(' ')
            first_name = tokens[0]
            last_name = ' '.join(tokens[1:]) if len(tokens) > 1 else ''
            password = client_code
            try:
                Profile.objects.get(code=client_code)
            except Profile.DoesNotExist:
                member = Member.objects.create_user(client_code, password, first_name=first_name, last_name=last_name, is_ghost=True)
                Profile.objects.create(member=member, code=client_code, country=cameroon, city=city)
    except:
        logger.error("Failed to import clients data", exc_info=True)


def pull_invoices(member, client_code=None, start_date=None, end_date=None, status=None,
                  send_mail=True, dry_run=True):
    endpoint = "https://api.businesscentral.dynamics.com/v2.0/7d95b71e-1303-4858-a5b8-d3918d7b4b40/Sandbox/ODataV4" \
               "/Company('TEST CREOLINK - NEW')/CustomerLedgerEntries?$filter=Document_Type eq 'Invoice'"
    pending_count = 0  # The number of pending invoices pulled
    if not client_code:
        try:
            client_code = Profile.objects.get(member=member).code
        except Profile.DoesNotExist:
            return [], pending_count

    endpoint += " and Customer_No eq '%s'" % client_code.strip().upper()

    if start_date and end_date:
        start = start_date.strftime('%Y-%m-%d')
        end = end_date.strftime('%Y-%m-%d')
        endpoint += " and Posting_Date gt %s and Posting_Date lt %s" % (start, end)
    if status == Invoice.PENDING:
        endpoint += " and Open eq true"
    elif status == Invoice.PAID:
        endpoint += " and Open eq false"
    headers = {'Authorization': 'Basic ' + getattr(settings, 'NAVISION_AUTH_HEADER')}
    weblet = get_service_instance()
    config = weblet.config
    invoicing_config = get_invoicing_config_instance()
    invoice_list = []
    try:
        r = requests.get(endpoint, headers=headers, verify=False, timeout=300)
        resp = r.json()
        assets = resp['value']
        for val in assets:
            monthly_cost = val['Sales_LCY']
            amount = val['Remaining_Amt_LCY']
            number = val['Document_No']
            # number = val['Description']
            due_date_str = val['Due_Date']
            date_issued = datetime.strptime(val['Posting_Date'], '%Y-%m-%d')
            if val['Open']:
                status = Invoice.PENDING
                pending_count += 1
            else:
                status = Invoice.PAID

            item = InvoiceItem(label='Internet & TV Access', amount=amount)
            entries = [InvoiceEntry(item=item, short_description=client_code,
                                    quantity=1, quantity_unit='', total=amount)]
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            try:
                subscription = Subscription.objects.get(reference_id=client_code)
                if subscription.member != member:
                    return [], 0  # Attempt to use a client_code already in use
            except Subscription.DoesNotExist:
                subscription = Subscription(member=member, monthly_cost=monthly_cost, details='',
                                            status=Subscription.ACTIVE, billing_cycle=Service.MONTHLY,
                                            reference_id=client_code, expiry=due_date.date())
                if not dry_run:
                    subscription.save()
            invoice = Invoice(subscription=subscription, member=member, number=number, amount=amount,
                              months_count=1, due_date=due_date.date(), date_issued=date_issued.date(), is_one_off=True,
                              entries=entries, status=status)
            invoice_pdf_file = None
            if not dry_run:
                invoice.save()
                try:
                    invoice_pdf_file = generate_pdf_invoice(invoicing_config, invoice)
                except:
                    pass
            invoice_list.append(invoice)
            subject, message, sms_text = get_invoice_generated_message(invoice)

            if invoice.status == Invoice.PENDING:
                send_mail = True

            if not dry_run and send_mail and member.email:
                invoice_url = 'http://creolink.com' + reverse('billing:invoice_detail', args=(invoice.id,))
                html_content = get_mail_content(subject, message, template_name='billing/mails/notice.html',
                                                extra_context={'member_name': member.first_name, 'cta': _("Pay now"),
                                                               'invoice': invoice, 'invoice_url': invoice_url,
                                                               'currency': 'XAF'})
                # Sender is simulated as being no-reply@company_name_slug.com to avoid the mail
                # to be delivered to Spams because of origin check.
                sender = '%s <no-reply@%s>' % (config.company_name, weblet.domain)
                msg = EmailMessage(subject, html_content, sender, [member.email])
                if invoice_pdf_file:
                    msg.attach_file(invoice_pdf_file, mimetype='application/pdf')
                msg.content_subtype = "html"
                invoice.reminders_sent += 1
                invoice.last_reminder = datetime.now()
                invoice.save()
                try:
                    if msg.send():
                        logger.debug("1st Invoice reminder for sent to %s" % member.email)
                    else:
                        logger.error(u"Invoice #%s generated but mail not sent to %s" % (number, member.email),
                                     exc_info=True)
                except:
                    logger.error(u"Connexion error on Invoice #%s to %s" % (number, member.email), exc_info=True)
    except:
        logger.error("Failed to import clients data", exc_info=True)
    return invoice_list, pending_count


def test_invoice_generation():
    from ikwen.billing.models import Invoice
    start = datetime(2020, 1, 1)
    end = datetime(2020, 8, 18)
    m = Member.objects.get(username='w177')
    i = Invoice.objects.get(number='FE0000002048')
    i.delete()
    pull_invoices(m, 'C010320', start, end)
    # ic = get_invoicing_config_instance()
    # pdf = generate_pdf_invoice(ic, i)
