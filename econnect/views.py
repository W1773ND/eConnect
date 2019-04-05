from django.shortcuts import render
from django_mongodb_engine.contrib import _compiler_for_queryset

from ikwen.accesscontrol.backends import UMBRELLA
from ikwen.core.views import HybridListView, ChangeObjectBase
from ikwen.billing.models import Payment

from django.views.generic import TemplateView

from econnect.admin import ProductAdmin, PackageAdmin, EquipmentAdmin, ExtraAdmin
from econnect.models import Order, CustomerRequest, Product, Package, Equipment, Extra


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
        equipment = Equipment.objects.get(product=product)
        context['product'] = product
        context['equipment_name'] = equipment.name
        context['default_equipment_cost'] = product.installation_cost + equipment.purchase_cost
        return context
