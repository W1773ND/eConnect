from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.template.defaultfilters import slugify
from django_mongodb_engine.contrib import _compiler_for_queryset

from ikwen.accesscontrol.backends import UMBRELLA
from ikwen.core.views import HybridListView, ChangeObjectBase
from ikwen.billing.models import Payment

from django.views.generic import TemplateView

from econnect.admin import ProductAdmin, PackageAdmin, EquipmentAdmin, ExtraAdmin
from econnect.models import Order, CustomerRequest, Product, Package, Equipment, Extra


class Maps(TemplateView):
    template_name = 'econnect/maps.html'


class Admin(TemplateView):
    template_name = 'econnect/admin/admin_home.html'


class OrderList(HybridListView):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/admin/snippets/order_list_result.html'
    model = Order
    queryset = Order.objects.using(UMBRELLA).all()
    search_field = 'member'
    context_object_name = 'order'


class CustomerRequestList(HybridListView):
    template_name = 'econnect/admin/request_list.html'
    html_results_template_name = 'econnect/admin/snippets/request_list_result.html'
    model = CustomerRequest
    queryset = CustomerRequest.objects.using(UMBRELLA).all()
    search_field = 'member'
    context_object_name = 'customerRequest'


class Home(TemplateView):
    template_name = 'econnect/homepage.html'

    def get_context_data(self, **kwargs):
        context = super(Home, self).get_context_data(**kwargs)
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


class PricingNumerilink(TemplateView):
    template_name = 'econnect/pricing_numerilink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingNumerilink, self).get_context_data(**kwargs)
        product = Product.objects.get(name='NumeriLink')
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['default_equipment_cost'] = product.instalation_cost + equipment_purchase_cost
        context['product'] = product
        return context


class PricingHomelink(TemplateView):
    template_name = 'econnect/pricing_homelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingHomelink, self).get_context_data(**kwargs)
        product = Product.objects.get(name='HomeLink')
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['default_equipment_cost'] = product.instalation_cost + equipment_purchase_cost
        context['product'] = product
        return context


class PricingOfficelink(TemplateView):
    template_name = 'econnect/pricing_officelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingOfficelink, self).get_context_data(**kwargs)
        product = Product.objects.get(name='OfficeLink')
        equipment_list = Equipment.objects.filter(product=product)
        equipment_purchase_cost = 0
        for equipment in equipment_list:
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['default_equipment_cost'] = product.instalation_cost + equipment_purchase_cost
        context['equipment_list'] = equipment_list
        context['product'] = product
        return context


class PricingCorporatelink(TemplateView):
    template_name = 'econnect/pricing_corporatelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingCorporatelink, self).get_context_data(**kwargs)
        product = Product.objects.get(name='CorporateLink')
        equipment_list = Equipment.objects.filter(product=product)
        equipment_purchase_cost = 0
        for equipment in equipment_list:
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['default_equipment_cost'] = product.instalation_cost + equipment_purchase_cost
        context['equipment_list'] = equipment_list
        context['product'] = product
        return context
