# -*- coding: utf-8 -*-

__author__ = 'W1773ND (wilfriedwillend@gmail.com)'

from datetime import datetime, timedelta

import requests
import urlparse
import os
import time
import json

from threading import Thread

from currencies.models import Currency

from django.conf import settings
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.db import transaction
from django.core import mail
from django.views.generic import TemplateView
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.core.exceptions import MultipleObjectsReturned
from django.template.defaultfilters import slugify
from django.utils.translation import gettext as _

from ikwen.conf import settings as ikwen_settings
from ikwen.conf.settings import WALLETS_DB_ALIAS
from ikwen.accesscontrol.backends import UMBRELLA
from ikwen.accesscontrol.models import Member, DEFAULT_GHOST_PWD
from ikwen.core.models import Service
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

from econnect.admin import ProductAdmin, PackageAdmin, EquipmentAdmin, ExtraAdmin
from econnect.forms import OrderForm
from econnect.models import Subscription, Order, CustomerRequest, Product, Package, Equipment, EquipmentOrderEntry, \
    Extra, RENTAL, PURCHASE, REPORTED, FINISHED, DEVICE_ID, \
    NUMERIHOME, NUMERIHOTEL, HOME, OFFICE, CORPORATE, ANALOG, DIGITAL, ECONNECT

import logging
logger = logging.getLogger('ikwen')


def set_prospect(order, url, payload):
    resp = requests.get(url, params=payload)
    if DEVICE_ID in resp.text:
        order.maps_url = resp.text
        parsed_query = urlparse.urlparse(resp.text).query
        query = urlparse.parse_qs(parsed_query)
        device_id = query[DEVICE_ID][0]
        order.maps_id = device_id
        order.save()
    else:
        pass


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
                    context['product_url'] = reverse('econnect:' + product.slug) + '?order_id=' + order.id
                    break
                except Order.DoesNotExist:
                    time.sleep(0.5)
        return context

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == 'confirm_order':
            return self.confirm_order(request, *args, **kwargs)
        return super(OrderConfirm, self).get(request, *args, **kwargs)

    @staticmethod
    def confirm_order(request):
        order_id = request.GET['order_id']
        order = get_object_or_404(Order, id=order_id)
        order.status = PENDING
        order.save()
        member = order.member
        lat = order.location_lat
        lng = order.location_lng

        if getattr(settings, 'DEBUG', False):
            prospect_url = getattr(settings, "LOCAL_MAPS_URL") + 'save_prospect'
            payload = {
                'customer_name': member.full_name,
                'lat': lat,
                'lng': lng,
                'order_id': order_id,
                'debug': 'true'
            }
        else:
            prospect_url = getattr(settings, "CREOLINK_MAPS_URL") + 'save_prospect'
            payload = {
                'customer_name': member.full_name,
                'lat': lat,
                'lng': lng,
                'order_id': order_id
            }
        Thread(target=set_prospect, args=(order, prospect_url, payload)).start()

        response = {"success": True}
        return HttpResponse(json.dumps(response), 'content-type: text/json')


class PendingOrderList(HybridListView):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/admin/snippets/order_list_results.html'
    queryset = Order.objects.exclude(status__in=[REPORTED, Invoice.PAID, FINISHED])
    search_field = 'member'
    list_filter = ('created_on', 'status')
    context_object_name = 'order'

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == 'set_equipment':
            return self.set_equipment(request)
        if action == 'accept_order':
            return self.accept_order(request)
        elif action == 'report_order':
            return self.report_order(request)
        return super(PendingOrderList, self).get(request, *args, **kwargs)

    @staticmethod
    def set_equipment(request):
        order_id = request.GET['order_id']
        order = get_object_or_404(Order, id=order_id)
        member = order.member
        lat = order.location_lat
        lng = order.location_lng

        if getattr(settings, 'DEBUG', False):
            prospect_url = getattr(settings, "LOCAL_MAPS_URL") + 'save_prospect'
            payload = {
                'customer_name': member.full_name,
                'lat': lat,
                'lng': lng,
                'order_id': order_id,
                'debug': 'true'
            }
        else:
            prospect_url = getattr(settings, "CREOLINK_MAPS_URL") + 'save_prospect'
            payload = {
                'customer_name': member.full_name,
                'lat': lat,
                'lng': lng,
                'order_id': order_id
            }

        Thread(target=set_prospect, args=(order, prospect_url, payload)).start()
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
        due_date = datetime.now() + timedelta(days=config.payment_delay)
        subscription = Subscription.objects.create(member=member, product=order.package, monthly_cost=amount,
                                                   billing_cycle=Service.MONTHLY, details='', order=order)
        invoice = Invoice.objects.create(subscription=subscription, member=member, number=number, amount=order.cost,
                                         months_count=1, due_date=due_date.date(), is_one_off=True, entries=entries)
        try:
            subject = _("Dear " + member.full_name + ", we are ready to come and install your service.")
            invoice_url = service.url + reverse('billing:invoice_detail', args=(invoice.id,))
            html_content = get_mail_content(subject, template_name='econnect/mails/order_accepted.html',
                                            extra_context={'invoice_url': invoice_url,
                                                           'order_label': label,
                                                           'order_location': order_location
                                                           })
            sender = 'Creolink Communications <no-reply@creolink.com>'
            msg = XEmailMessage(subject, html_content, sender, [member.email])
            msg.content_subtype = "html"
            Thread(target=lambda m: m.send(), args=(msg,)).start()
        except:
            logger.error("Mail sending failed", exc_info=True)
            response = {"success": True, "Mail": False}
            return HttpResponse(json.dumps(response), 'content-type: text/json')

        if getattr(settings, 'DEBUG', False):
            customer_url = getattr(settings, "LOCAL_MAPS_URL") + 'update_prospect'
            payload = {DEVICE_ID: order.maps_id}

        else:
            customer_url = getattr(settings, "CREOLINK_MAPS_URL") + 'update_prospect'
            payload = {DEVICE_ID: order.maps_id}

        Thread(target=requests.get, args=(customer_url, payload)).start()

        response = {"success": True}
        return HttpResponse(json.dumps(response), 'content-type: text/json')

    @staticmethod
    def report_order(request):
        order_id = request.GET['order_id']
        order = get_object_or_404(Order, id=order_id)
        order.status = REPORTED
        order.save()
        member = order.member
        product_name = order.package.product.name
        package_name = order.package.name
        label = product_name + ' [' + package_name + ']'
        order_location = order.formatted_address

        try:
            subject = _("Dear " + member.full_name + ", we'll come soon as possible to install your service.")
            html_content = get_mail_content(subject, template_name='econnect/mails/order_reported.html',
                                            extra_context={'order_label': label,
                                                           'order_location': order_location
                                                           })
            sender = 'Creolink Communications <no-reply@creolink.com>'
            msg = XEmailMessage(subject, html_content, sender, [member.email])
            msg.content_subtype = "html"
            Thread(target=lambda m: m.send(), args=(msg,)).start()
        except:
            logger.error("Mail sending failed", exc_info=True)
            response = {"success": True, "Mail": False}
            return HttpResponse(json.dumps(response), 'content-type: text/json')

        response = {"success": True}
        return HttpResponse(json.dumps(response), 'content-type: text/json')


class PaidOrderList(HybridListView):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/admin/snippets/order_list_results.html'
    queryset = Order.objects.filter(status=Invoice.PAID)
    search_field = 'member'
    list_filter = ('created_on',)
    context_object_name = 'order'

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == 'finish_order':
            return self.finish_order(request)
        return super(PaidOrderList, self).get(request, *args, **kwargs)

    @staticmethod
    def finish_order(request):
        order_id = request.GET['order_id']
        order = get_object_or_404(Order, id=order_id)
        order.status = FINISHED
        order.save()
        member = order.member
        product_name = order.package.product.name
        package_name = order.package.name
        label = product_name + ' [' + package_name + ']'
        order_location = order.formatted_address
        try:
            subject = _("Dear " + member.full_name + ", thanks to business with Creolink Communications.")
            html_content = get_mail_content(subject, template_name='econnect/mails/service_completed.html',
                                            extra_context={'order_label': label,
                                                           'order_location': order_location
                                                           })
            sender = 'Creolink Communications <no-reply@creolink.com>'
            msg = XEmailMessage(subject, html_content, sender, [member.email])
            msg.content_subtype = "html"
            Thread(target=lambda m: m.send(), args=(msg,)).start()
        except:
            logger.error("Mail sending failed", exc_info=True)
            response = {"success": True, "Mail": False}
            return HttpResponse(json.dumps(response), 'content-type: text/json')
        response = {"success": True}
        return HttpResponse(json.dumps(response), 'content-type: text/json')


class ReportedOrderList(HybridListView):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/admin/snippets/order_list_results.html'
    queryset = Order.objects.filter(status=REPORTED)
    search_field = 'member'
    list_filter = ('created_on',)
    context_object_name = 'order'


class Admin(TemplateView):
    template_name = 'econnect/admin/admin_home.html'


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
        product_list = []
        for product in Product.objects.all().exclude(name=NUMERIHOTEL):
            product.url = reverse('econnect:' + product.slug)
            product_list.append(product)
        product_numeri_hotel = Product.objects.get(name=NUMERIHOTEL)
        product_numeri_hotel.slug = slugify(product_numeri_hotel.name)
        product_numeri_hotel.url = reverse('econnect:' + product_numeri_hotel.slug)
        context['product_list'] = product_list
        context['product_numeri_hotel'] = product_numeri_hotel
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
                member = Member.objects.create_user(username, DEFAULT_GHOST_PWD, email=visitor_email, is_ghost=True)
                tag = ECONNECT
                econnect_tag, change = ProfileTag.objects.get_or_create(slug=tag)
                member_profile = MemberProfile.objects.get(member=member)
                member_profile.tag_fk_list = [econnect_tag.id]
                member_profile.save()
                next_url = reverse('ikwen:logout') + "?next=" + reverse('ikwen:register')
                try:
                    subject = _("Do more with Creolink Communications !")
                    html_content = get_mail_content(subject, template_name='accesscontrol/mails/complete_registration.html',
                                                    extra_context={'member_email': visitor_email, 'next_url': next_url}, )
                    sender = '%s <no-reply@%s>' % (config.company_name, service.domain)
                    msg = EmailMessage(subject, html_content, sender, [visitor_email])
                    msg.content_subtype = "html"
                    Thread(target=lambda m: m.send(), args=(msg,)).start()
                except:
                    logger.error("Mail sending failed", exc_info=True)
            if request.user.is_anonymous():
                ghost_member = authenticate(username=visitor_email, password=DEFAULT_GHOST_PWD)
                login(request, ghost_member)
        return HttpResponseRedirect(next_url)


class ProductList(HybridListView):
    model = Product
    search_field = 'name'


class ChangeProduct(ChangeObjectBase):
    model = Product
    model_admin = ProductAdmin


class PackageList(HybridListView):
    model = Package
    list_filter = ('product',)
    search_field = 'name'


class ChangePackage(ChangeObjectBase):
    model = Package
    model_admin = PackageAdmin


class EquipmentList(HybridListView):
    model = Equipment
    list_filter = ('product',)
    search_field = 'name'


class ChangeEquipment(ChangeObjectBase):
    model = Equipment
    model_admin = EquipmentAdmin


class ExtraList(HybridListView):
    model = Extra
    list_filter = ('product',)
    search_field = 'name'


class ChangeExtra(ChangeObjectBase):
    model = Extra
    model_admin = ExtraAdmin


class PricingNumerilink(PostView):
    template_name = 'econnect/pricing_numerilink_home.html'

    def get_context_data(self, **kwargs):
        context = super(PricingNumerilink, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        product = get_object_or_404(Product, name=NUMERIHOME)
        equipment_order_entry_list = []
        extra_id_list = []
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
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
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        return context


class PricingNumerilinkHotel(PostView):
    template_name = 'econnect/pricing_numerilink_hotel.html'

    def get_context_data(self, **kwargs):
        context = super(PricingNumerilinkHotel, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        product = get_object_or_404(Product, name=NUMERIHOTEL)
        package_analog_list = []
        package_digital_list = []
        equipment_order_entry_list = []
        extra_id_list = []
        equipment_purchase_cost = 0
        for package_analog in product.package_set.filter(type=ANALOG):
            package_analog_list.append(package_analog)
        for package_digital in product.package_set.filter(type=DIGITAL):
            package_digital_list.append(package_digital)
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
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
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        context['package_analog_list'] = package_analog_list
        context['package_digital_list'] = package_digital_list
        return context


class PricingHomelink(PostView):
    template_name = 'econnect/pricing_homelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingHomelink, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        product = get_object_or_404(Product, name=HOME)
        equipment_order_entry_list = []
        extra_id_list = []
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
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
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        return context


class PricingOfficelink(PostView):
    template_name = 'econnect/pricing_officelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingOfficelink, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        product = get_object_or_404(Product, name=OFFICE)
        equipment_order_entry_list = []
        extra_id_list = []
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
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
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        return context


class PricingCorporatelink(PostView):
    template_name = 'econnect/pricing_corporatelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingCorporatelink, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        product = get_object_or_404(Product, name=CORPORATE)
        equipment_order_entry_list = []
        extra_id_list = []
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
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
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        return context


class About(TemplateView):
    template_name = 'econnect/about.html'


class Legal(TemplateView):
    template_name = 'econnect/legal.html'


class Privacy(TemplateView):
    template_name = 'econnect/privacy.html'


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
            recipient_label, recipient_label_raw, recipient_src, recipient_list, recipient_profile = self.get_recipient_list(
                request)
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
