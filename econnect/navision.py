# -*- coding: utf-8 -*-
import json
import logging
import math
from datetime import datetime, timedelta
from threading import Thread

import requests
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.translation import ugettext as _
from ikwen.accesscontrol.backends import UMBRELLA
from ikwen.billing.invoicing.views import PaymentList, InvoiceList
from ikwen.core.generic import HybridListView, ChangeObjectBase

from ikwen.core.models import Country, Service
from ikwen.core.utils import get_mail_content, get_service_instance
from ikwen.accesscontrol.models import Member
from ikwen.billing.models import Invoice, InvoiceItem, InvoiceEntry, MoMoTransaction
from ikwen.billing.utils import get_invoice_generated_message, generate_pdf_invoice, get_invoicing_config_instance, \
    get_payment_model

from econnect.admin import IncompleteClientAdmin
from econnect.models import Profile, Subscription, IncompleteClient

Payment = get_payment_model()

logger = logging.getLogger('ikwen')

if getattr(settings, 'DEBUG', False):
    NAVISION_BASE_URL = "https://api.businesscentral.dynamics.com/v2.0/7d95b71e-1303-4858-a5b8-d3918d7b4b40" \
                        "/Sandbox/ODataV4/Company('TEST CREOLINK - NEW')"
    NAVISION_AUTH_HEADER = 'YmNkZXY6d0NodlA2d0wzWFpCSHBlQ2FveWtyVlJUbmdIek92eHFNaGNqZVNUY0tuOD0='
else:
    NAVISION_BASE_URL = "https://api.businesscentral.dynamics.com/v2.0/7d95b71e-1303-4858-a5b8-d3918d7b4b40" \
                        "/sandbox-production/ODataV4/Company('CREOLINK%20COMMUNICATIONS')"
    NAVISION_AUTH_HEADER = 'YmNkZXY6OVdxTUphZUh5dCtrTnNtRVo1RXFHNHpRRDJyWEtrZUJhcnFyOVo3azIzTT0='


def import_clients(start=0, length=1000, max_items=None, debug=False):
    headers = {'Authorization': 'Basic ' + NAVISION_AUTH_HEADER}
    endpoint = NAVISION_BASE_URL + "/CustomerCard"
    endpoint += "?$select=No,Name,E_Mail,Phone_No,City&$top=%d&$skip=" % length
    now = datetime.now()
    start_date = now - timedelta(days=90)
    if max_items:
        max_counter = max_items / length
        if max_items % length != 0:
            max_counter += 1
    else:
        max_counter = 1e10  # Very large number to simulate infinite
    n = start / length - 1
    result = []
    while n < max_counter:
        n += 1
        skip = n * length
        endpoint += str(skip)
        try:
            r = requests.get(endpoint, headers=headers, verify=False, timeout=300)
            resp = r.json()
            assets = resp['value']
            if len(assets) == 0:
                break
            try:
                cameroon = Country.objects.get(iso2__iexact='cm')
            except:
                cameroon = Country.objects.create(name='Cameroon', iso2='CM', iso3='CMR')
            for val in assets:
                client_code = val['No']
                city = val['City']
                name = val['Name']
                tokens = name.split(' ')
                first_name = tokens[0]
                last_name = ' '.join(tokens[1:]) if len(tokens) > 1 else ''
                password = client_code
                email = val['E_Mail'].replace('-', '').replace(' ', '').split('/')[0]
                phone = val['Phone_No'].replace('-', '').replace(' ', '').split('/')[0]
                if not email:
                    try:
                        IncompleteClient.objects.get(code=client_code)
                    except:
                        IncompleteClient.objects.create(code=client_code, name=name, phone=phone, city=city, email='')
                    continue
                member1, member2 = None, None
                try:
                    member1 = Member.objects.get(email=email)
                except Member.DoesNotExist:
                    pass
                if phone:
                    try:
                        member2 = Member.objects.get(phone=phone)
                    except Member.DoesNotExist:
                        if member1:
                            member1.phone = phone
                            member1.save()
                if member1 and member2 and member1 != member2:
                    # Send notice of inconsistent data for manual fix
                    continue
                if not member1 and member2:
                    member2.email = email
                    member2.save()
                member1 = member2
                try:
                    profile = Profile.objects.get(code=client_code)
                    if profile.member != member1:
                        # Send notice of inconsistency for manual fix
                        continue
                except Profile.DoesNotExist:
                    if not member1:
                        member1 = Member.objects \
                            .create_user(email, password, first_name=first_name,
                                         last_name=last_name, email=email, phone=phone)
                    # Set code_update_count to 4 to prevent manual update by customer, as 3 is the max allowed
                    Profile.objects.create(member=member1, code=client_code, country=cameroon, city=city,
                                           code_update_count=4)
                invoice_list, pending_count = pull_invoices(member1, client_code, start_date=start_date, end_date=now,
                                                            send_mail=False, dry_run=False, debug=debug)
                if debug:
                    invoices = ["%s:%s" % (inv.number, inv.amount) for inv in invoice_list]
                    item = {
                        'Member': member1.username + ':' + client_code,
                        'Invoices': invoices
                    }
                    result.append(item)
        except:
            logger.error("Failed to import clients data", exc_info=True)
            break
    return result


def pull_invoices(member=None, client_code=None, start_date=None, end_date=None, status=None,
                  send_mail=True, dry_run=True, debug=False):
    headers = {'Authorization': 'Basic ' + NAVISION_AUTH_HEADER}
    endpoint = NAVISION_BASE_URL + "/CustomerLedgerEntries"
    endpoint += "?$filter=Document_Type eq 'Invoice'"
    pending_count = 0  # The number of pending invoices pulled
    if not (member or client_code):
        raise ValueError("member or client_code is expected.")
    if not member:
        try:
            member = Profile.objects.get(code=client_code).member
        except Profile.DoesNotExist:
            return [], pending_count
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
            amount = int(math.ceil(amount))
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
            try:
                Invoice.objects.get(number=number)
                continue
            except Invoice.DoesNotExist:
                invoice = Invoice(subscription=subscription, member=member, number=number, amount=amount,
                                  months_count=1, due_date=due_date.date(), date_issued=date_issued.date(),
                                  is_one_off=True, entries=entries, status=status)
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
                recipient_list = [member.email]
                msg = EmailMessage(subject, html_content, sender, recipient_list)
                if debug:
                    msg.bcc = getattr(settings, 'ADMINS', [])
                if invoice_pdf_file:
                    msg.attach_file(invoice_pdf_file, mimetype='application/pdf')
                msg.content_subtype = "html"
                invoice.reminders_sent += 1
                invoice.last_reminder = datetime.now()
                invoice.save()
                try:
                    if msg.send():
                        logger.debug("1st Reminder for Invoice %s sent to %s" % (number, member.email))
                    else:
                        logger.error("Invoice #%s generated but mail not sent to %s" % (number, member.email),
                                     exc_info=True)
                except:
                    logger.error("Connexion error on Invoice #%s to %s" % (number, member.email), exc_info=True)
    except:
        logger.error("Failed to import clients data", exc_info=True)
    return invoice_list, pending_count


def extract(request, *args, **kwargs):
    api_key = request.GET.get('api_key')
    if api_key != getattr(settings, 'YUP_APP_KEY') and api_key != getattr(settings, 'YUP_APP_TEST_KEY'):
        return HttpResponse(json.dumps({"error": "Invalid API Signature"}), content_type='application/json')
    client_code = request.GET['client_code']
    pull_invoices(client_code=client_code, status=Invoice.PENDING, dry_run=False)
    subscription_list = list(Subscription.objects.filter(reference_id=client_code))
    response = []
    for invoice in Invoice.objects.filter(subscription__in=subscription_list).order_by('due_date'):
        response.append({
            'id': invoice.id,
            'number': invoice.number,
            'amount': invoice.amount,
            'date_issued': invoice.date_issued.strftime("%Y-%m-%d"),
            'due_date': invoice.due_date.strftime("%Y-%m-%d")
        })
    return HttpResponse(json.dumps(response), content_type='application/json')


class IncompleteClientList(HybridListView):
    queryset = IncompleteClient.objects.filter(email='')
    change_object_url_name = 'change_incompleteclient'
    show_add = False


class ChangeIncompleteClient(ChangeObjectBase):
    object_list_url = 'incompleteclient_list'
    model = IncompleteClient
    model_admin = IncompleteClientAdmin

    def get(self, request, *args, **kwargs):
        obj = self.get_object(**kwargs)
        if obj:
            obj.last_access = datetime.now()
            obj.save()
        return super(ChangeIncompleteClient, self).get(request, *args, **kwargs)

    def after_save(self, request, obj, *args, **kwargs):
        if obj.email:
            name = obj.name
            tokens = name.split(' ')
            first_name = tokens[0]
            last_name = ' '.join(tokens[1:]) if len(tokens) > 1 else ''
            now = datetime.now()
            start_date = now - timedelta(days=90)
            try:
                cameroon = Country.objects.get(iso2__iexact='cm')
            except:
                cameroon = Country.objects.create(name='Cameroon', iso2='CM', iso3='CMR')
            try:
                Profile.objects.get(code=obj.code)
            except Profile.DoesNotExist:
                member = Member.objects.create_user(obj.email, obj.code, first_name=first_name,
                                 last_name=last_name, email=obj.email, phone=obj.phone)
                # Set code_update_count to 4 to prevent manual update by customer, as 3 is the max allowed
                Profile.objects.create(member=member, code=obj.code, country=cameroon, city=obj.city,
                                       code_update_count=4)
                Thread(target=pull_invoices, args=(member, obj.code, start_date, now, None, False, False)).start()


class CustomInvoiceList(InvoiceList):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated() and not request.user.email_verified:
            email_verified = Member.objects.using(UMBRELLA).get(pk=request.user.id).email_verified
            if email_verified:
                # If email already verified in umbrella, report it to local database
                member = request.user
                member.email_verified = True
                member.propagate_changes()
                return super(CustomInvoiceList, self).get(request, *args, **kwargs)
            referrer = request.META.get('HTTP_REFERER', '/')
            next_url = reverse('ikwen:email_confirmation') + '?next=' + referrer
            return HttpResponseRedirect(next_url)
        return super(CustomInvoiceList, self).get(request, *args, **kwargs)


class CustomPaymentList(PaymentList):
    def export(self, queryset):
        now = datetime.now()
        filename = 'CREOLINK.COM_Payments_' + now.strftime('%y-%m-%d %H:%M')
        export_data = []
        for payment in queryset:
            invoice = payment.invoice
            member = invoice.member
            profile = Profile.objects.get(member=member)
            try:
                tx = MoMoTransaction.objects.using('wallets').get(processor_tx_id=payment.processor_tx_id)
                method = tx.wallet
            except:
                method = payment.method
            obj = {
                "Posting_Date": payment.created_on.strftime('%Y-%m-%d'),
                "Account_No": profile.code,
                "Payment_Method_Code19704": method,
                "Credit_Amount97735": payment.amount,
                "Applies_to_Doc_Type": "Invoice",
                "Applies_to_Doc_No": invoice.number
            }
            export_data.append(json.dumps(obj))
        export_data = ',\n'.join(export_data)
        try:
            response = HttpResponse(export_data, content_type='application/octet-stream')
        except TypeError:
            response = HttpResponse(export_data, mimetype='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename=%s' % filename
        return response


def export_payments(request, *args, **kwargs):
    logger.debug("Accessing payments export from %s; User-Agent: %s" % (request.META['REMOTE_ADDR'], request.user_agent))
    api_signature = request.GET.get('api_signature')
    try:
        Service.objects.get(api_signature=api_signature)
    except Service.DoesNotExist:
        logger.error("Accessing payments export failed with signature: %s" % api_signature)
        return HttpResponse(json.dumps({'error': 'Invalid API Signature'}), content_type='application/json')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    queryset = Payment.objects.filter(created_on__range=(start_date, end_date))
    export_data = []
    try:
        for payment in queryset:
            invoice = payment.invoice
            member = invoice.member
            try:
                profile = Profile.objects.get(member=member)
                client_code = profile.code
            except:
                client_code = ''
            try:
                tx = MoMoTransaction.objects.using('wallets').get(processor_tx_id=payment.processor_tx_id)
                method = tx.wallet
            except:
                method = payment.method
            obj = {
                "Posting_Date": payment.created_on.strftime('%Y-%m-%d'),
                "Posting_Time": payment.created_on.strftime('%H:%M:%S'),
                "Account_No": client_code,
                "Payment_Method_Code19704": method,
                "Credit_Amount97735": payment.amount,
                "Applies_to_Doc_Type": "Invoice",
                "Applies_to_Doc_No": invoice.number
            }
            export_data.append(obj)
        logger.debug("Successfully exported %s payments [%s - %s]:" % (len(export_data), start_date, end_date))
        return HttpResponse(json.dumps(export_data), content_type='application/json')
    except:
        notice = "Accessing payments export failed with signature: %s" % api_signature
        logger.error(notice, exc_info=True)
        return HttpResponse(json.dumps({'error': notice}), content_type='application/json')


def test_navision_import(request, *args, **kwargs):
    start = request.GET.get('start', 0)
    length = request.GET.get('length', 10)
    max_items = request.GET.get('max', 10)
    debug = request.GET.get('debug', False)
    result = import_clients(int(start), int(length), int(max_items), debug=debug)
    return HttpResponse(json.dumps(result))


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
