# -*- coding: utf-8 -*-
__author__ = 'W1773ND (wilfriedwillend@gmail.com)'

import json


from django.core.serializers import json
from django.core.urlresolvers import reverse
from django.forms import ModelForm
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.template.defaultfilters import slugify
from django.utils.http import urlquote
from django_mongodb_engine.contrib import _compiler_for_queryset

from ikwen.accesscontrol.backends import UMBRELLA
from ikwen.accesscontrol.models import Member
from ikwen.core.views import HybridListView, ChangeObjectBase
from ikwen.core.constants import PENDING, PENDING_FOR_PAYMENT
from ikwen.core.utils import get_model_admin_instance
from ikwen.billing.models import Payment

from django.views.generic import TemplateView

from econnect.admin import ProductAdmin, PackageAdmin, EquipmentAdmin, ExtraAdmin
from econnect.forms import OrderForm
from econnect.models import Order, CustomerRequest, Product, Package, Equipment, EquipmentOrderEntry, Extra, RENTAL, \
    NUMERI, HOME, OFFICE, CORPORATE, OPTIONAL_TV_COST, PURCHASE


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
            if optional_tv and optional_tv >= 2:
                optional_tv = int(optional_tv)
                optional_tv_cost = (optional_tv - 1) * OPTIONAL_TV_COST
                order_cost += optional_tv_cost
            member = get_object_or_404(Member, pk=customer_id)
            package = get_object_or_404(Package, pk=pack_id)
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
                order.status = PENDING
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


class AdminView(TemplateView):
    template_name = 'econnect/admin/admin_home.html'


class OrderList(HybridListView):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/admin/snippets/order_list_results.html'
    model = Order
    search_field = 'member'
    list_filter = ('created_on', 'status')
    context_object_name = 'order'


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
        for product in Product.objects.all():
            product.url = reverse('econnect:' + product.slug)
            product_list.append(product)
        context['product_list'] = product_list
        return context


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


class PricingNumerilinkView(PostView):
    template_name = 'econnect/pricing_numerilink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingNumerilinkView, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        product = get_object_or_404(Product, name=NUMERI)
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


class PricingHomelinkView(PostView):
    template_name = 'econnect/pricing_homelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingHomelinkView, self).get_context_data(**kwargs)
        product = get_object_or_404(Product, name=HOME)
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
        return context


class PricingOfficelinkView(PostView):
    template_name = 'econnect/pricing_officelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingOfficelinkView, self).get_context_data(**kwargs)
        product = get_object_or_404(Product, name=OFFICE)
        equipment_list = Equipment.objects.filter(product=product)
        equipment_purchase_cost = 0
        for equipment in equipment_list:
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['equipment_list'] = equipment_list
        context['product'] = product
        return context


class PricingCorporatelinkView(PostView):
    template_name = 'econnect/pricing_corporatelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingCorporatelinkView, self).get_context_data(**kwargs)
        product = get_object_or_404(Product, name=CORPORATE)
        equipment_list = Equipment.objects.filter(product=product)
        equipment_purchase_cost = 0
        for equipment in equipment_list:
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['equipment_list'] = equipment_list
        context['product'] = product
        return context


class OrderConfirmView(TemplateView):
    template_name = 'econnect/order_confirm.html'

    def get_context_data(self, **kwargs):
        context = super(OrderConfirmView, self).get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        if order_id:
            order = get_object_or_404(Order, pk=order_id)
            product = order.package.product
            context['order'] = order
            context['product_url'] = reverse('econnect:' + product.slug) + '?order_id=' + order.id
        return context

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == 'confirm_order':
            return self.confirm_order(request, *args, **kwargs)
        return super(OrderConfirmView, self).get(request, *args, **kwargs)

    def confirm_order(self, request):
        order_id = request.GET['order_id']
        order = get_object_or_404(Order, id=order_id)
        order.status = PENDING
        order.save()
        response = {"success": True}
        return HttpResponse(
            json.dumps(response),
            'content-type: text/json'
        )
