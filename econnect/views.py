# -*- coding: utf-8 -*-
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from ikwen.accesscontrol.utils import VerifiedEmailTemplateView

from econnect.navision import pull_invoices

__author__ = 'W1773ND (wilfriedwillend@gmail.com)'

from calendar import monthrange
from datetime import datetime, timedelta

import requests
import urlparse
import os
import time
import json

from threading import Thread

from currencies.models import Currency

from django.conf import settings
from django.http import HttpResponseRedirect, Http404, HttpResponse, request
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.db import transaction
from django.db.models import Q
from django.core import mail
from django.views.generic import TemplateView
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.core.exceptions import MultipleObjectsReturned
from django.template.defaultfilters import slugify
from django.utils.translation import gettext as _, get_language

from ikwen.conf import settings as ikwen_settings
from ikwen.conf.settings import WALLETS_DB_ALIAS
from ikwen.accesscontrol.backends import UMBRELLA
from ikwen.accesscontrol.models import Member, DEFAULT_GHOST_PWD
from ikwen.core.models import Service, Country
from ikwen.core.views import HybridListView, ChangeObjectBase
from ikwen.core.constants import PENDING, PENDING_FOR_PAYMENT, STARTED
from ikwen.core.utils import get_model_admin_instance, get_service_instance, get_item_list, get_model, get_mail_content, \
    XEmailMessage
from ikwen.billing.models import Invoice, InvoiceItem, InvoiceEntry
from ikwen.billing.utils import get_next_invoice_number
from ikwen.revival.models import ProfileTag, MemberProfile

from echo.views import CampaignBaseView, File, batch_send_mail
from echo.models import MailCampaign, Balance
from echo.admin import MailCampaignAdmin

from econnect.admin import ProductAdmin, PackageAdmin, EquipmentAdmin, ExtraAdmin, FaqAdmin, AdvertisementAdmin, \
    SiteAdmin, ProfileAdmin
from econnect.forms import OrderForm
from econnect.models import ADMIN_EMAIL, Subscription, Order, CustomerRequest, Product, Package, Equipment, \
    EquipmentOrderEntry, \
    Extra, RENTAL, PURCHASE, REPORTED, FINISHED, CANCELED, DEVICE_ID, \
    NUMERIHOME, NUMERIHOTEL, HOME, OFFICE, CORPORATE, ANALOG, DIGITAL, ECONNECT, Faq, Advertisement, Site, Profile, \
    IncompleteClient, Interaction

import logging

logger = logging.getLogger('ikwen')


def last_day_of_the_month(date):
    return date.replace(day=monthrange(date.year, date.month)[1])


def set_prospect_on_creolink_maps(order):
    """
    Issue a request to CREOLINK MAPS to add this Customer so
    that he becomes visible on the Map as a Prospect
    """
    endpoint = getattr(settings, "CREOLINK_MAPS_URL") + 'save_prospect'
    payload = {
        'api_key': getattr(settings, 'CREOLINK_MAPS_API_KEY'),
        'client_name': order.member.full_name,
        'lat': order.location_lat,
        'lng': order.location_lng,
        'order_id': order.id
    }
    resp = requests.get(endpoint, params=payload)
    data = resp.json()
    order.maps_id = data['device_id']
    order.save()


class InteractiveList(HybridListView):

    def get_context_data(self, **kwargs):
        context = super(InteractiveList, self).get_context_data(**kwargs)
        context['interaction_types'] = Interaction.INTERACTION_TYPES
        return context

    def render_to_response(self, context, **response_kwargs):
        fmt = self.request.GET.get('format')
        member = self.request.user
        queryset = context['queryset']
        queryset = queryset.order_by(*self.ordering)
        if self.request.GET.get('action') == 'export':
            return self.export(queryset)
        paginator = Paginator(queryset, self.page_size)
        page = self.request.GET.get('page')
        try:
            objects_page = paginator.page(page)
            page = int(page)
        except PageNotAnInteger:
            page = 1
            objects_page = paginator.page(1)
        except EmptyPage:
            page = paginator.num_pages
            objects_page = paginator.page(paginator.num_pages)
        context['q'] = self.request.GET.get('q')
        object_list = []
        for obj in objects_page.object_list:
            # Ordering by -is_main causes the main to appear first
            all_count = Interaction.objects.filter(object_id=obj.id).count()
            viewed_count = Interaction.objects.raw_query({
                'viewed_by': {'$elemMatch': {'$eq': member.id}}
            }).filter(object_id=obj.id).count()
            new_interaction_count = all_count - viewed_count
            obj.new_interaction_count = new_interaction_count
            object_list.append(obj)
        context['objects_page_list'] = object_list
        max_visible_page_count = context['max_visible_page_count']
        min_page = page - (page % max_visible_page_count)
        if min_page < max_visible_page_count:
            min_page += 1
        max_page = min(min_page + max_visible_page_count, paginator.num_pages)
        if page == paginator.num_pages:
            min_page = page - max_visible_page_count
        context['page_range'] = range(min_page, max_page + 1)
        context['max_page'] = max_page
        context['has_image'] = self.get_has_image(queryset)
        if fmt == 'html_results':
            return render(self.request, self.html_results_template_name, context)
        else:
            return super(InteractiveList, self).render_to_response(context, **response_kwargs)

    def add_interaction(self, request, *args, **kwargs):
        type = request.GET['type']
        object_id = request.GET['object_id']
        summary = request.GET.get('summary')
        response = request.GET.get('response')
        next_rdv = request.GET.get('next_rdv')
        Interaction.objects.create(member=request.user, type=type, object_id=object_id,
                                   summary=summary, response=response, next_rdv=next_rdv)
        return HttpResponse(json.dumps({'success': True}), content_type='application/json')

    def list_interactions(self, request, *args, **kwargs):
        member = request.user
        object_id = request.GET['object_id']
        tokens = request.GET['model'].split('.')
        model = get_model(tokens[0], tokens[1])
        obj = model.objects.get(pk=object_id)
        interaction_list = []
        for elt in obj.interaction_set:
            if member.id not in elt.viewed_by:
                elt.viewed_by.append(member.id)
                elt.save()
            interaction_list.append(elt.to_dict())
        return HttpResponse(json.dumps(interaction_list), content_type='application/json')


class PostView(TemplateView):
    model = None

    def post(self, request, *args, **kwargs):
        form = OrderForm(request.POST)
        equipment_order_entry_list = []
        extra_list = []
        if form.is_valid():
            order_id = request.POST.get('order_id')
            product_id = form.cleaned_data['product_id']
            customer_id = form.cleaned_data['customer_id']
            customer_lat = form.cleaned_data['customer_lat']
            customer_lng = form.cleaned_data['customer_lng']
            formatted_address = form.cleaned_data['formatted_address']
            pack_id = form.cleaned_data['pack_id']
            equipment_entry_list = request.POST['equipment'].strip(";").split(";")
            extra_id_list = request.POST.get('extra').strip(";").split(";")
            optional_tv = request.POST.get('optional_tv')
            product = get_object_or_404(Product, pk=product_id)
            member = get_object_or_404(Member, pk=customer_id)
            package = get_object_or_404(Package, pk=pack_id)
            order_cost = product.install_cost
            for equipment_entry in equipment_entry_list:
                tokens = equipment_entry.split("|")
                equipment = get_object_or_404(Equipment, pk=tokens[0])
                if tokens[1] == RENTAL:
                    is_rent = True
                    cost = equipment.rent_cost
                    order_cost += cost
                else:
                    is_rent = False
                    cost = equipment.purchase_cost
                    order_cost += cost
                equipment_order_entry = EquipmentOrderEntry(equipment=equipment, cost=cost, is_rent=is_rent)
                equipment_order_entry_list.append(equipment_order_entry)
            if extra_id_list != [u'']:
                for extra_id in extra_id_list:
                    extra = get_object_or_404(Extra, pk=extra_id)
                    extra_list.append(extra)
                    order_cost += extra.cost
            if optional_tv:
                optional_tv = int(optional_tv)
                optional_tv_cost = optional_tv * package.optional_target_cost
                order_cost += optional_tv_cost
            else:
                optional_tv = None
            order_cost += package.cost
            if order_id:
                order = get_object_or_404(Order, pk=order_id)
                order.package = package
                order.extra_list = extra_list
                order.optional_tv = optional_tv
                order.equipment_order_entry_list = equipment_order_entry_list
                order.location_lat = customer_lat
                order.location_lng = customer_lng
                order.formatted_address = formatted_address
                order.status = STARTED
                order.cost = order_cost

            else:
                order = Order(member=member, package=package, extra_list=extra_list, optional_tv=optional_tv,
                              equipment_order_entry_list=equipment_order_entry_list, location_lat=customer_lat,
                              location_lng=customer_lng, formatted_address=formatted_address, cost=order_cost)
            order.save()
            url = reverse('econnect:order_confirm')
            url += '?order_id=' + order.id
            return HttpResponseRedirect(url)
        else:
            return render(request, self.template_name, {'form': form})


class Maps(PostView):
    template_name = 'econnect/maps.html'

    def get_context_data(self, **kwargs):
        context = super(Maps, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        equipment_order_entry_list = []
        extra_id_list = []
        if order_id:
            order = get_object_or_404(Order, pk=order_id)
            for equipment_order_entry in order.equipment_order_entry_list:
                equipment_order_entry_id = equipment_order_entry.equipment_id
                if equipment_order_entry.is_rent:
                    equipment_order_entry_id += '|' + RENTAL
                else:
                    equipment_order_entry_id += '|' + PURCHASE
                equipment_order_entry_list.append(equipment_order_entry_id)
            equipment_order_entry = ';'.join(equipment_order_entry_list)
            for extra in order.extra_list:
                extra_id = extra.id
                extra_id_list.append(extra_id)
            extra = ';'.join(extra_id_list)
            context['equipment_order_entry'] = equipment_order_entry
            context['extra'] = extra
            context['order'] = order
        return context


class OrderConfirm(TemplateView):
    template_name = 'econnect/order_confirm.html'

    def get_context_data(self, **kwargs):
        context = super(OrderConfirm, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        if order_id:
            while True:
                try:
                    order = Order.objects.get(pk=order_id)
                    product = order.package.product
                    context['order'] = order
                    context['product_url'] = reverse('econnect:' + product.slug) + '-pricing?order_id=' + order.id
                    break
                except Order.DoesNotExist:
                    time.sleep(0.5)
        return context

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == 'confirm_order':
            return self.confirm_order(request)
        return super(OrderConfirm, self).get(request, *args, **kwargs)

    @staticmethod
    def confirm_order(request):
        order_id = request.GET['order_id']
        order = get_object_or_404(Order, id=order_id)
        order.status = PENDING
        order.tags = order.member.full_name + ' ' + order.member.email
        order.save()
        member = order.member
        member_fullname = member.full_name if not member.is_ghost else _('Customer')
        product_name = order.package.product.name
        package_name = order.package.name
        label = product_name + ' [' + package_name + ']'
        service = get_service_instance()
        config = service.config
        notify_email = [email.strip() for email in config.notification_email.split(',')]
        admin_url = service.url + reverse('pending_order')
        Thread(target=set_prospect_on_creolink_maps, args=(order, )).start()
        try:
            subject = _("New order issued on CREOLINK.COM !")
            html_content = get_mail_content(subject, template_name='econnect/mails/order_submitted.html',
                                            extra_context={'order_label': label,
                                                           'member_fullname': member_fullname,
                                                           'admin_url': admin_url})
            sender = 'Creolink Communications <no-reply@creolink.com>'
            msg = XEmailMessage(subject, html_content, sender, notify_email)
            msg.content_subtype = "html"
            Thread(target=lambda m: m.send(), args=(msg,)).start()
        except:
            logger.error("Mail sending failed", exc_info=True)
        response = {"success": True}
        return HttpResponse(json.dumps(response), 'content-type: text/json')


class PendingStatusListFilter(object):
    title = _('Status')
    parameter_name = 'status'

    def lookups(self):
        choices = [
            (STARTED, _('Started')),
            (PENDING, _('Pending')),
            (PENDING_FOR_PAYMENT, _('Pending for payment'))
        ]
        return choices

    def queryset(self, request, queryset):
        value = request.GET.get(self.parameter_name)
        if value:
            return queryset.filter(status=value)
        return queryset


class PendingOrderList(InteractiveList):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/admin/snippets/order_list_results.html'
    embed_doc_template_name = 'econnect/admin/snippets/order_list_results.html'
    queryset = Order.objects.exclude(status__in=[REPORTED, Invoice.PAID, FINISHED, CANCELED])
    search_field = 'tags'
    list_filter = (
        PendingStatusListFilter,
        ('created_on', _('Date'))
    )
    context_object_name = 'order'

    @staticmethod
    def set_equipment(request):
        order_id = request.GET['order_id']
        order = get_object_or_404(Order, id=order_id)
        set_prospect_on_creolink_maps(order)
        response = {"success": True}
        return HttpResponse(json.dumps(response), 'content-type: text/json')

    @staticmethod
    def accept_order(request):
        order_id = request.GET['order_id']
        order = get_object_or_404(Order, id=order_id)
        order.status = PENDING_FOR_PAYMENT
        order.save()
        install_cost = order.package.product.install_cost
        amount = order.cost - install_cost
        member = order.member
        member_lastname = member.last_name if not member.is_ghost else _('Customer')
        service = get_service_instance()
        config = service.config
        number = get_next_invoice_number()
        product_name = order.package.product.name
        package_name = order.package.name
        label = product_name + ' [' + package_name + ']'
        order_location = order.formatted_address

        item1 = InvoiceItem(label='Installation', amount=install_cost)
        entry1 = InvoiceEntry(item=item1, quantity=1, quantity_unit='', total=install_cost)
        item2 = InvoiceItem(label=label, amount=amount)
        entry2 = InvoiceEntry(item=item2, short_description='For ' + member.full_name, quantity=1, total=amount)

        entries = [entry1, entry2]
        for elt in order.equipment_order_entry_list:
            item = InvoiceItem(label=elt.equipment.name, amount=elt.cost)
            short_description = _("Rental") if elt.is_rent else _("Purchase")
            entry = InvoiceEntry(item=item, short_description=short_description, quantity=1, total=elt.cost)
            entries.append(entry)
        for extra in order.extra_list:
            item = InvoiceItem(label=extra.name, amount=extra.cost)
            entry = InvoiceEntry(item=item, quantity=1, total=extra.cost)
            entries.append(entry)

        due_date = datetime.now() + timedelta(days=config.payment_delay)
        subscription = Subscription.objects.create(member=member, product=order.package, monthly_cost=amount,
                                                   billing_cycle=Service.MONTHLY, details='', order=order)
        invoice = Invoice.objects.create(subscription=subscription, member=member, number=number, amount=order.cost,
                                         months_count=1, due_date=due_date.date(), is_one_off=True, entries=entries)
        Interaction.objects.create(member=request.user, type=_("Handover"), object_id=order.id,
                                   summary=_("Order verified and accepted"))
        try:
            subject = _("We are ready to come and install your service.")
            invoice_url = service.url + reverse('billing:invoice_detail', args=(invoice.id,))
            html_content = get_mail_content(subject, template_name='econnect/mails/order_accepted.html',
                                            extra_context={'invoice_url': invoice_url,
                                                           'order_label': label,
                                                           'order_location': order_location,
                                                           'member_lastname': member_lastname})
            sender = 'Creolink Communications <no-reply@creolink.com>'
            msg = XEmailMessage(subject, html_content, sender, [member.email], bcc=[ADMIN_EMAIL])
            msg.content_subtype = "html"
            Thread(target=lambda m: m.send(), args=(msg,)).start()
        except:
            logger.error("Mail sending failed", exc_info=True)
            response = {"success": True, "Mail": False}
            return HttpResponse(json.dumps(response), 'content-type: text/json')
        response = {"success": True}
        return HttpResponse(json.dumps(response), 'content-type: text/json')

    @staticmethod
    def report_order(request):
        order_id = request.GET['order_id']
        order = get_object_or_404(Order, id=order_id)
        order.status = REPORTED
        order.save()
        Interaction.objects.create(member=request.user, type=_("Handover"), object_id=order.id,
                                   summary=_("Order checked and reported"))
        member = order.member
        member_lastname = member.last_name if not member.is_ghost else _('Customer')
        my_creolink_url = reverse('my_creolink')
        try:
            subject = _("We will come soon as possible to install your service.")
            html_content = get_mail_content(subject, template_name='econnect/mails/order_reported.html',
                                            extra_context={'my_creolink_url': my_creolink_url,
                                                           'member_lastname': member_lastname})
            sender = 'Creolink Communications <no-reply@creolink.com>'
            msg = XEmailMessage(subject, html_content, sender, [member.email], [ADMIN_EMAIL])
            msg.content_subtype = "html"
            Thread(target=lambda m: m.send(), args=(msg,)).start()
        except:
            logger.error("Mail sending failed", exc_info=True)
            response = {"success": True, "Mail": False}
            return HttpResponse(json.dumps(response), 'content-type: text/json')

        # Update the prospect in Creolink Maps to Reported Prospect.
        # This operation will set a new category on the Prospect object, thus changing its icon
        endpoint = getattr(settings, "CREOLINK_MAPS_URL") + 'update_prospect'
        payload = {
            'api_key': getattr(settings, 'CREOLINK_MAPS_API_KEY'),
            'device_id': order.maps_id
        }
        Thread(target=requests.get, args=(endpoint, payload)).start()

        response = {"success": True}
        return HttpResponse(json.dumps(response), 'content-type: text/json')


class PaidStatusListFilter(object):
    title = _('Status')
    parameter_name = 'status'

    def lookups(self):
        choices = [
            (Invoice.PAID, _('Paid')),
            (FINISHED, _('Processed and archived'))
        ]
        return choices

    def queryset(self, request, queryset):
        value = request.GET.get(self.parameter_name)
        if value:
            return queryset.filter(status=value)
        return queryset


class PaidOrderList(InteractiveList):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/admin/snippets/order_list_results.html'
    queryset = Order.objects.filter(status__in=[Invoice.PAID, FINISHED])
    search_field = 'tags'
    list_filter = (
        PaidStatusListFilter,
        ('created_on', _('Date'))
    )
    context_object_name = 'order'

    @staticmethod
    def terminate_order(request):
        order_id = request.GET['order_id']
        client_code = request.GET['client_code']
        city = request.GET['city']

        order = get_object_or_404(Order, id=order_id)
        member = order.member
        try:
            cameroon = Country.objects.get(iso2__iexact='cm')
        except:
            cameroon = Country.objects.create(name='Cameroon', iso2='CM', iso3='CMR')

        # Check Client code
        client_code = slugify(client_code).replace('-', '').upper()
        try:
            Profile.objects.get(code__iexact=client_code)
            return HttpResponse(json.dumps({'error': _("Client code <strong>%s</strong> already exists" % client_code)}),
                                'content-type: text/json')
        except Profile.DoesNotExist:
            Profile.objects.create(member=member, code=client_code, country=cameroon, city=city, code_update_count=4)

        # Terminate the Order
        order.status = FINISHED
        order.save()

        # Mark the matching subscription as active and create and Profile for MyCreolink to work correctly
        Subscription.objects.filter(order=order).update(status=Subscription.ACTIVE)

        # Automatically create an interaction for that
        Interaction.objects.create(member=request.user, object_id=order_id,
                                   type=Interaction.INTERVENTION, summary=client_code)

        # Prepare and send email
        member_lastname = member.last_name if not member.is_ghost else _('Customer')
        product_name = order.package.product.name
        package_name = order.package.name
        label = product_name + ' [' + package_name + ']'
        order_location = order.formatted_address
        try:
            subject = _("Dear " + member.full_name + ", thanks to business with Creolink Communications.")
            html_content = get_mail_content(subject, template_name='econnect/mails/service_completed.html',
                                            extra_context={'order_label': label,
                                                           'order_location': order_location,
                                                           'member_lastname': member_lastname})
            sender = 'Creolink Communications <no-reply@creolink.com>'
            msg = XEmailMessage(subject, html_content, sender, [member.email], [ADMIN_EMAIL])
            msg.content_subtype = "html"
            Thread(target=lambda m: m.send(), args=(msg,)).start()
        except:
            logger.error("Mail sending failed", exc_info=True)
            response = {"success": True, "Mail": False}
            return HttpResponse(json.dumps(response), 'content-type: text/json')

        # Update the prospect in Creolink Maps to Client with necessary information
        endpoint = getattr(settings, "CREOLINK_MAPS_URL") + 'update_prospect'
        payload = {
            'api_key': getattr(settings, 'CREOLINK_MAPS_API_KEY'),
            'device_id': order.maps_id,
            'client_code': client_code
        }
        Thread(target=requests.get, args=(endpoint, payload)).start()

        response = {"success": True}
        return HttpResponse(json.dumps(response), 'content-type: text/json')


class ReportedOrderList(InteractiveList):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/snippets/order_list_results.html'
    queryset = Order.objects.filter(status=REPORTED)
    search_field = 'tags'
    list_filter = ('created_on',)
    context_object_name = 'order'


class CanceledOrderList(HybridListView):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/snippets/order_list_results.html'
    queryset = Order.objects.filter(status=CANCELED)
    search_field = 'tags'
    list_filter = (('created_on', _("Date")), )
    context_object_name = 'order'


class Admin(TemplateView):
    template_name = 'econnect/admin/admin_home.html'


class Dashboard(TemplateView):
    template_name = 'econnect/admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super(Dashboard, self).get_context_data(**kwargs)
        context['incomplete_client_count'] = IncompleteClient.objects.filter(email='').count()
        return context


class CustomerRequestList(HybridListView):
    template_name = 'econnect/admin/request_list.html'
    html_results_template_name = 'econnect/admin/snippets/request_list_result.html'
    model = CustomerRequest
    queryset = CustomerRequest.objects.using(UMBRELLA).all()
    search_field = 'member'
    context_object_name = 'customerRequest'


class HomeView(TemplateView):
    template_name = 'econnect/homepage.html'

    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)
        lang = get_language()
        product_list = []
        advertisement_list = []
        if Product.objects.filter(lang=lang).count() < Product.objects.filter(lang='en').count():
            lang = 'en'
        for product in Product.objects.filter(lang=lang).exclude(Q(name=NUMERIHOTEL) & Q(name=NUMERIHOME)):
            product_pricing = slugify(product.name) + '-pricing'
            product.url = reverse('econnect:' + product_pricing)
            product_list.append(product)
        try:
            product_numeri_home = Product.objects.get(name=NUMERIHOME, lang=lang)
            product_numeri_hotel = Product.objects.get(name=NUMERIHOTEL, lang=lang)
        except:
            product_numeri_home = get_object_or_404(Product, name=NUMERIHOME, lang='en')
            product_numeri_hotel = get_object_or_404(Product, name=NUMERIHOTEL, lang='en')
        product_numeri_home.slug = slugify(product_numeri_home.name)
        product_numeri_hotel.slug = slugify(product_numeri_hotel.name)
        product_numeri_home.url = reverse('econnect:' + product_numeri_home.slug)
        product_numeri_hotel.url = reverse('econnect:' + product_numeri_hotel.slug)
        if Advertisement.objects.filter(lang=lang).count() < Advertisement.objects.filter(lang='en').count():
            lang = 'en'
        for advertisement in Advertisement.objects.filter(lang=lang):
            advertisement_list.append(advertisement)
        context['product_list'] = product_list
        context['product_numeri_home'] = product_numeri_home
        context['product_numeri_hotel'] = product_numeri_hotel
        context['advertisement_list'] = advertisement_list
        return context

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == 'send_mail_to_visitor':
            return self.send_mail_to_visitor(request)
        return super(HomeView, self).get(request, *args, **kwargs)

    def send_mail_to_visitor(self, request):
        service = get_service_instance()
        config = service.config
        visitor_email = request.GET.get('visitor_email')
        visitor_phone = request.GET.get('visitor_phone')
        next_url = request.GET.get('next', '/')
        if not visitor_email:
            response = {'error': 'No Email found'}
            return HttpResponse(json.dumps(response), 'content-type: text/json')
        try:
            Member.objects.get(email=visitor_email, is_ghost=False)
            next_url = reverse('ikwen:sign_in') + "?next=" + request.META['HTTP_REFERER']
            return HttpResponseRedirect(next_url)
        except MultipleObjectsReturned:
            next_url = reverse('ikwen:sign_in') + "?next=" + request.META['HTTP_REFERER']
            return HttpResponseRedirect(next_url)
        except Member.DoesNotExist:
            username = visitor_email
            try:
                Member.objects.get(username=username, is_ghost=True)
            except Member.DoesNotExist:
                member = Member.objects.create_user(username, DEFAULT_GHOST_PWD, email=visitor_email, phone=visitor_phone, is_ghost=True)
                tag = ECONNECT
                econnect_tag, change = ProfileTag.objects.get_or_create(name=tag, slug=slugify(tag))
                member_profile = MemberProfile.objects.get(member=member)
                member_profile.tag_fk_list = [econnect_tag.id]
                member_profile.save()
                next_url_for_mail = reverse('ikwen:logout') + "?next=" + reverse('ikwen:register')
                try:
                    subject = _("Do more with Creolink Communications !")
                    html_content = get_mail_content(subject,
                                                    template_name='accesscontrol/mails/complete_registration.html',
                                                    extra_context={'member_email': visitor_email,
                                                                   'next_url': next_url_for_mail}, )
                    sender = '%s <no-reply@%s>' % (config.company_name, service.domain)
                    msg = EmailMessage(subject, html_content, sender, [visitor_email], [ADMIN_EMAIL])
                    msg.content_subtype = "html"
                    Thread(target=lambda m: m.send(), args=(msg,)).start()
                except:
                    logger.error("Mail sending failed", exc_info=True)
            if request.user.is_anonymous():
                ghost_member = authenticate(username=visitor_email, password=DEFAULT_GHOST_PWD)
                login(request, ghost_member)
        return HttpResponseRedirect(next_url)


class Numerilink(TemplateView):
    template_name = 'econnect/numerilink_home.html'

    def get_context_data(self, **kwargs):
        context = super(Numerilink, self).get_context_data(**kwargs)
        lang = get_language()
        try:
            product = Product.objects.get(name=NUMERIHOME, lang=lang)
        except:
            product = get_object_or_404(Product, name=NUMERIHOME, lang='en')
        product_pricing = slugify(product.name) + '-pricing'
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        context['product_url'] = reverse('econnect:' + product_pricing)
        return context


class NumerilinkHotel(TemplateView):
    template_name = 'econnect/numerilink_hotel.html'

    def get_context_data(self, **kwargs):
        context = super(NumerilinkHotel, self).get_context_data(**kwargs)
        lang = get_language()
        try:
            product = Product.objects.get(name=NUMERIHOTEL, lang=lang)
        except:
            product = get_object_or_404(Product, name=NUMERIHOTEL, lang='en')
        product_pricing = slugify(product.name) + '-pricing'
        equipment_purchase_cost = 0
        digital_package_list = []
        analog_package_list = []
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        for analog_package in product.package_set.filter(type=ANALOG):
            analog_package_list.append(analog_package)
        for digital_package in product.package_set.filter(type=DIGITAL):
            digital_package_list.append(digital_package)
        context['digital_package_list'] = digital_package_list
        context['analog_package_list'] = analog_package_list
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        context['product_url'] = reverse('econnect:' + product_pricing)
        return context


class Homelink(TemplateView):
    template_name = 'econnect/homelink.html'

    def get_context_data(self, **kwargs):
        context = super(Homelink, self).get_context_data(**kwargs)
        lang = get_language()
        try:
            product = Product.objects.get(name=HOME, lang=lang)
        except:
            product = get_object_or_404(Product, name=HOME, lang='en')
        product_pricing = slugify(product.name) + '-pricing'
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        context['product_url'] = reverse('econnect:' + product_pricing)
        return context


class Officelink(TemplateView):
    template_name = 'econnect/officelink.html'

    def get_context_data(self, **kwargs):
        context = super(Officelink, self).get_context_data(**kwargs)
        lang = get_language()
        try:
            product = Product.objects.get(name=OFFICE, lang=lang)
        except:
            product = get_object_or_404(Product, name=OFFICE, lang='en')
        product_pricing = slugify(product.name) + '-pricing'
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        context['product_url'] = reverse('econnect:' + product_pricing)
        return context


class Corporatelink(TemplateView):
    template_name = 'econnect/corporatelink.html'

    def get_context_data(self, **kwargs):
        context = super(Corporatelink, self).get_context_data(**kwargs)
        lang = get_language()
        try:
            product = Product.objects.get(name=CORPORATE, lang=lang)
        except:
            product = get_object_or_404(Product, name=CORPORATE, lang='en')
        product_pricing = slugify(product.name) + '-pricing'
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        context['product_url'] = reverse('econnect:' + product_pricing)
        return context


class ProductList(HybridListView):
    model = Product
    search_field = 'name'
    ordering = ('order_of_appearance',)


class ChangeProduct(ChangeObjectBase):
    model = Product
    model_admin = ProductAdmin


class PackageList(HybridListView):
    model = Package
    list_filter = ('product',)
    search_field = 'name'
    ordering = ('order_of_appearance',)


class ChangePackage(ChangeObjectBase):
    model = Package
    model_admin = PackageAdmin
    template_name = 'econnect/admin/change_package.html'


class EquipmentList(HybridListView):
    model = Equipment
    list_filter = ('product',)
    search_field = 'name'
    ordering = ('order_of_appearance',)


class ChangeEquipment(ChangeObjectBase):
    model = Equipment
    model_admin = EquipmentAdmin


class ExtraList(HybridListView):
    model = Extra
    list_filter = ('product',)
    search_field = 'name'
    ordering = ('order_of_appearance',)


class ChangeExtra(ChangeObjectBase):
    model = Extra
    model_admin = ExtraAdmin


class FaqList(HybridListView):
    model = Faq
    list_filter = ('product',)
    search_field = 'question'
    ordering = ('order_of_appearance',)


class ChangeFaq(ChangeObjectBase):
    model = Faq
    model_admin = FaqAdmin


class AdvertisementList(HybridListView):
    model = Advertisement
    ordering = ('order_of_appearance',)


class ChangeAdvertisement(ChangeObjectBase):
    model = Advertisement
    model_admin = AdvertisementAdmin
    label_field = 'cta_label'


class SiteList(HybridListView, VerifiedEmailTemplateView):
    queryset = Site.objects.select_related('member', 'site')
    ordering = ('order_of_appearance',)
    context_object_name = 'site_list'
    change_object_url_name = 'change_site'
    template_name = 'econnect/site_list.html'
    html_results_template_name = 'econnect/snippets/site_list_results.html'


class ChangeSite(ChangeObjectBase, VerifiedEmailTemplateView):
    model = Site
    model_admin = SiteAdmin
    template_name = 'econnect/change_site.html'
    object_list_url = 'site_list'

    def get_context_data(self, **kwargs):
        context = super(ChangeSite, self).get_context_data(**kwargs)
        member = self.request.user
        context['member'] = member
        return context

    def after_save(self, request, obj, *args, **kwargs):
        obj.code = obj.code.upper()
        obj.member = request.user
        obj.save()
        try:
            code_client = Profile.objects.get(member=self.request.user).code
            now = datetime.today()
            expiry = last_day_of_the_month(now)
            reference_id = code_client + ":" + obj.code
            subscription, update = Subscription.objects.get_or_create(member=obj.member, reference_id=reference_id)
            subscription.product = obj.package
            subscription.expiry = expiry
            subscription.status = Subscription.ACTIVE
            subscription.save()
            obj.subscription = subscription
            obj.save()
        except Profile.DoesNotExist:
            pass


class PricingNumerilink(PostView):
    template_name = 'econnect/pricing_numerilink_home.html'

    def get_context_data(self, **kwargs):
        context = super(PricingNumerilink, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        lang = get_language()
        try:
            product = Product.objects.get(name=NUMERIHOME, lang=lang)
        except:
            product = get_object_or_404(Product, name=NUMERIHOME, lang='en')
        equipment_order_entry_list = []
        extra_id_list = []
        faq_item_list = []
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        for faq_item in product.faq_set.all():
            faq_item_list.append(faq_item)
        if order_id:
            order = get_object_or_404(Order, pk=order_id)
            for equipment_order_entry in order.equipment_order_entry_list:
                equipment_order_entry_id = equipment_order_entry.equipment_id
                if equipment_order_entry.is_rent:
                    equipment_order_entry_id += '|' + RENTAL
                else:
                    equipment_order_entry_id += '|' + PURCHASE
                equipment_order_entry_list.append(equipment_order_entry_id)
            equipment_order_entry = ';'.join(equipment_order_entry_list)
            for extra in order.extra_list:
                extra_id = extra.id
                extra_id_list.append(extra_id)
            extra = ';'.join(extra_id_list)
            context['equipment_order_entry'] = equipment_order_entry
            context['extra'] = extra
            context['order'] = order
        context['faq_item_list'] = faq_item_list
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        return context


class PricingNumerilinkHotel(PostView):
    template_name = 'econnect/pricing_numerilink_hotel.html'

    def get_context_data(self, **kwargs):
        context = super(PricingNumerilinkHotel, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        lang = get_language()
        try:
            product = Product.objects.get(name=NUMERIHOTEL, lang=lang)
        except:
            product = get_object_or_404(Product, name=NUMERIHOTEL, lang='en')
        analog_package_list = []
        digital_package_list = []
        equipment_order_entry_list = []
        extra_id_list = []
        faq_item_list = []
        equipment_purchase_cost = 0
        for analog_package in product.package_set.filter(type=ANALOG):
            analog_package_list.append(analog_package)
        for digital_package in product.package_set.filter(type=DIGITAL):
            digital_package_list.append(digital_package)
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        for faq_item in product.faq_set.all():
            faq_item_list.append(faq_item)
        if order_id:
            order = get_object_or_404(Order, pk=order_id)
            for equipment_order_entry in order.equipment_order_entry_list:
                equipment_order_entry_id = equipment_order_entry.equipment_id
                if equipment_order_entry.is_rent:
                    equipment_order_entry_id += '|' + RENTAL
                else:
                    equipment_order_entry_id += '|' + PURCHASE
                equipment_order_entry_list.append(equipment_order_entry_id)
            equipment_order_entry = ';'.join(equipment_order_entry_list)
            for extra in order.extra_list:
                extra_id = extra.id
                extra_id_list.append(extra_id)
            extra = ';'.join(extra_id_list)
            context['equipment_order_entry'] = equipment_order_entry
            context['extra'] = extra
            context['order'] = order
        context['faq_item_list'] = faq_item_list
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        context['analog_package_list'] = analog_package_list
        context['digital_package_list'] = digital_package_list
        return context


class PricingHomelink(PostView):
    template_name = 'econnect/pricing_homelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingHomelink, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        lang = get_language()
        try:
            product = Product.objects.get(name=HOME, lang=lang)
        except:
            product = get_object_or_404(Product, name=HOME, lang='en')
        equipment_order_entry_list = []
        extra_id_list = []
        faq_item_list = []
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        for faq_item in product.faq_set.all():
            faq_item_list.append(faq_item)
        if order_id:
            order = get_object_or_404(Order, pk=order_id)
            for equipment_order_entry in order.equipment_order_entry_list:
                equipment_order_entry_id = equipment_order_entry.equipment_id
                if equipment_order_entry.is_rent:
                    equipment_order_entry_id += '|' + RENTAL
                else:
                    equipment_order_entry_id += '|' + PURCHASE
                equipment_order_entry_list.append(equipment_order_entry_id)
            equipment_order_entry = ';'.join(equipment_order_entry_list)
            for extra in order.extra_list:
                extra_id = extra.id
                extra_id_list.append(extra_id)
            extra = ';'.join(extra_id_list)
            context['equipment_order_entry'] = equipment_order_entry
            context['extra'] = extra
            context['order'] = order
        context['faq_item_list'] = faq_item_list
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        return context


class PricingOfficelink(PostView):
    template_name = 'econnect/pricing_officelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingOfficelink, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        lang = get_language()
        try:
            product = Product.objects.get(name=OFFICE, lang=lang)
        except:
            product = get_object_or_404(Product, name=OFFICE, lang='en')
        equipment_order_entry_list = []
        extra_id_list = []
        faq_item_list = []
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        for faq_item in product.faq_set.all():
            faq_item_list.append(faq_item)
        if order_id:
            order = get_object_or_404(Order, pk=order_id)
            for equipment_order_entry in order.equipment_order_entry_list:
                equipment_order_entry_id = equipment_order_entry.equipment_id
                if equipment_order_entry.is_rent:
                    equipment_order_entry_id += '|' + RENTAL
                else:
                    equipment_order_entry_id += '|' + PURCHASE
                equipment_order_entry_list.append(equipment_order_entry_id)
            equipment_order_entry = ';'.join(equipment_order_entry_list)
            for extra in order.extra_list:
                extra_id = extra.id
                extra_id_list.append(extra_id)
            extra = ';'.join(extra_id_list)
            context['equipment_order_entry'] = equipment_order_entry
            context['extra'] = extra
            context['order'] = order
        context['faq_item_list'] = faq_item_list
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        return context


class PricingCorporatelink(PostView):
    template_name = 'econnect/pricing_corporatelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingCorporatelink, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        lang = get_language()
        try:
            product = Product.objects.get(name=CORPORATE, lang=lang)
        except:
            product = get_object_or_404(Product, name=CORPORATE, lang='en')
        equipment_order_entry_list = []
        extra_id_list = []
        faq_item_list = []
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        for faq_item in product.faq_set.all():
            faq_item_list.append(faq_item)
        if order_id:
            order = get_object_or_404(Order, pk=order_id)
            for equipment_order_entry in order.equipment_order_entry_list:
                equipment_order_entry_id = equipment_order_entry.equipment_id
                if equipment_order_entry.is_rent:
                    equipment_order_entry_id += '|' + RENTAL
                else:
                    equipment_order_entry_id += '|' + PURCHASE
                equipment_order_entry_list.append(equipment_order_entry_id)
            equipment_order_entry = ';'.join(equipment_order_entry_list)
            for extra in order.extra_list:
                extra_id = extra.id
                extra_id_list.append(extra_id)
            extra = ';'.join(extra_id_list)
            context['equipment_order_entry'] = equipment_order_entry
            context['extra'] = extra
            context['order'] = order
        context['faq_item_list'] = faq_item_list
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        return context


class Offline(TemplateView):
    template_name = 'econnect/offline.html'


class ChangeMailCampaign(CampaignBaseView, ChangeObjectBase):
    template_name = "econnect/admin/change_mailcampaign.html"
    model = MailCampaign
    model_admin = MailCampaignAdmin
    context_object_name = 'campaign'

    def get_context_data(self, **kwargs):
        context = super(ChangeMailCampaign, self).get_context_data(**kwargs)
        obj = context['obj']
        context['csv_model'] = "ikwen_MAIL_campaign_csv_model"
        if obj:
            obj.terminated = obj.progress > 0 and obj.progress == obj.total
        items_fk_list = []
        if self.request.GET.get('items_fk_list'):
            items_fk_list = self.request.GET.get('items_fk_list').split(',')
            obj.items_fk_list = items_fk_list
            obj.save(using=UMBRELLA)
            context['set_cyclic'] = True
        context['items_fk_list'] = ','.join(items_fk_list)
        context['item_list'] = get_item_list('kako.Product', items_fk_list)
        return context

    def get_object(self, **kwargs):
        object_id = kwargs.get('object_id')  # May be overridden with the one from GET data
        if object_id:
            try:
                return MailCampaign.objects.using(UMBRELLA).get(pk=object_id)
            except MailCampaign.DoesNotExist:
                raise Http404()

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == 'toggle_campaign':
            return self.toggle_campaign(request, *args, **kwargs)
        if action == 'run_test':
            return self.run_test(request, *args, **kwargs)
        if action == 'clone_campaign':
            return self.clone_campaign(request, *args, **kwargs)
        return super(ChangeMailCampaign, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        object_admin = get_model_admin_instance(self.model, self.model_admin)
        object_id = kwargs.get('object_id')
        service = get_service_instance(using=UMBRELLA)
        member = request.user
        mbr = Member.objects.using(UMBRELLA).get(pk=member.id)
        if object_id:
            while True:
                try:
                    obj = MailCampaign.objects.using(UMBRELLA).get(pk=object_id)
                    break
                except MailCampaign.DoesNotExist:
                    time.sleep(0.5)
        else:
            obj = self.model()
        model_form = object_admin.get_form(request)
        form = model_form(request.POST, instance=obj)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            pre_header = form.cleaned_data['pre_header']
            content = form.cleaned_data['content']
            order_id = request.POST.get('order_id')
            if order_id:
                cta = _("Confirm my order now")
                cta_url = service.url + reverse('econnect:order_confirm') + '?order_id=' + order_id
            else:
                cta = form.cleaned_data['cta']
                cta_url = form.cleaned_data['cta_url']
            recipient_label, recipient_label_raw, recipient_src, recipient_list, checked_profile_tag_id_list, \
                recipient_profile = self.get_recipient_list(request)
            slug = slugify(subject)
            if not object_id:
                obj = MailCampaign(service=service, member=mbr)

            obj.subject = subject
            obj.slug = slug
            obj.pre_header = pre_header
            obj.content = content
            obj.cta = cta
            obj.cta_url = cta_url
            obj.recipient_label = recipient_label
            obj.recipient_label_raw = recipient_label_raw
            obj.recipient_src = recipient_src
            obj.recipient_profile = recipient_profile
            obj.recipient_list = recipient_list
            obj.total = len(recipient_list)
            obj.save(using=UMBRELLA)

            image_url = request.POST.get('image_url')
            if image_url:
                s = get_service_instance()
                image_field_name = request.POST.get('image_field_name', 'image')
                image_field = obj.__getattribute__(image_field_name)
                if not image_field.name or image_url != image_field.url:
                    filename = image_url.split('/')[-1]
                    media_root = getattr(settings, 'MEDIA_ROOT')
                    media_url = getattr(settings, 'MEDIA_URL')
                    path = image_url.replace(media_url, '')
                    try:
                        with open(media_root + path, 'r') as f:
                            content = File(f)
                            destination = media_root + obj.UPLOAD_TO + "/" + s.project_name_slug + '_' + filename
                            image_field.save(destination, content)
                        os.unlink(media_root + path)
                    except IOError as e:
                        if getattr(settings, 'DEBUG', False):
                            raise e
                        return {'error': 'File failed to upload. May be invalid or corrupted image file'}
            if request.POST.get('keep_editing'):
                next_url = reverse('econnect:change_mailcampaign', args=(obj.id,))
            else:
                next_url = self.get_object_list_url(request, obj, *args, **kwargs)
            if object_id:
                messages.success(request, obj._meta.verbose_name.capitalize() + ' <strong>' + str(obj).decode(
                    'utf8') + '</strong> ' + _('successfully updated').decode('utf8'))
            else:
                messages.success(request, obj._meta.verbose_name.capitalize() + ' <strong>' + str(obj).decode(
                    'utf8') + '</strong> ' + _('successfully created').decode('utf8'))
            return HttpResponseRedirect(next_url)
        else:
            context = self.get_context_data(**kwargs)
            context['errors'] = form.errors
            return render(request, self.template_name, context)

    def start_campaign(self, request, *args, **kwargs):
        campaign_id = kwargs['object_id']
        campaign = MailCampaign.objects.using(UMBRELLA).get(pk=campaign_id)
        if campaign.is_started and not campaign.keep_running:
            response = {"error": "Campaign already started"}
            return HttpResponse(json.dumps(response), 'content-type: text/json')
        balance = Balance.objects.using('wallets').get(service_id=get_service_instance().id)
        campaign.keep_running = True
        campaign.is_started = True
        campaign.save()
        # "transaction.atomic" instruction locks database during all operations inside "with" block
        try:
            if balance.mail_count < campaign.total:
                response = {"insufficient_balance": _("Insufficient Email balance.")}
                return HttpResponse(json.dumps(response), 'content-type: text/json')
            with transaction.atomic(using='wallets'):
                balance.mail_count -= campaign.total
                balance.save()
                if getattr(settings, 'UNIT_TESTING', False):
                    batch_send_mail(campaign)
                elif campaign.total < 50:
                    # for small campaign ie minor than 50, send sms directly from application server
                    Thread(target=batch_send_mail, args=(campaign,)).start()
                response = {"success": True, "balance": balance.mail_count, "campaign": campaign.to_dict()}
        except Exception as e:
            response = {"error": "Error while submitting your campaign. Please try again later."}

        return HttpResponse(json.dumps(response), 'content-type: text/json')

    def toggle_campaign(self, request, *args, **kwargs):
        campaign_id = kwargs['object_id']
        campaign = MailCampaign.objects.using(UMBRELLA).get(pk=campaign_id)
        campaign.keep_running = not campaign.keep_running
        campaign.save()
        response = {"success": True, "campaign": campaign.to_dict()}
        return HttpResponse(json.dumps(response), 'content-type: text/json')

    def run_test(self, request, *args, **kwargs):
        campaign_id = kwargs['object_id']
        campaign = MailCampaign.objects.using(UMBRELLA).get(pk=campaign_id)
        test_email_list = request.GET['test_email_list'].split(',')
        test_email_count = len(test_email_list)
        service = get_service_instance()
        balance = Balance.objects.using(WALLETS_DB_ALIAS).get(service_id=service.id)
        if balance.mail_count < test_email_count:
            response = {'error': 'Insufficient Email and SMS credit'}
            return HttpResponse(json.dumps(response))

        connection = mail.get_connection()
        try:
            connection.open()
        except:
            response = {'error': 'Failed to connect to mail server. Please check your internet'}
            return HttpResponse(json.dumps(response))
        config = service.config

        warning = []
        for email in test_email_list[:5]:
            if balance.mail_count == 0:
                warning.append('Insufficient email Credit')
                break
            email = email.strip()
            subject = "Test - " + campaign.subject
            try:
                member = Member.objects.filter(email=email)[0]
                message = campaign.content.replace('$client', member.first_name)
            except:
                message = campaign.content.replace('$client', "")
            sender = '%s <no-reply@%s>' % (config.company_name, service.domain)
            media_url = ikwen_settings.CLUSTER_MEDIA_URL + service.project_name_slug + '/'
            product_list = []
            if campaign.items_fk_list:
                app_label, model_name = campaign.model_name.split('.')
                item_model = get_model(app_label, model_name)
                product_list = item_model._default_manager.filter(pk__in=campaign.items_fk_list)
            try:
                currency = Currency.objects.get(is_base=True)
            except Currency.DoesNotExist:
                currency = None
            html_content = get_mail_content(subject, message, template_name='echo/mails/campaign.html',
                                            extra_context={'media_url': media_url, 'product_list': product_list,
                                                           'campaign': campaign, 'currency': currency})
            msg = EmailMessage(subject, html_content, sender, [email])
            msg.content_subtype = "html"
            try:
                with transaction.atomic(using='wallets'):
                    balance.mail_count -= 1
                    balance.save()
                    if not msg.send():
                        transaction.rollback(using='wallets')
                        warning.append('Mail not sent to %s' % email)
            except:
                pass
        try:
            connection.close()
        except:
            pass

        response = {'success': True, 'warning': warning}
        return HttpResponse(json.dumps(response))
